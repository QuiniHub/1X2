import json
from datetime import datetime, timezone
from pathlib import Path


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


def main():
    jornadas = []
    if SNAPSHOTS.exists():
        for path in sorted(SNAPSHOTS.glob("jornada_*.json")):
            jornadas.append(comparar_snapshot(path))

    cerrados = sum(j["partidos_cerrados"] for j in jornadas)
    aciertos = sum(j["aciertos"] for j in jornadas)
    salida = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": "Backtesting solo con snapshots guardados antes de que hubiera resultados oficiales.",
        "resumen": {
            "jornadas_snapshot": len(jornadas),
            "partidos_cerrados": cerrados,
            "aciertos": aciertos,
            "precision": round(aciertos / cerrados * 100, 2) if cerrados else None,
        },
        "jornadas": jornadas,
    }
    guardar_json(OUT, salida)
    print(OUT)


if __name__ == "__main__":
    main()
