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
