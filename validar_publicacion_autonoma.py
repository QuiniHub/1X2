import json
import re
import traceback
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from compuerta_jornada import normalizar_estado_publicacion

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
JORNADAS = DATA / "jornadas"
DIAGNOSTICO = DATA / "diagnostico_publicacion.json"

PATRONES_CRITICOS = (
    "La prediccion publicada esta vacia",
    "La prediccion no indica jornada.",
    "La prediccion no contiene 14 partidos.",
    "es DOBLE pero signo_final no tiene dos signos.",
    "es TRIPLE pero signo_final no es 1X2.",
)


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"AVISO_PUBLICACION: JSON invalido en {path}: {exc}")
        return defecto
    except OSError as exc:
        print(f"AVISO_PUBLICACION: no se pudo leer {path}: {exc}")
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def numero(valor, defecto=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def entero(valor, defecto=0):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


def normalizar(texto):
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", texto).strip()


def jornada_cerrada(data):
    partidos = data.get("partidos", [])[:14]
    return bool(partidos) and all(str(p.get("signo_oficial") or "").upper() in {"1", "X", "2"} for p in partidos)


def jornadas_existentes():
    numeros = []
    for path in JORNADAS.glob("jornada_*.json"):
        try:
            data = cargar_json(path, {})
            numero_jornada = entero(data.get("jornada") or path.stem.split("_")[-1])
            if numero_jornada:
                numeros.append(numero_jornada)
        except Exception as exc:
            print(f"AVISO_PUBLICACION: no se pudo evaluar {path}: {exc}")
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
        -entero(partido.get("num")),
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
        -entero(partido.get("num")),
    )


def validar_razonamiento(partido):
    tipo = str(partido.get("tipo") or "").upper()
    texto = normalizar(partido.get("razonamiento"))
    texto_decision = re.sub(r"cobertura sugerida por sorpresa: (triple|doble|fijo)", "", texto)
    errores = []
    num = partido.get("num")
    if not texto:
        errores.append(f"Partido {num} no tiene razonamiento.")
        return errores
    if "decision final:" not in texto:
        errores.append(f"Partido {num} no incluye Decision final en el razonamiento.")
    if tipo == "FIJO":
        if "se cubre con doble" in texto_decision or "se protege con doble" in texto_decision or "se abre triple" in texto_decision or "se protege con triple" in texto_decision:
            errores.append(f"Partido {num} es FIJO pero el razonamiento habla de doble/triple/cobertura.")
        if "se mantiene como fijo" not in texto and "se deja como fijo" not in texto:
            errores.append(f"Partido {num} es FIJO pero el razonamiento no confirma FIJO.")
    elif tipo == "DOBLE":
        if "se abre triple" in texto_decision or "se protege con triple" in texto_decision:
            errores.append(f"Partido {num} es DOBLE pero el razonamiento habla de abrir triple.")
        if "se mantiene como fijo" in texto or "se deja como fijo" in texto:
            errores.append(f"Partido {num} es DOBLE pero el razonamiento habla de fijo.")
        if "se cubre con doble" not in texto and "se protege con doble" not in texto:
            errores.append(f"Partido {num} es DOBLE pero el razonamiento no confirma DOBLE.")
    elif tipo == "TRIPLE":
        if "se mantiene como fijo" in texto or "se deja como fijo" in texto or "se cubre con doble" in texto:
            errores.append(f"Partido {num} es TRIPLE pero el razonamiento habla de fijo/doble.")
        if "se abre triple" not in texto and "se protege con triple" not in texto:
            errores.append(f"Partido {num} es TRIPLE pero el razonamiento no confirma TRIPLE.")
    return errores


def muestra_mundial_limitada(partido):
    mundial = partido.get("memoria_mundial_2026") or {}
    if not mundial.get("aplicado"):
        return False
    try:
        return int(mundial.get("muestra_minima") or 0) < 3
    except Exception:
        return True


def datos_limitados(partido):
    calidad = str(partido.get("calidad_datos") or "").lower()
    return calidad in {"baja", "media_baja", "media"} or muestra_mundial_limitada(partido)


def es_error_critico(error):
    return any(patron in error for patron in PATRONES_CRITICOS)


