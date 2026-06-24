import json
from pathlib import Path

from generar_memoria_mundial_2026 import normalizar_nombre

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
MEMORIA_MUNDIAL = DATA / "memoria_ia" / "mundial_2026_forma.json"
CLASIFICACIONES_MUNDIAL = DATA / "memoria_ia" / "clasificaciones_mundial_2026.json"


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


def incertidumbre(probs, muestra_minima, riesgo_extra=0.0):
    valores = sorted([float(v) for v in probs.values()], reverse=True)
    if len(valores) < 2:
        return 160.0
    penalizacion_muestra = 22 if muestra_minima <= 1 else 10 if muestra_minima == 2 else 0
    return round(100 - (valores[0] - valores[1]) + float(probs.get("X", 0)) * 0.35 + penalizacion_muestra + riesgo_extra, 2)


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


def buscar_clasificacion(clasificaciones, nombre):
    equipos = (clasificaciones or {}).get("equipos") or {}
    clave = normalizar_nombre(nombre)
    if clave in equipos:
        return equipos[clave]
    piezas = set(clave.split())
    mejor = None
    mejor_score = 0
    for key, datos in equipos.items():
        candidato = set(str(key).split())
        score = len(piezas & candidato)
        if clave and (clave in key or key in clave):
            score += 3
        if score > mejor_score:
            mejor = datos
            mejor_score = score
    return mejor if mejor_score >= 1 else None


def factor_motivacion_clasificacion(datos):
    situacion = str((datos or {}).get("situacion") or "").lower()
    if situacion == "necesita_ganar":
        return 3.0
    if situacion == "le_vale_empate":
        return 1.8
    if situacion == "depende_de_otros_resultados":
        return 1.4
    if situacion == "ya_clasificada":
        return -1.2
    if situacion == "eliminada":
        return -1.8
    return 0.0


def resumen_clasificacion(datos):
    if not datos:
        return {}
    return {
        "equipo": datos.get("equipo"),
        "grupo": datos.get("grupo"),
        "posicion": datos.get("posicion"),
        "pts": datos.get("pts"),
        "pj": datos.get("pj"),
        "dg": datos.get("dg"),
        "situacion": datos.get("situacion"),
        "necesidad_resultado": datos.get("necesidad_resultado"),
        "motivacion_competitiva": datos.get("motivacion_competitiva"),
        "rotacion_probable": datos.get("rotacion_probable"),
        "lectura": datos.get("lectura"),
    }


def ajustar_por_clasificacion_mundial(probs, local_cls, visitante_cls):
    if not local_cls and not visitante_cls:
        return probs, 0.0, []
    p = dict(probs)
    lecturas = []
    fl = factor_motivacion_clasificacion(local_cls)
    fv = factor_motivacion_clasificacion(visitante_cls)
    diff = fl - fv
    if diff:
        ajuste = clamp(diff * 2.2, -8.0, 8.0)
        p["1"] += ajuste
        p["2"] -= ajuste
        lecturas.append(
            "Clasificacion Mundial 2026: la motivacion de grupo ajusta el 1X2 "
            f"({(local_cls or {}).get('situacion', 'sin_dato')} vs {(visitante_cls or {}).get('situacion', 'sin_dato')})."
        )
    if (local_cls or {}).get("situacion") == "le_vale_empate" or (visitante_cls or {}).get("situacion") == "le_vale_empate":
        p["X"] += 2.3
        lecturas.append("Clasificacion Mundial 2026: a una seleccion le vale empate, sube la X como resultado tactico.")
    if (local_cls or {}).get("rotacion_probable") and not (visitante_cls or {}).get("rotacion_probable"):
        p["1"] -= 2.2
        p["X"] += 0.9
        p["2"] += 1.3
        lecturas.append("Clasificacion Mundial 2026: posible rotacion del local por objetivo cerrado.")
    if (visitante_cls or {}).get("rotacion_probable") and not (local_cls or {}).get("rotacion_probable"):
        p["2"] -= 2.2
        p["X"] += 0.9
        p["1"] += 1.3
        lecturas.append("Clasificacion Mundial 2026: posible rotacion del visitante por objetivo cerrado.")
    riesgo = min(abs(diff) * 3.0 + len(lecturas) * 1.5, 18.0)
    return normalizar_probs(p), round(riesgo, 2), lecturas


