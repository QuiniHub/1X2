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


def snapshot_de_otra_jornada(snapshot, datos_jornada):
    """True solo si hay PRUEBA de que el snapshot es de otra jornada real.

    La numeracion de La Quiniela se reinicia cada temporada: el fichero
    jornada_22.json de la 27/28 no es la J22 de la 26/27 aunque se llame
    igual (auditoria 26/11). Se compara por equipos (cronologia_jornadas) y,
    si los nombres no bastan (otra fuente cambia todos los nombres en una
    jornada femenina), por la fecha del primer partido. Sin datos para
    comparar devuelve False: no se descarta nada a ciegas.

    datos_jornada puede ser data/jornadas/jornada_N.json o cualquier dict con
    'partidos' (otra prediccion de la misma jornada)."""
    import cronologia_jornadas as cj
    if not isinstance(snapshot, dict) or not isinstance(datos_jornada, dict):
        return False
    pred = snapshot.get("prediccion")
    if not isinstance(pred, dict):
        pred = snapshot
    coinciden, comparables = cj.coincidencia_equipos(pred, datos_jornada)
    if comparables >= cj.UMBRAL_PARTIDOS_IGUALES and coinciden * 2 >= comparables:
        return False
    primer = cj.parsear_fecha(snapshot.get("primer_partido_utc"))
    real = cj.fecha_real_jornada(datos_jornada)
    if primer is not None and real is not None:
        return abs((primer - real).days) > 2
    if comparables >= cj.UMBRAL_PARTIDOS_IGUALES:
        # Medido en el repo: dos jornadas reales distintas nunca comparten 3
        # partidos; la misma jornada con nombres de otra fuente comparte >= 5.
        return coinciden < 3
    return False


def temporada_de_jornada(jornada, jornada_num):
    """'2026_2027' segun la FECHA real de la jornada (nunca segun now())."""
    try:
        import cronologia_jornadas as cj
        fecha = cj.fecha_real_jornada(jornada)
        return cj.temporada_de_fecha(fecha, jornada_num) if fecha else None
    except Exception:
        return None


def marcar_inmutables_vencidos(ahora=None, dir_snapshots=None):
    """Marca inmutable=True todo snapshot cuyo primer partido ya paso.

    Auditoria 26/11: J23 y J24 se quedaron con inmutable=False para siempre
    porque la primera ejecucion tras el inicio ya veia resultados y salia
    antes de marcar, y despues la jornada activa ya era otra. Solo cambia la
    etiqueta (y congelado_en): la prediccion y su hash no se tocan. Devuelve
    la lista de jornadas marcadas."""
    ahora = ahora or ahora_utc()
    base = Path(dir_snapshots) if dir_snapshots else BACKTEST
    marcados = []
    if not base.exists():
        return marcados
    for ruta in sorted(base.glob("jornada_*.json")):
        try:
            snap = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(snap, dict) or snap.get("inmutable") is not False:
            continue
        try:
            inicio = datetime.fromisoformat(str(snap.get("primer_partido_utc")).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if inicio.tzinfo is None:
            inicio = inicio.replace(tzinfo=timezone.utc)
        if inicio <= ahora:
            snap["inmutable"] = True
            snap["congelado_en"] = ahora.isoformat()
            guardar_json(ruta, snap)
            marcados.append(snap.get("jornada"))
    return marcados


def crear_snapshot_prediccion(prediccion=None, sobrescribir=False):
    prediccion = prediccion or cargar_json(PREDICCIONES / "ultima_prediccion.json", {})
    jornada_num = prediccion.get("jornada")
    if not jornada_num:
        return {"creado": False, "motivo": "No hay ultima_prediccion con jornada."}
    if prediccion.get("prediccion_disponible") is False:
        return {"creado": False, "motivo": "Prediccion bloqueada: no se guarda snapshot predictivo."}

    jornada = cargar_json(JORNADAS / f"jornada_{jornada_num}.json", {})
    resumen = resumen_jornada(jornada)
    destino = BACKTEST / f"jornada_{jornada_num}.json"
    inicio = primer_inicio_jornada(jornada)
    ahora = ahora_utc()
    # Auditoria 16/11/2026: el snapshot se congelaba en la PRIMERA generacion
    # (J21: foto del 8/11 con el mercado Losilla aun de la J20, 9/14) y los
    # backtests "pre-cierre" evaluaban eso en vez de lo que se podia jugar al
    # cierre (10/14). Ahora se refresca en cada ciclo hasta el primer partido;
    # desde entonces es inmutable.
    abierto = inicio is not None and ahora < inicio

    # Auditoria 26/11 (a): el fichero que hay en disco puede ser la jornada
    # del mismo NUMERO de otra temporada. Si lo es, no vale ni para congelar
    # ni para heredar su creado_en: se trata como si no existiera.
    previo = cargar_json(destino, {}) if destino.exists() else {}
    previo_ajeno = bool(previo) and snapshot_de_otra_jornada(previo, prediccion)
    if previo_ajeno:
        previo = {}

    # Auditoria 26/11 (b): marcar inmutable ANTES del corte por resultados.
    # Con el cron cada 6-8 h la primera ejecucion tras el primer partido ya
    # suele ver algun signo oficial y la etiqueta no se ponia nunca (J23, J24).
    if previo and not abierto and not sobrescribir:
        if previo.get("inmutable") is False:
            previo["inmutable"] = True
            previo["congelado_en"] = ahora.isoformat()
            guardar_json(destino, previo)
        return {"creado": False, "motivo": f"Snapshot pre-cierre congelado (jornada en juego o jugada): {destino}", "ruta": str(destino)}

    if resumen["cerrados"] > 0:
        return {"creado": False, "motivo": f"No se crea snapshot pre-cierre: jornada {jornada_num} ya tiene resultados."}

    # Auditoria 26/11 (c): si no hay snapshot valido y el primer partido ya
    # empezo, una prediccion de AHORA no es "pre-cierre" (el motor puede estar
    # ya sin mercado): no se fabrica una foto a posteriori. Sin fechas en la
    # jornada (inicio None) tampoco: no se puede garantizar que sea
    # pre-cierre (segunda pasada de la auditoria). Cuando la jornada traiga
    # fechas y siga abierta, el snapshot se crea con normalidad.
    if not previo and not abierto and not sobrescribir:
        if inicio is None:
            motivo = (f"Sin snapshot pre-cierre de la jornada {jornada_num}: sin fechas no se puede "
                      "garantizar que sea pre-cierre y no se fabrica.")
        else:
            motivo = (f"Sin snapshot pre-cierre valido de la jornada {jornada_num}: el primer partido ya empezo "
                      "y no se fabrica uno a posteriori.")
        return {"creado": False, "motivo": motivo + (" El fichero existente es de otra temporada." if previo_ajeno else "")}

    if previo and not sobrescribir:
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
        "temporada": temporada_de_jornada(jornada, jornada_num),
        "prediccion_hash": hash_json(prediccion),
        "resumen_jornada_al_crear": resumen,
        "prediccion": prediccion,
    }
    guardar_json(destino, snapshot)
    return {"creado": True, "ruta": str(destino), "prediccion_hash": snapshot["prediccion_hash"], "inmutable": snapshot["inmutable"]}


def main():
    resultado = crear_snapshot_prediccion()
    print(resultado.get("ruta") or resultado.get("motivo"))
    marcados = marcar_inmutables_vencidos()
    if marcados:
        print("Snapshots marcados inmutables (primer partido ya jugado): "
              + ", ".join(f"J{j}" for j in marcados))


if __name__ == "__main__":
    main()
