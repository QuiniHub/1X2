import json
from pathlib import Path

from generar_memoria_mundial_2026 import normalizar_nombre

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
MEMORIA_MUNDIAL = DATA / "memoria_ia" / "mundial_2026_forma.json"


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clamp(valor, minimo, maximo):
    return max(min(float(valor), maximo), minimo)


def normalizar_probs(probs):
    p = {k: max(float(probs.get(k, 1)), 1.0) for k in ("1", "X", "2")}
    total = sum(p.values()) or 1.0
    return {k: round(v / total * 100, 1) for k, v in p.items()}


def fuerza_mundial(equipo):
    if not equipo:
        return 0.0
    pj = max(float(equipo.get("pj") or 1), 1.0)
    tendencias = equipo.get("tendencias") or {}
    ppg = float(equipo.get("pts") or 0) / pj
    dg = float(equipo.get("dg") or 0) / pj
    gf = float(tendencias.get("goles_favor_por_partido") or 0)
    gc = float(tendencias.get("goles_contra_por_partido") or 0)
    forma = float(tendencias.get("forma_5_pts") or 0) / min(pj, 5.0)
    empates = float(tendencias.get("empates_pct") or 0)
    return ppg * 32 + dg * 12 + gf * 7 - gc * 7 + forma * 16 + empates * 0.05


def modelo_mundial(local, visitante):
    diff = fuerza_mundial(local) - fuerza_mundial(visitante)
    emp_l = float((local.get("tendencias") or {}).get("empates_pct") or 0)
    emp_v = float((visitante.get("tendencias") or {}).get("empates_pct") or 0)
    empate_medio = (emp_l + emp_v) / 2.0
    probs = {
        "1": 36 + clamp(diff * 0.42, -20, 20),
        "X": 28 + max(0.0, 14 - abs(diff) * 0.18) + empate_medio * 0.04,
        "2": 36 + clamp(-diff * 0.42, -20, 20),
    }
    return normalizar_probs(probs), round(diff, 2)


def mezclar_probs(base, mundial, peso):
    return normalizar_probs({
        signo: float(base.get(signo, 33.3)) * (1 - peso) + float(mundial.get(signo, 33.3)) * peso
        for signo in ("1", "X", "2")
    })


def signo_top(probs):
    return sorted(probs.items(), key=lambda item: item[1], reverse=True)[0][0]


def margen(probs):
    valores = sorted([float(v) for v in probs.values()], reverse=True)
    return round(valores[0] - valores[1], 2) if len(valores) >= 2 else 0.0


def tercera_prob(probs):
    valores = sorted([float(v) for v in probs.values()], reverse=True)
    return round(valores[2], 2) if len(valores) >= 3 else 0.0


def incertidumbre(probs, muestra_minima):
    valores = sorted([float(v) for v in probs.values()], reverse=True)
    if len(valores) < 2:
        return 160.0
    penalizacion_muestra = 22 if muestra_minima <= 1 else 10 if muestra_minima == 2 else 0
    return round(100 - (valores[0] - valores[1]) + float(probs.get("X", 0)) * 0.35 + penalizacion_muestra, 2)


def prob_sorpresa(probs, inc):
    top = max(float(v) for v in probs.values())
    extra = max(min((inc - 90) * 0.25, 16), 0)
    return round(clamp(100 - top + extra, 18, 70), 1)


def indice_sorpresa(probs, inc, muestra_minima):
    top = max(float(v) for v in probs.values())
    marg = margen(probs)
    tercera = tercera_prob(probs)
    score = 100 - top + max(0, 22 - marg) + max(0, tercera - 18) * 1.1 + max(0, inc - 120) * 0.18
    if muestra_minima <= 1:
        score += 10
    return round(clamp(score, 0, 100), 1)


def cobertura_desde_riesgo(probs, indice, sorpresa):
    marg = margen(probs)
    tercera = tercera_prob(probs)
    if indice >= 76 and tercera >= 18 and (marg <= 10 or sorpresa >= 60):
        return "TRIPLE"
    if indice >= 55 or marg <= 12 or sorpresa >= 55:
        return "DOBLE"
    return "FIJO"


def calidad_muestra(local, visitante):
    muestra_minima = min(int(local.get("pj") or 0), int(visitante.get("pj") or 0))
    if muestra_minima >= 3:
        return "alta", muestra_minima
    if muestra_minima >= 1:
        return "media", muestra_minima
    return "baja", muestra_minima


def resumen_equipo(equipo):
    tendencias = equipo.get("tendencias") or {}
    return {
        "equipo": equipo.get("equipo"),
        "pj": equipo.get("pj"),
        "pts": equipo.get("pts"),
        "gf": equipo.get("gf"),
        "gc": equipo.get("gc"),
        "dg": equipo.get("dg"),
        "forma_5_pts": tendencias.get("forma_5_pts"),
        "goles_favor_por_partido": tendencias.get("goles_favor_por_partido"),
        "goles_contra_por_partido": tendencias.get("goles_contra_por_partido"),
        "partidos": equipo.get("partidos", [])[-3:],
    }