def aplicar_mundial_a_partido(partido, equipos, clasificaciones=None):
    local = equipos.get(normalizar_nombre(partido.get("local")))
    visitante = equipos.get(normalizar_nombre(partido.get("visitante")))
    local_cls = buscar_clasificacion(clasificaciones, partido.get("local"))
    visitante_cls = buscar_clasificacion(clasificaciones, partido.get("visitante"))
    if not local or not visitante:
        partido.setdefault("diagnostico_calidad", {})["mundial_2026"] = {
            "aplicado": False,
            "motivo": "No hay historial del Mundial 2026 para ambos equipos.",
            "local_en_memoria": bool(local),
            "visitante_en_memoria": bool(visitante),
            "local_en_clasificacion": bool(local_cls),
            "visitante_en_clasificacion": bool(visitante_cls),
        }
        if partido.get("origen_probabilidades", "").startswith("fallback"):
            partido["calidad_datos"] = "baja"
        return partido

    base = partido.get("probabilidades") or {"1": 33.3, "X": 33.3, "2": 33.3}
    mundial_probs, diff = modelo_mundial(local, visitante)
    calidad, muestra_minima = calidad_muestra(local, visitante)
    peso = 0.72 if muestra_minima == 1 else 0.82 if muestra_minima == 2 else 0.90
    probs = mezclar_probs(base, mundial_probs, peso)
    probs, riesgo_clasificacion, lecturas_clasificacion = ajustar_por_clasificacion_mundial(probs, local_cls, visitante_cls)
    inc = incertidumbre(probs, muestra_minima, riesgo_clasificacion)
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
    ] + lecturas_clasificacion[:3]
    partido["origen_probabilidades"] = "mundial_2026_resultados_y_modelo_base"
    partido["calidad_datos"] = calidad
    partido.setdefault("trazabilidad_datos", {})["origen_probabilidades"] = partido["origen_probabilidades"]
    partido["trazabilidad_datos"]["calidad_datos"] = calidad
    partido["trazabilidad_datos"]["memoria_estadistica"] = {"local": True, "visitante": True, "fuente": "mundial_2026"}
    partido["trazabilidad_datos"]["clasificacion_mundial_2026"] = {
        "local": bool(local_cls),
        "visitante": bool(visitante_cls),
        "riesgo_extra": riesgo_clasificacion,
    }
    lecturas_previas = partido.get("lecturas_motivacion") or []
    partido["lecturas_motivacion"] = lecturas_previas + lecturas_clasificacion
    partido["ajuste_clasificacion_mundial_2026"] = {
        "activo": bool(lecturas_clasificacion),
        "riesgo_extra": riesgo_clasificacion,
        "lecturas": lecturas_clasificacion,
        "local": resumen_clasificacion(local_cls),
        "visitante": resumen_clasificacion(visitante_cls),
    }
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


def aplicar_a_prediccion(data, memoria, clasificaciones=None):
    equipos = memoria.get("equipos") or {}
    partidos = []
    aplicados = 0
    pendientes = 0
    clasificacion_aplicada = 0
    for partido in data.get("partidos", []):
        antes = partido.get("origen_probabilidades")
        nuevo = aplicar_mundial_a_partido(dict(partido), equipos, clasificaciones=clasificaciones)
        if nuevo.get("origen_probabilidades") == "mundial_2026_resultados_y_modelo_base" and antes != nuevo.get("origen_probabilidades"):
            aplicados += 1
        if nuevo.get("ajuste_clasificacion_mundial_2026", {}).get("activo"):
            clasificacion_aplicada += 1
        if not nuevo.get("memoria_mundial_2026", {}).get("aplicado") and int(nuevo.get("num") or 0) <= 13:
            pendientes += 1
        partidos.append(nuevo)
    data["partidos"] = partidos
    data["memoria_mundial_2026"] = {
        "aplicada": aplicados,
        "pendientes_sin_historial_completo": pendientes,
        "total_equipos_memoria": memoria.get("total_equipos", 0),
        "clasificacion_mundial_aplicada": clasificacion_aplicada,
        "total_equipos_clasificacion": (clasificaciones or {}).get("total_equipos", 0),
        "generado_en": memoria.get("generado_en"),
        "clasificaciones_generado_en": (clasificaciones or {}).get("generado_en"),
        "criterio_critico": "Los porcentajes de selecciones solo se consideran estudiados si memoria_mundial_2026.aplicado es true.",
    }
    return data


def aplicar_archivo(path, memoria, clasificaciones=None):
    data = cargar_json(path, {})
    if not data:
        return False
    antes = json.dumps(data, ensure_ascii=False, sort_keys=True)
    data = aplicar_a_prediccion(data, memoria, clasificaciones=clasificaciones)
    despues = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if antes == despues:
        return False
    guardar_json(path, data)
    return True


def aplicar_clasificacion_mundial_en_archivos():
    memoria = cargar_json(MEMORIA_MUNDIAL, {"equipos": {}})
    clasificaciones = cargar_json(CLASIFICACIONES_MUNDIAL, {"equipos": {}})
    if not memoria.get("equipos"):
        print("No hay memoria del Mundial 2026; se conserva la prediccion base.")
        return []
    ultima = PREDICCIONES / "ultima_prediccion.json"
    cambios = []
    if aplicar_archivo(ultima, memoria, clasificaciones=clasificaciones):
        cambios.append(str(ultima))
    data = cargar_json(ultima, {})
    jornada = data.get("jornada")
    if jornada:
        path_jornada = PREDICCIONES / f"jornada_{jornada}.json"
        guardar_json(path_jornada, data)
        cambios.append(str(path_jornada))
    return cambios


def main():
    cambios = aplicar_clasificacion_mundial_en_archivos()
    print("Memoria Mundial 2026 aplicada: " + (", ".join(cambios) if cambios else "sin cambios"))


if __name__ == "__main__":
    main()
