import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
JORNADAS = DATA / "jornadas"
BACKTEST = DATA / "backtesting" / "pre_cierre"


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def signo_cerrado(valor):
    return str(valor or "").strip().upper() in {"1", "X", "2"}


def resumen_jornada(jornada):
    partidos = [p for p in jornada.get("partidos", []) if int(p.get("num", 0) or 0) <= 14]
    cerrados = sum(1 for p in partidos if signo_cerrado(p.get("signo_oficial")))
    pendientes = len(partidos) - cerrados
    return {
        "jornada": jornada.get("jornada"),
        "fecha": jornada.get("fecha") or jornada.get("fecha_texto"),
        "partidos": len(partidos),
        "cerrados": cerrados,
        "pendientes": pendientes,
        "estado": jornada.get("estado"),
    }


def main():
    prediccion = cargar_json(PREDICCIONES / "ultima_prediccion.json", {})
    jornada_num = prediccion.get("jornada")
    if not jornada_num:
        raise SystemExit("No hay ultima_prediccion con jornada.")

    jornada = cargar_json(JORNADAS / f"jornada_{jornada_num}.json", {})
    resumen = resumen_jornada(jornada)
    if resumen["cerrados"] > 0:
        print(f"No se crea snapshot pre-cierre: jornada {jornada_num} ya tiene resultados.")
        return

    destino = BACKTEST / f"jornada_{jornada_num}.json"
    if destino.exists():
        print(f"Snapshot pre-cierre ya existe: {destino}")
        return

    snapshot = {
        "version": "1.0",
        "tipo": "prediccion_pre_cierre",
        "creado_en": datetime.now(timezone.utc).isoformat(),
        "jornada": jornada_num,
        "resumen_jornada_al_crear": resumen,
        "prediccion": prediccion,
    }
    guardar_json(destino, snapshot)
    print(destino)


if __name__ == "__main__":
    main()
