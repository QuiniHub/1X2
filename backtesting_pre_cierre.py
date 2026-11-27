import json
from datetime import datetime, timezone
from pathlib import Path

import cronologia_jornadas as cj
from guardar_snapshot_prediccion import snapshot_de_otra_jornada


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SNAPSHOTS = DATA / "backtesting" / "pre_cierre"
JORNADAS = DATA / "jornadas"
OUT = DATA / "backtesting" / "resumen_pre_cierre.json"


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def signo_valido(valor):
    valor = str(valor or "").strip().upper()
    return valor if valor in {"1", "X", "2"} else ""


def indice_resultados(jornada):
    salida = {}
    for partido in jornada.get("partidos", []):
        try:
            num = int(partido.get("num"))
        except Exception:
            continue
        if num <= 14:
            salida[num] = signo_valido(partido.get("signo_oficial"))
    return salida


def comparar_snapshot(path):
    snapshot = cargar_json(path, {})
    prediccion = snapshot.get("prediccion") or {}
    jornada_num = int(snapshot.get("jornada") or prediccion.get("jornada") or 0)
    jornada = cargar_json(JORNADAS / f"jornada_{jornada_num}.json", {})
    # Auditoria 26/11: el NUMERO no identifica la jornada (se reinicia cada
    # temporada). Un snapshot que no es de los mismos partidos que el
    # jornada_N.json actual no se puntua contra el.
    fecha, temporada = fecha_y_temporada(jornada, jornada_num, snapshot)
    if snapshot_de_otra_jornada(snapshot, jornada):
        return {
            "jornada": jornada_num,
            "temporada": temporada_del_snapshot(snapshot, jornada_num),
            "fecha": None,
            "snapshot": str(path.relative_to(ROOT)).replace("\\", "/"),
            "creado_en": snapshot.get("creado_en"),
            "prediccion_generada_en": prediccion.get("generado_en"),
            "estado": "snapshot_de_otra_jornada",
            "partidos_cerrados": 0,
            "aciertos": 0,
            "precision": None,
            "configuracion": prediccion.get("configuracion", {}),
            "coste": prediccion.get("coste", {}),
            "por_tipo": {},
            "partidos": [],
        }
    resultados = indice_resultados(jornada)
    partidos = []
    resumen_tipo = {
        "FIJO": {"total": 0, "aciertos": 0},
        "DOBLE": {"total": 0, "aciertos": 0},
        "TRIPLE": {"total": 0, "aciertos": 0},
    }

    for partido in prediccion.get("partidos", []):
        num = int(partido.get("num", 0) or 0)
        oficial = resultados.get(num, "")
        if not oficial:
            continue
        jugado = str(partido.get("signo_final") or partido.get("signo_base") or "")
        tipo = str(partido.get("tipo") or ("TRIPLE" if len(jugado) >= 3 else "DOBLE" if len(jugado) == 2 else "FIJO"))
        acierto = oficial in jugado
        if tipo not in resumen_tipo:
            resumen_tipo[tipo] = {"total": 0, "aciertos": 0}
        resumen_tipo[tipo]["total"] += 1
        resumen_tipo[tipo]["aciertos"] += 1 if acierto else 0
        partidos.append({
            "num": num,
            "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
            "jugado": jugado,
            "tipo": tipo,
            "oficial": oficial,
            "acierto": acierto,
            "probabilidades": partido.get("probabilidades", {}),
            "incertidumbre": partido.get("incertidumbre"),
            "probabilidad_sorpresa": partido.get("probabilidad_sorpresa"),
        })

    aciertos = sum(1 for p in partidos if p["acierto"])
    cerrados = len(partidos)
    return {
        "jornada": jornada_num,
        "temporada": temporada,
        "fecha": fecha.isoformat() if fecha else None,
        "snapshot": str(path.relative_to(ROOT)).replace("\\", "/"),
        "creado_en": snapshot.get("creado_en"),
        "prediccion_generada_en": prediccion.get("generado_en"),
        "estado": "cerrada_o_parcial" if cerrados else "pendiente_resultados",
        "partidos_cerrados": cerrados,
        "aciertos": aciertos,
        "precision": round(aciertos / cerrados * 100, 2) if cerrados else None,
        "configuracion": prediccion.get("configuracion", {}),
        "coste": prediccion.get("coste", {}),
        "por_tipo": resumen_tipo,
        "partidos": partidos,
    }


def fecha_y_temporada(jornada, jornada_num, snapshot=None):
    """(fecha real, 'YYYY_YYYY') de la jornada; la temporada sale de la FECHA."""
    fecha = cj.fecha_real_jornada(jornada)
    if fecha is None and snapshot:
        fecha = cj.parsear_fecha(snapshot.get("primer_partido_utc"))
    return fecha, (cj.temporada_de_fecha(fecha, jornada_num) if fecha else None)


def temporada_del_snapshot(snapshot, jornada_num):
    fecha = cj.parsear_fecha(snapshot.get("primer_partido_utc")) or cj.parsear_fecha(snapshot.get("creado_en"))
    return snapshot.get("temporada") or (cj.temporada_de_fecha(fecha, jornada_num) if fecha else None)


def resumir(jornadas):
    validas = [j for j in jornadas if j.get("estado") != "snapshot_de_otra_jornada"]
    cerrados = sum(j["partidos_cerrados"] for j in validas)
    aciertos = sum(j["aciertos"] for j in validas)
    return {
        "jornadas_snapshot": len(validas),
        "partidos_cerrados": cerrados,
        "aciertos": aciertos,
        "precision": round(aciertos / cerrados * 100, 2) if cerrados else None,
    }


def construir_salida(jornadas):
    """Resumen global (todas las temporadas, como siempre) y, ademas, por
    temporada. Las jornadas van en orden CRONOLOGICO, no por numero: la J76
    de la 25/26 es anterior a la J1 de la 26/27."""
    jornadas = sorted(jornadas, key=lambda j: (j.get("fecha") is None, j.get("fecha") or "", j["jornada"]))
    por_temporada = {}
    for j in jornadas:
        if j.get("estado") == "snapshot_de_otra_jornada":
            continue
        por_temporada.setdefault(j.get("temporada") or "desconocida", []).append(j)
    resumen = resumir(jornadas)
    descartados = [j["jornada"] for j in jornadas if j.get("estado") == "snapshot_de_otra_jornada"]
    if descartados:
        resumen["snapshots_de_otra_jornada"] = descartados
    return {
        "version": "1.1",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": "Backtesting solo con snapshots guardados antes de que hubiera resultados oficiales.",
        "resumen": resumen,
        "resumen_por_temporada": {t: resumir(js) for t, js in sorted(por_temporada.items())},
        "jornadas": jornadas,
    }


def main():
    jornadas = []
    if SNAPSHOTS.exists():
        for path in sorted(SNAPSHOTS.glob("jornada_*.json")):
            jornadas.append(comparar_snapshot(path))

    salida = construir_salida(jornadas)
    guardar_json(OUT, salida)
    print(OUT)


if __name__ == "__main__":
    main()