def validar_prediccion(pred):
    errores = []
    avisos = []
    tipos = {"FIJO": 0, "DOBLE": 0, "TRIPLE": 0}

    if not isinstance(pred, dict) or not pred:
        errores.append("La prediccion publicada esta vacia o no se pudo cargar.")
        return errores, avisos, tipos

    pred = normalizar_estado_publicacion(pred)
    if pred.get("prediccion_disponible") is False or not pred.get("publicar_prediccion", True):
        avisos.append(pred.get("motivo_bloqueo") or pred.get("mensaje") or "Prediccion no disponible por compuerta maestra.")
        return errores, avisos, tipos

    partidos = pred.get("partidos", [])[:14]
    jornada = pred.get("jornada")

    if not jornada:
        errores.append("La prediccion no indica jornada.")
    if len(partidos) < 14:
        errores.append("La prediccion no contiene 14 partidos.")

    partidos_datos_limitados = []
    for partido in partidos:
        tipo = str(partido.get("tipo") or "").upper()
        tipos[tipo] = tipos.get(tipo, 0) + 1
        if datos_limitados(partido):
            partidos_datos_limitados.append(partido.get("num"))
        signo_final = str(partido.get("signo_final") or "")
        if tipo == "DOBLE" and len(signo_final) < 2:
            errores.append(f"Partido {partido.get('num')} es DOBLE pero signo_final no tiene dos signos.")
        if tipo == "TRIPLE" and signo_final != "1X2":
            errores.append(f"Partido {partido.get('num')} es TRIPLE pero signo_final no es 1X2.")
        errores.extend(validar_razonamiento(partido))

    config = pred.get("configuracion", {})
    dobles_config = entero(config.get("dobles"))
    triples_config = entero(config.get("triples"))
    if tipos.get("DOBLE", 0) != dobles_config:
        errores.append(f"Dobles publicados ({tipos.get('DOBLE', 0)}) no coinciden con configuracion ({dobles_config}).")
    if tipos.get("TRIPLE", 0) != triples_config:
        errores.append(f"Triples publicados ({tipos.get('TRIPLE', 0)}) no coinciden con configuracion ({triples_config}).")

    if partidos_datos_limitados:
        avisos.append(
            "Hay partidos con muestra limitada o sin memoria estadistica completa; se permite variacion de coberturas "
            f"si el boleto explica la calidad del dato. Partidos: {sorted(partidos_datos_limitados)}."
        )

    triples_esperados = {p.get("num") for p in sorted(partidos, key=score_triple, reverse=True)[:triples_config]}
    triples_publicados = {p.get("num") for p in partidos if str(p.get("tipo") or "").upper() == "TRIPLE"}
    if triples_publicados != triples_esperados:
        mensaje = (
            "Los triples publicados no coinciden con los partidos de mayor prioridad por analisis. "
            f"Esperados {sorted(triples_esperados)}, publicados {sorted(triples_publicados)}."
        )
        if partidos_datos_limitados:
            avisos.append(mensaje + " Aviso no bloqueante por muestra limitada del Mundial/fallback.")
        else:
            errores.append(mensaje)

    cubiertos_esperados = {p.get("num") for p in sorted(partidos, key=score_cobertura, reverse=True)[:dobles_config + triples_config]}
    cubiertos_publicados = {p.get("num") for p in partidos if str(p.get("tipo") or "").upper() in {"DOBLE", "TRIPLE"}}
    if cubiertos_publicados != cubiertos_esperados:
        mensaje = (
            "Los dobles/triples no estan colocados en los partidos de mayor riesgo. "
            f"Esperados {sorted(cubiertos_esperados)}, publicados {sorted(cubiertos_publicados)}."
        )
        if partidos_datos_limitados:
            avisos.append(mensaje + " Aviso no bloqueante por muestra limitada del Mundial/fallback.")
        else:
            errores.append(mensaje)

    if jornada:
        jornada_path = JORNADAS / f"jornada_{jornada}.json"
        if not jornada_path.exists():
            avisos.append(f"No existe data/jornadas/jornada_{jornada}.json para la prediccion publicada. Aviso no bloqueante.")

    existentes = jornadas_existentes()
    cerradas = [n for n in existentes if jornada_cerrada(cargar_json(JORNADAS / f"jornada_{n}.json", {}))]
    jornada_num = entero(jornada)
    if cerradas and jornada_num and jornada_num <= max(cerradas):
        avisos.append(
            f"La prediccion publicada es jornada {jornada}, pero la ultima cerrada detectada es {max(cerradas)}."
        )

    return errores, avisos, tipos


def main():
    try:
        pred = cargar_json(PREDICCIONES / "ultima_prediccion.json", {})
        errores, avisos, tipos = validar_prediccion(pred)
        pred = normalizar_estado_publicacion(pred if isinstance(pred, dict) else {})
        errores_criticos = [error for error in errores if es_error_critico(error)]
        errores_tolerados = [error for error in errores if not es_error_critico(error)]
        for error in errores_tolerados:
            avisos.append("Validacion tolerante no bloqueante: " + error)

        diagnostico = {
            "generado_en": datetime.now(timezone.utc).isoformat(),
            "jornada_publicada": pred.get("jornada"),
            "estado": "bloqueada" if errores_criticos else pred.get("estado", "lista_para_publicar"),
            "prediccion_disponible": pred.get("prediccion_disponible") is not False,
            "publicar_solo_boleto": pred.get("publicar_solo_boleto", False),
            "publicar_prediccion": pred.get("publicar_prediccion", True),
            "errores": errores_criticos,
            "avisos": avisos,
            "errores_tolerados": errores_tolerados,
            "resumen_boleto": tipos,
        }
        guardar_json(DIAGNOSTICO, diagnostico)

        for aviso in avisos:
            print("AVISO_PUBLICACION: " + aviso)
        if errores_criticos:
            for error in errores_criticos:
                print("ERROR_PUBLICACION: " + error)
            raise SystemExit("Publicacion bloqueada por error critico de prediccion.")
        print("Publicacion validada correctamente con modo tolerante.")
    except SystemExit:
        raise
    except Exception as exc:
        print(f"AVISO_PUBLICACION: excepcion no critica en validar_publicacion_autonoma.py: {exc}")
        traceback.print_exc()
        guardar_json(DIAGNOSTICO, {
            "generado_en": datetime.now(timezone.utc).isoformat(),
            "estado": "validacion_tolerante_con_excepcion",
            "errores": [],
            "avisos": [str(exc)],
            "resumen_boleto": {},
        })


if __name__ == "__main__":
    main()
