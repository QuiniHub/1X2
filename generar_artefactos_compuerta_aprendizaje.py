import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORIA = DATA / "memoria_ia"
APRENDIZAJE = DATA / "aprendizaje_ia.json"
REVISIONES = MEMORIA / "revisiones_prediccion_resultado.json"
METRICAS = MEMORIA / "metricas_probabilisticas.json"
FIABILIDAD = MEMORIA / "fiabilidad_equipos.json"
SIGNOS = ("1", "X", "2")


def ahora_iso():
    return datetime.now(timezone.utc).isoformat()


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def jornada_num(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def separar_partido(texto):
    partes = str(texto or "").split(" - ", 1)
    if len(partes) == 2:
        return partes[0].strip(), partes[1].strip()
    return str(texto or "").strip(), ""


def agrupar_por_jornada(detalle):
    jornadas = defaultdict(list)
    for item in detalle:
        jornada = jornada_num(item.get("jornada"))
        if jornada:
            jornadas[jornada].append(item)
    return jornadas


def construir_revisiones(aprendizaje, generado_en):
    jornadas = agrupar_por_jornada(aprendizaje.get("detalle") or [])
    revisiones = []
    for jornada in sorted(jornadas):
        for num, item in enumerate(jornadas[jornada], start=1):
            revisiones.append({
                "jornada": jornada,
                "num": item.get("num") or num,
                "partido": item.get("partido", ""),
                "pronostico": item.get("pronostico", ""),
                "tipo_pronostico": item.get("tipo_pronostico", ""),
                "resultado": item.get("resultado_final") or item.get("resultado"),
                "signo_real": item.get("signo_real"),
                "signos_cubiertos": item.get("signos_cubiertos", ""),
                "acierto": bool(item.get("acierto")),
                "motivo_error": item.get("motivo_error", ""),
                "origen": item.get("origen", ""),
                "probabilidades_usadas": item.get("probabilidades_usadas") or {},
                "fuentes_utilizadas": item.get("fuentes_utilizadas") or [],
            })
    return {
        "version": "1.0",
        "generado_en": generado_en,
        "fuente": "data/aprendizaje_ia.json",
        "total_revisiones": len(revisiones),
        "jornadas": {
            str(jornada): {"revisiones": len(items), "completa_para_compuerta": len(items) >= 14}
            for jornada, items in sorted(jornadas.items())
        },
        "revisiones": revisiones,
    }


def rps_partido(probs, signo_real):
    """Ranked probability score de un partido (categorias ordenadas 1,X,2).

    Menor = mejor. Es la metrica estandar de la literatura (Constantinou &
    Fenton 2012; el Soccer Prediction Challenge se juzga con ella): castiga
    mas equivocarse "de lejos" (decir 1 y salir 2) que "de cerca" (decir 1 y
    salir X), cosa que la precision a secas no distingue. Devuelve None si
    faltan probabilidades o el signo real no es valido."""
    try:
        valores = [float(probs[s]) for s in SIGNOS]
    except (KeyError, TypeError, ValueError):
        return None
    total = sum(valores)
    if total <= 0 or str(signo_real).upper() not in SIGNOS:
        return None
    valores = [v / total for v in valores]
    real = str(signo_real).upper()
    acum_p = acum_o = suma = 0.0
    for s, p in zip(SIGNOS[:-1], valores[:-1]):
        acum_p += p
        acum_o += 1.0 if s == real else 0.0
        suma += (acum_p - acum_o) ** 2
    return suma / (len(SIGNOS) - 1)


def construir_bloque_rps_calibracion(revisiones_items):
    """RPS medio (global y por jornada) + calibracion por signo + calibracion
    del favorito por bandas. Solo con partidos que tengan probabilidades y
    signo real; los antiguos sin probabilidades quedan fuera y se cuenta
    cuantos son (transparencia, no silencio)."""
    evaluables = []
    sin_probs = 0
    for item in revisiones_items:
        r = rps_partido(item.get("probabilidades_usadas") or {}, item.get("signo_real"))
        if r is None:
            sin_probs += 1
            continue
        evaluables.append((item, r))
    if not evaluables:
        return {"partidos_con_probabilidades": 0, "sin_probabilidades": sin_probs}

    por_jornada = defaultdict(list)
    for item, r in evaluables:
        por_jornada[jornada_num(item.get("jornada"))].append(r)

    # calibracion por signo: cuanta probabilidad le damos de media a cada
    # signo vs cuantas veces sale de verdad (sesgo + = lo sobreestimamos)
    calibracion_signo = {}
    n = len(evaluables)
    for s in SIGNOS:
        prob_media = sum(
            float((item.get("probabilidades_usadas") or {}).get(s) or 0) for item, _ in evaluables
        ) / n
        frecuencia = 100.0 * sum(
            1 for item, _ in evaluables if str(item.get("signo_real")).upper() == s
        ) / n
        calibracion_signo[s] = {
            "prob_media_pronosticada": round(prob_media, 1),
            "frecuencia_real_pct": round(frecuencia, 1),
            "sesgo_puntos": round(prob_media - frecuencia, 1),
        }

    # calibracion del favorito por bandas: cuando decimos "el favorito tiene
    # 50-60%", ¿acierta de verdad el 50-60% de las veces?
    bandas = {}
    for item, _ in evaluables:
        probs = item.get("probabilidades_usadas") or {}
        favorito = max(SIGNOS, key=lambda s: float(probs.get(s) or 0))
        p_fav = float(probs.get(favorito) or 0)
        banda = f"{int(p_fav // 10) * 10}-{int(p_fav // 10) * 10 + 10}"
        registro = bandas.setdefault(banda, {"n": 0, "suma_prob": 0.0, "aciertos": 0})
        registro["n"] += 1
        registro["suma_prob"] += p_fav
        registro["aciertos"] += 1 if str(item.get("signo_real")).upper() == favorito else 0
    calibracion_favorito = {
        banda: {
            "n": v["n"],
            "prob_media": round(v["suma_prob"] / v["n"], 1),
            "acierto_real_pct": round(100.0 * v["aciertos"] / v["n"], 1),
        }
        for banda, v in sorted(bandas.items())
    }

    return {
        "nota": "RPS: menor = mejor; referencia mundial ~0,19-0,21 (mercado/estado del arte).",
        "partidos_con_probabilidades": n,
        "sin_probabilidades": sin_probs,
        "rps_medio_global": round(sum(r for _, r in evaluables) / n, 5),
        "rps_por_jornada": {
            str(j): round(sum(valores) / len(valores), 5)
            for j, valores in sorted(por_jornada.items())
        },
        "calibracion_por_signo": calibracion_signo,
        "calibracion_favorito": calibracion_favorito,
    }


def construir_metricas(aprendizaje, revisiones, generado_en):
    por_jornada = defaultdict(list)
    for item in revisiones.get("revisiones") or []:
        por_jornada[jornada_num(item.get("jornada"))].append(item)
    metricas_jornada = {}
    for jornada, items in sorted(por_jornada.items()):
        aciertos = sum(1 for item in items if item.get("acierto"))
        total = len(items)
        metricas_jornada[str(jornada)] = {
            "partidos_evaluados": total,
            "aciertos": aciertos,
            "fallos": max(total - aciertos, 0),
            "precision": round(aciertos / max(total, 1) * 100.0, 2),
            "completa_para_compuerta": total >= 14,
        }
    return {
        "version": "1.0",
        "generado_en": generado_en,
        "fuente": "data/aprendizaje_ia.json",
        "partidos_evaluados": int(aprendizaje.get("partidos_revisados") or revisiones.get("total_revisiones") or 0),
        "jornadas_evaluadas": int(aprendizaje.get("jornadas_revisadas") or len(metricas_jornada)),
        "precision": aprendizaje.get("precision"),
        "aciertos": aprendizaje.get("aciertos"),
        "fallos": aprendizaje.get("fallos"),
        "fallos_por_tipo": aprendizaje.get("fallos_por_tipo") or {},
        "fallos_por_signo_real": aprendizaje.get("fallos_por_signo_real") or {},
        "precision_por_tipo": aprendizaje.get("precision_por_tipo") or {},
        "precision_por_signo_real": aprendizaje.get("precision_por_signo_real") or {},
        "por_jornada": metricas_jornada,
        "rps_calibracion": construir_bloque_rps_calibracion(revisiones.get("revisiones") or []),
    }


def construir_fiabilidad(aprendizaje, revisiones, generado_en):
    equipos = defaultdict(lambda: {"partidos": 0, "aciertos": 0, "fallos": 0, "jornadas": set(), "roles": Counter(), "signos_reales": Counter()})
    for item in revisiones.get("revisiones") or []:
        jornada = jornada_num(item.get("jornada"))
        local, visitante = separar_partido(item.get("partido"))
        for nombre, rol in ((local, "local"), (visitante, "visitante")):
            if not nombre:
                continue
            equipos[nombre]["partidos"] += 1
            equipos[nombre]["aciertos"] += 1 if item.get("acierto") else 0
            equipos[nombre]["fallos"] += 0 if item.get("acierto") else 1
            equipos[nombre]["jornadas"].add(jornada)
            equipos[nombre]["roles"][rol] += 1
            if item.get("signo_real"):
                equipos[nombre]["signos_reales"][item["signo_real"]] += 1
    salida = {}
    for nombre, datos in sorted(equipos.items()):
        partidos = int(datos["partidos"])
        salida[nombre] = {
            "equipo": nombre,
            "partidos": partidos,
            "aciertos": int(datos["aciertos"]),
            "fallos": int(datos["fallos"]),
            "precision": round(float(datos["aciertos"]) / max(partidos, 1) * 100.0, 2),
            "jornadas": sorted(datos["jornadas"]),
            "roles": dict(datos["roles"]),
            "signos_reales": dict(datos["signos_reales"]),
        }
    return {
        "version": "1.0",
        "generado_en": generado_en,
        "fuente": "data/aprendizaje_ia.json",
        "equipos": salida,
        "resumen": {"equipos": len(salida), "partidos_revisados": aprendizaje.get("partidos_revisados", 0), "precision_global": aprendizaje.get("precision")},
    }


def generar_artefactos(aprendizaje=None):
    aprendizaje = aprendizaje or cargar_json(APRENDIZAJE, {})
    generado_en = ahora_iso()
    revisiones = construir_revisiones(aprendizaje, generado_en)
    metricas = construir_metricas(aprendizaje, revisiones, generado_en)
    fiabilidad = construir_fiabilidad(aprendizaje, revisiones, generado_en)
    guardar_json(REVISIONES, revisiones)
    guardar_json(METRICAS, metricas)
    guardar_json(FIABILIDAD, fiabilidad)
    return {"revisiones": revisiones.get("total_revisiones", 0), "partidos_evaluados": metricas.get("partidos_evaluados", 0), "equipos": len(fiabilidad.get("equipos") or {})}


def main():
    resultado = generar_artefactos()
    print(f"Artefactos de compuerta generados: {resultado['revisiones']} revisiones, {resultado['partidos_evaluados']} partidos evaluados, {resultado['equipos']} equipos.")


if __name__ == "__main__":
    main()
