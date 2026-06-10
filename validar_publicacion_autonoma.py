import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
JORNADAS = DATA / "jornadas"
DIAGNOSTICO = DATA / "diagnostico_publicacion.json"


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def numero(valor, defecto=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def jornada_cerrada(data):
    partidos = data.get("partidos", [])[:14]
    return bool(partidos) and all(str(p.get("signo_oficial") or "").upper() in {"1", "X", "2"} for p in partidos)


def jornadas_existentes():
    numeros = []
    for path in JORNADAS.glob("jornada_*.json"):
        try:
            data = cargar_json(path, {})
            numero_jornada = int(data.get("jornada") or path.stem.split("_")[-1])
            numeros.append(numero_jornada)
        except Exception:
            continue
    return sorted(set(numeros))


def cobertura_sugerida(partido):
    return str(partido.get("cobertura_sorpresa_sugerida") or "FIJO").upper()


def score_triple(partido):
    sugerida = cobertura_sugerida(partido)
    return (
        100000 if sugerida == "TRIPLE" else 0,
        numero(partido.get("indice_sorpresa_quinielistica")),
        numero(partido.get("tercera_probabilidad")),
        numero(partido.get("probabilidad_sorpresa")),
        numero(partido.get("incertidumbre")),
        -numero(partido.get("margen_probabilidad"), 99),
        -int(partido.get("num") or 0),
    )


def score_cobertura(partido):
    sugerida = cobertura_sugerida(partido)
    return (
        100000 if sugerida in {"TRIPLE", "DOBLE"} else 0,
        numero(partido.get("indice_sorpresa_quinielistica")),
        numero(partido.get("probabilidad_sorpresa")),
        numero(partido.get("incertidumbre")),
        -numero(partido.get("margen_probabilidad"), 99),
        numero((partido.get("probabilidades") or {}).get("X")),
        -int(partido.get("num") or 0),
    )


def validar_prediccion(pred):
    errores = []
    avisos = []
    partidos = pred.get("partidos", [])[:14]
    jornada = pred.get("jornada")

    if not jornada:
        errores.append("La prediccion no indica jornada.")
    if len(partidos) < 14:
        errores.append("La prediccion no contiene 14 partidos.")

    tipos = {"FIJO": 0, "DOBLE": 0, "TRIPLE": 0}
    for partido in partidos:
        tipo = str(partido.get("tipo") or "").upper()
        tipos[tipo] = tipos.get(tipo, 0) + 1
        signo_final = str(partido.get("signo_final") or "")
        if tipo == "DOBLE" and len(signo_final) < 2:
            errores.append(f"Partido {partido.get('num')} es DOBLE pero signo_final no tiene dos signos.")
        if tipo == "TRIPLE" and signo_final != "1X2":
            errores.append(f"Partido {partido.get('num')} es TRIPLE pero signo_final no es 1X2.")

    config = pred.get("configuracion", {})
    dobles_config = int(config.get("dobles") or 0)
    triples_config = int(config.get("triples") or 0)
    if tipos.get("DOBLE", 0) != dobles_config:
        errores.append(f"Dobles publicados ({tipos.get('DOBLE', 0)}) no coinciden con configuracion ({dobles_config}).")
    if tipos.get("TRIPLE", 0) != triples_config:
        errores.append(f"Triples publicados ({tipos.get('TRIPLE', 0)}) no coinciden con configuracion ({triples_config}).")

    triples_esperados = {p.get("num") for p in sorted(partidos, key=score_triple, reverse=True)[:triples_config]}
    triples_publicados = {p.get("num") for p in partidos if str(p.get("tipo") or "").upper() == "TRIPLE"}
    if triples_publicados != triples_esperados:
        errores.append(
            "Los triples publicados no coinciden con los partidos de mayor prioridad por analisis. "
            f"Esperados {sorted(triples_esperados)}, publicados {sorted(triples_publicados)}."
        )

    cubiertos_esperados = {p.get("num") for p in sorted(partidos, key=score_cobertura, reverse=True)[:dobles_config + triples_config]}
    cubiertos_publicados = {p.get("num") for p in partidos if str(p.get("tipo") or "").upper() in {"DOBLE", "TRIPLE"}}
    if cubiertos_publicados != cubiertos_esperados:
        errores.append(
            "Los dobles/triples no estan colocados en los partidos de mayor riesgo. "
            f"Esperados {sorted(cubiertos_esperados)}, publicados {sorted(cubiertos_publicados)}."
        )

    if jornada:
        jornada_path = JORNADAS / f"jornada_{jornada}.json"
        if not jornada_path.exists():
            errores.append(f"No existe data/jornadas/jornada_{jornada}.json para la prediccion publicada.")

    existentes = jornadas_existentes()
    cerradas = [n for n in existentes if jornada_cerrada(cargar_json(JORNADAS / f"jornada_{n}.json", {}))]
    if cerradas and jornada and int(jornada) <= max(cerradas):
        avisos.append(
            f"La prediccion publicada es jornada {jornada}, pero la ultima cerrada detectada es {max(cerradas)}."
        )

    return errores, avisos, tipos


def main():
    pred = cargar_json(PREDICCIONES / "ultima_prediccion.json", {})
    errores, avisos, tipos = validar_prediccion(pred)
    diagnostico = {
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "jornada_publicada": pred.get("jornada"),
        "estado": "bloqueada" if errores else "lista",
        "errores": errores,
        "avisos": avisos,
        "resumen_boleto": tipos,
    }
    guardar_json(DIAGNOSTICO, diagnostico)
    if errores:
        for error in errores:
            print("ERROR_PUBLICACION: " + error)
        raise SystemExit("Publicacion bloqueada por incoherencias del boleto.")
    print("Publicacion validada correctamente.")


if __name__ == "__main__":
    main()