def aplicar_mundial_a_partido(partido, equipos):
    local = equipos.get(normalizar_nombre(partido.get("local")))
    visitante = equipos.get(normalizar_nombre(partido.get("visitante")))
    if not local or not visitante:
        partido.setdefault("diagnostico_calidad", {})["mundial_2026"] = {
            "aplicado": False,
            "motivo": "No hay historial del Mundial 2026 para ambos equipos.",
            "local_en_memoria": bool(local),
            "visitante_en_memoria": bool(visitante),
        }
        if partido.get("origen_probabilidades", "").startswith("fallback"):
            partido["calidad_datos"] = "baja"
        return partido

    base = partido.get("probabilidades") or {"1": 33.3, "X": 33.3, "2": 33.3}
    mundial_probs, diff = modelo_mundial(local, visitante)
    calidad, muestra_minima = calidad_muestra(local, visitante)
    peso = 0.72 if muestra_minima == 1 else 0.82 if muestra_minima == 2 else 0.90
    probs = mezclar_probs(base, mundial_probs, peso)
    inc = incertidumbre(probs, muestra_minima)
    sorpresa = prob_sorpresa(probs, inc)
    indice = indice_sorpresa(probs, inc, muestra_minima)
    cobertura = cobertura_desde_riesgo(probs, indice, sorpresa)
    top = signo_top(probs)
    signos_ordenados = [s for s, _ in sorted(probs.items(), key=lambda item: item[1], reverse=True)]

    partido["probabilidades"] = probs
    partido["signo_base"] = top
    partido["incertidumbre"] = inc
    partido["probabilidad_sorpresa"] = sorpresa
    partido["probabilidad_top"] = max(probs.values())
    partido["margen_probabilidad"] = margen(probs)
    partido["tercera_probabilidad"] = tercera_prob(probs)
    partido["indice_sorpresa_quinielistica"] = indice
    partido["categoria_sorpresa"] = "partido_muy_abierto" if indice >= 75 else "sorpresa_vigilada" if indice >= 50 else "riesgo_controlado"
    partido["favorito"] = top if top in {"1", "2"} else None
    partido["favorito_nombre"] = partido.get("local") if top == "1" else partido.get("visitante") if top == "2" else "Empate"
    partido["favorito_atacable"] = bool(top in {"1", "2"} and indice >= 60)
    partido["signo_sorpresa_principal"] = signos_ordenados[1] if len(signos_ordenados) > 1 else ""
    partido["signos_contra_favorito"] = [s for s in signos_ordenados if s != top][:2]
    partido["cobertura_sorpresa_sugerida"] = cobertura
    partido["motivos_sorpresa"] = [
        "historial del Mundial 2026 incorporado",
        f"muestra minima {muestra_minima} partido(s)",
        f"margen {partido['margen_probabilidad']} puntos",
    ]
    partido["origen_probabilidades"] = "mundial_2026_resultados_y_modelo_base"
    partido["calidad_datos"] = calidad
    partido.setdefault("trazabilidad_datos", {})["origen_probabilidades"] = partido["origen_probabilidades"]
    partido["trazabilidad_datos"]["calidad_datos"] = calidad
    partido["trazabilidad_datos"]["memoria_estadistica"] = {"local": True, "visitante": True, "fuente": "mundial_2026"}
    partido["memoria_mundial_2026"] = {
        "aplicado": True,
        "calidad": calidad,
        "muestra_minima": muestra_minima,
        "peso_aplicado": peso,
        "diff_mundial": diff,
        "local": resumen_equipo(local),
        "visitante": resumen_equipo(visitante),
    }
    return partido


def aplicar_a_prediccion(data, memoria):
    equipos = memoria.get("equipos") or {}
    partidos = []
    aplicados = 0
    pendientes = 0
    for partido in data.get("partidos", []):
        antes = partido.get("origen_probabilidades")
        nuevo = aplicar_mundial_a_partido(dict(partido), equipos)
        if nuevo.get("origen_probabilidades") == "mundial_2026_resultados_y_modelo_base" and antes != nuevo.get("origen_probabilidades"):
            aplicados += 1
        if not nuevo.get("memoria_mundial_2026", {}).get("aplicado") and int(nuevo.get("num") or 0) <= 13:
            pendientes += 1
        partidos.append(nuevo)
    data["partidos"] = partidos
    data["memoria_mundial_2026"] = {
        "aplicada": aplicados,
        "pendientes_sin_historial_completo": pendientes,
        "total_equipos_memoria": memoria.get("total_equipos", 0),
        "generado_en": memoria.get("generado_en"),
        "criterio_critico": "Los porcentajes de selecciones solo se consideran estudiados si memoria_mundial_2026.aplicado es true.",
    }
    return data


def aplicar_archivo(path, memoria):
    data = cargar_json(path, {})
    if not data:
        return False
    antes = json.dumps(data, ensure_ascii=False, sort_keys=True)
    data = aplicar_a_prediccion(data, memoria)
    despues = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if antes == despues:
        return False
    guardar_json(path, data)
    return True


def main():
    memoria = cargar_json(MEMORIA_MUNDIAL, {"equipos": {}})
    if not memoria.get("equipos"):
        print("No hay memoria del Mundial 2026; se conserva la prediccion base.")
        return
    ultima = PREDICCIONES / "ultima_prediccion.json"
    cambios = []
    if aplicar_archivo(ultima, memoria):
        cambios.append(str(ultima))
    data = cargar_json(ultima, {})
    jornada = data.get("jornada")
    if jornada:
        path_jornada = PREDICCIONES / f"jornada_{jornada}.json"
        guardar_json(path_jornada, data)
        cambios.append(str(path_jornada))
    print("Memoria Mundial 2026 aplicada: " + (", ".join(cambios) if cambios else "sin cambios"))


if __name__ == "__main__":
    main()
