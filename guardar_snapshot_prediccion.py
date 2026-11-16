import json
import hashlib
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


def hash_json(data):
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


def primer_inicio_jornada(jornada):
    """Fecha-hora UTC del primer partido de la jornada (hora local de Madrid
    en el JSON). Sin hora, se asume 00:00 del dia; sin fechas, None."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Europe/Madrid")
    except Exception:  # pragma: no cover
        tz = timezone.utc
    inicios = []
    for p in jornada.get("partidos", []):
        fecha = str(p.get("fecha") or "")[:10]
        if not fecha or not fecha[:4].isdigit():
            continue
        hora = str(p.get("hora") or "00:00")[:5]
        try:
            inicio = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        except ValueError:
            inicio = datetime.strptime(fecha, "%Y-%m-%d").replace(tzinfo=tz)
        inicios.append(inicio.astimezone(timezone.utc))
    return min(inicios) if inicios else None


def ahora_utc():
    return datetime.now(timezone.utc)


def crear_snapshot_prediccion(prediccion=None, sobrescribir=False):
    prediccion = prediccion or cargar_json(PREDICCIONES / "ultima_prediccion.json", {})
    jornada_num = prediccion.get("jornada")
    if not jornada_num:
        return {"creado": False, "motivo": "No hay ultima_prediccion con jornada."}
    if prediccion.get("prediccion_disponible") is False:
        return {"creado": False, "motivo": "Prediccion bloqueada: no se guarda snapshot predictivo."}

    jornada = cargar_json(JORNADAS / f"jornada_{jornada_num}.json", {})
    resumen = resumen_jornada(jornada)
    if resumen["cerrados"] > 0:
        return {"creado": False, "motivo": f"No se crea snapshot pre-cierre: jornada {jornada_num} ya tiene resultados."}

    destino = BACKTEST / f"jornada_{jornada_num}.json"
    inicio = primer_inicio_jornada(jornada)
    ahora = ahora_utc()
    # Auditoria 16/11/2026: el snapshot se congelaba en la PRIMERA generacion
    # (J21: foto del 8/11 con el mercado Losilla aun de la J20, 9/14) y los
    # backtests "pre-cierre" evaluaban eso en vez de lo que se podia jugar al
    # cierre (10/14). Ahora se refresca en cada ciclo hasta el primer partido;
    # desde entonces es inmutable.
    abierto = inicio is not None and ahora < inicio
    if destino.exists() and not sobrescribir:
        previo = cargar_json(destino, {})
        if not abierto:
            if previo.get("inmutable") is False:
                previo["inmutable"] = True
                previo["congelado_en"] = ahora.isoformat()
                guardar_json(destino, previo)
            return {"creado": False, "motivo": f"Snapshot pre-cierre congelado (jornada en juego o jugada): {destino}", "ruta": str(destino)}
        if previo.get("prediccion_hash") == hash_json(prediccion):
            return {"creado": False, "motivo": "Snapshot pre-cierre sin cambios.", "ruta": str(destino)}
        creado_en = previo.get("creado_en")
    else:
        creado_en = None

    snapshot = {
        "version": "1.2",
        "tipo": "prediccion_pre_cierre",
        "inmutable": not abierto,
        "creado_en": creado_en or ahora.isoformat(),
        "refrescado_en": ahora.isoformat(),
        "primer_partido_utc": inicio.isoformat() if inicio else None,
        "jornada": jornada_num,
        "prediccion_hash": hash_json(prediccion),
        "resumen_jornada_al_crear": resumen,
        "prediccion": prediccion,
    }
    guardar_json(destino, snapshot)
    return {"creado": True, "ruta": str(destino), "prediccion_hash": snapshot["prediccion_hash"], "inmutable": snapshot["inmutable"]}


def main():
    resultado = crear_snapshot_prediccion()
    print(resultado.get("ruta") or resultado.get("motivo"))


if __name__ == "__main__":
    main()
