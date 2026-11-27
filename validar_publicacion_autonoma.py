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
SNAPSHOTS = DATA / "backtesting" / "pre_cierre"
FALLOS_CRONICOS = DATA / "diagnostico_fallos_cronicos.json"
UMBRAL_FALLO_CRONICO = 3
PRECIO_APUESTA = 0.75
IMPORTE_MINIMO = 1.50
SIGNOS_VALIDOS = {"1", "X", "2"}
DIAS_MAX_JORNADA_EN_JUEGO = 10

PATRONES_CRITICOS = (
    "La prediccion publicada esta vacia",
    "La prediccion no indica jornada.",
    "La prediccion no contiene 14 partidos.",
    "es DOBLE pero signo_final no tiene dos signos.",
    "es TRIPLE pero signo_final no es 1X2.",
    # Auditoria 26/11/2026 (hallazgo 104): invariantes del boleto que solo se
    # probaban en tests ANTES del pipeline (sobre el ciclo anterior).
    "Los partidos no estan numerados del 1 al 14.",
    "tiene un signo_final invalido",
    "es FIJO pero signo_final no tiene un solo signo.",
    "coste.apuestas no cuadra con los signos del boleto",
    "coste.importe_quiniela no cuadra con las apuestas",
    # Auditoria 26/11/2026 (hallazgo 112): jornada en juego sin congelar.
    "esta en juego y la prediccion no esta congelada al cierre",
    "snapshot pre-cierre ilegible con la jornada en juego",
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


def _signo_ok(signo):
    return bool(signo) and set(signo) <= SIGNOS_VALIDOS and len(set(signo)) == len(signo)


def invariantes_boleto(pred):
    """Invariantes matematicos del boleto publicado.

    Devuelve (criticos, tolerados). Los criticos detienen la publicacion
    (boleto incoherente: no se puede jugar tal cual). Los tolerados salen
    como aviso: delatan que algun paso posterior al motor ha tocado el
    reparto, pero no impiden publicar (por ejemplo, una prediccion congelada
    con una foto del cierre anterior a este arreglo).
    """
    criticos, tolerados = [], []
    partidos = [p for p in (pred.get("partidos") or [])[:14] if isinstance(p, dict)]
    if not partidos:
        return criticos, tolerados

    nums = sorted(entero(p.get("num")) for p in partidos)
    if len(partidos) == 14 and nums != list(range(1, 15)):
        criticos.append("Los partidos no estan numerados del 1 al 14.")

    apuestas = 1
    signos_validos = True
    for partido in partidos:
        num = partido.get("num")
        tipo = str(partido.get("tipo") or "").upper()
        signo_final = str(partido.get("signo_final") or "").upper()
        if not _signo_ok(signo_final):
            criticos.append(f"Partido {num} tiene un signo_final invalido ('{signo_final}').")
            signos_validos = False
            continue
        apuestas *= len(signo_final)
        if tipo == "FIJO" and len(signo_final) != 1:
            criticos.append(f"Partido {num} es FIJO pero signo_final no tiene un solo signo.")
        signo_base = str(partido.get("signo_base") or "").upper()
        x_autor = (partido.get("x_de_autor") or {}).get("activo")
        if signo_base and signo_base not in signo_final and not (x_autor and signo_final == "X"):
            tolerados.append(
                f"Partido {num}: signo_base '{signo_base}' no esta cubierto por signo_final '{signo_final}'."
            )
        autor = partido.get("cobertura_autor") or {}
        if autor.get("activo"):
            if autor.get("cubierta") and tipo == "DOBLE" and "X" not in signo_final:
                tolerados.append(
                    f"Partido {num}: cobertura de autor marcada como cubierta pero el doble '{signo_final}' no lleva la X."
                )
            if autor.get("cubierta") and tipo == "FIJO":
                tolerados.append(
                    f"Partido {num}: cobertura de autor marcada como cubierta pero el partido es FIJO."
                )

    coste = pred.get("coste") or {}
    if coste and signos_validos and len(partidos) == 14:
        if entero(coste.get("apuestas"), -1) != apuestas:
            criticos.append(
                f"coste.apuestas no cuadra con los signos del boleto: dice {coste.get('apuestas')} y los signos dan {apuestas}."
            )
        else:
            esperado = round(max(apuestas * PRECIO_APUESTA, IMPORTE_MINIMO), 2)
            if abs(numero(coste.get("importe_quiniela"), -1) - esperado) > 0.01:
                criticos.append(
                    f"coste.importe_quiniela no cuadra con las apuestas: dice {coste.get('importe_quiniela')} y deberia ser {esperado}."
                )

    elegidos = [p for p in partidos if p.get("elige8") or p.get("en_elige8")]
    if elegidos and len(elegidos) != 8:
        tolerados.append(f"Elige 8 marca {len(elegidos)} partidos en vez de 8.")
    return criticos, tolerados


def _fecha_utc(valor):
    try:
        f = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return f if f.tzinfo else f.replace(tzinfo=timezone.utc)


def estado_congelacion(pred, ahora=None, dir_snapshots=None, dir_jornadas=None):
    """Dice si la jornada de la prediccion esta EN JUEGO y si esta congelada.

    Auditoria 26/11/2026 (hallazgo 112). Con la jornada empezada, el motor
    regenera la prediccion sin mercado y el unico paso que la devuelve a la
    foto del cierre es congelar_bloques_sombra.py. Si ese paso falla o el
    snapshot no se puede leer (cargar_json devuelve {} y responde
    'sin_snapshot' sin avisar), se publicaria la prediccion sin congelar.

    "En juego" = el snapshot pre-cierre es de ESTA jornada real (misma prueba
    de equipos/fecha que usa congelar_bloques_sombra, no solo el numero), su
    primer partido ya ha empezado hace como mucho DIAS_MAX_JORNADA_EN_JUEGO
    dias y la jornada no esta cerrada.
    Devuelve {en_juego, congelada, error?, aviso?}.
    """
    ahora = ahora or datetime.now(timezone.utc)
    dir_snapshots = Path(dir_snapshots or SNAPSHOTS)
    dir_jornadas = Path(dir_jornadas or JORNADAS)
    salida = {"en_juego": False, "congelada": False}
    if not isinstance(pred, dict):
        return salida
    jornada = pred.get("jornada")
    if not isinstance(jornada, int) or isinstance(jornada, bool):
        return salida
    marca = pred.get("prediccion_congelada_al_cierre") or {}
    salida["congelada"] = bool(isinstance(marca, dict) and marca.get("activa"))

    import cronologia_jornadas as cj

    datos_jornada = cj.cargar_jornada(jornada, dir_jornadas)
    if not datos_jornada or cj.jornada_cerrada(datos_jornada):
        return salida
    ruta = dir_snapshots / f"jornada_{jornada}.json"
    if not ruta.exists():
        return salida

    try:
        bruto = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        bruto = None
    legible = isinstance(bruto, dict) and isinstance(bruto.get("prediccion"), dict) and bool(bruto.get("prediccion"))
    if not legible:
        # Sin snapshot legible solo queda la fecha real del boleto oficial.
        inicio = cj.fecha_real_jornada(datos_jornada)
        hoy = ahora.date()
        if inicio and inicio <= hoy and (hoy - inicio).days <= DIAS_MAX_JORNADA_EN_JUEGO:
            salida["en_juego"] = True
            salida["error"] = (
                f"Jornada {jornada}: snapshot pre-cierre ilegible con la jornada en juego "
                f"({ruta.name}); no se puede garantizar la prediccion del cierre."
            )
        else:
            salida["aviso"] = f"Snapshot pre-cierre {ruta.name} ilegible (jornada sin empezar)."
        return salida

    # MISMA prueba de identidad que congelar_bloques_sombra.congelar (snapshot
    # contra la PREDICCION, con guardar_snapshot_prediccion.snapshot_de_otra_jornada):
    # si aqui se usara otro criterio, los dos pasos podrian discrepar y este
    # validador bloquearia todos los ciclos de una jornada que congelar, con
    # razon o sin ella, no ha marcado.
    snap = bruto
    try:
        from guardar_snapshot_prediccion import snapshot_de_otra_jornada
    except Exception:
        snapshot_de_otra_jornada = None
    if snap["prediccion"].get("jornada") != jornada or (
        snapshot_de_otra_jornada is not None and snapshot_de_otra_jornada(snap, pred)
    ):
        salida["aviso"] = (
            f"El snapshot pre-cierre {ruta.name} no es de la jornada {jornada} actual "
            "(otra temporada u otros partidos); no se usa para congelar."
        )
        return salida
    inicio = _fecha_utc(snap.get("primer_partido_utc"))
    if not inicio or inicio > ahora:
        return salida
    if (ahora - inicio).days > DIAS_MAX_JORNADA_EN_JUEGO:
        # Una jornada que no cierra (partido aplazado, resultado que no llega)
        # no puede dejar la web sin publicar indefinidamente.
        if not salida["congelada"]:
            salida["aviso"] = (
                f"La jornada {jornada} empezo hace mas de {DIAS_MAX_JORNADA_EN_JUEGO} dias, sigue sin cerrar "
                "y su prediccion no esta congelada al cierre; ya no se bloquea la publicacion."
            )
        return salida
    salida["en_juego"] = True
    if not salida["congelada"]:
        salida["error"] = (
            f"La jornada {jornada} esta en juego y la prediccion no esta congelada al cierre "
            f"(primer partido {snap.get('primer_partido_utc')}): no se publica."
        )
    return salida


def diferencias_espejo(pred, dir_predicciones=None):
    """Claves de primer nivel en que predicciones/jornada_N.json difiere de
    ultima_prediccion.json (hallazgo 111: deben ser el mismo documento)."""
    jornada = pred.get("jornada") if isinstance(pred, dict) else None
    if not jornada:
        return []
    ruta = Path(dir_predicciones or PREDICCIONES) / f"jornada_{jornada}.json"
    if not ruta.exists():
        return ["(no existe el espejo)"]
    espejo = cargar_json(ruta, {})
    if not isinstance(espejo, dict):
        return ["(espejo ilegible)"]
    return sorted(k for k in set(pred) | set(espejo) if pred.get(k) != espejo.get(k))


def fallos_cronicos(ruta=None):
    """Scripts no criticos que llevan >= 3 ciclos seguidos fallando
    (hallazgos 122 y 139: la alarma solo salia en el log de Actions)."""
    historial = cargar_json(Path(ruta or FALLOS_CRONICOS), {})
    salida = []
    if isinstance(historial, dict):
        for nombre, entrada in sorted(historial.items()):
            if isinstance(entrada, dict) and entero(entrada.get("fallos_consecutivos")) >= UMBRAL_FALLO_CRONICO:
                salida.append({
                    "script": nombre,
                    "fallos_consecutivos": entero(entrada.get("fallos_consecutivos")),
                    "ultimo_fallo": entrada.get("ultimo_fallo"),
                })
    return salida


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

    # Auditoria 26/11/2026 (hallazgos 1 y 30): aqui habia un TERCER criterio
    # de reparto (score_triple/score_cobertura, copia del que usaba
    # alinear_boleto_con_analisis) que comparaba el boleto con "los partidos
    # de mayor prioridad por analisis". El unico dueno del reparto es el
    # motor; lo que se valida ahora es que el boleto sea coherente consigo
    # mismo y con lo que el motor dejo trazado.
    criticos_boleto, tolerados_boleto = invariantes_boleto(pred)
    errores.extend(criticos_boleto)
    errores.extend(tolerados_boleto)

    congelacion = estado_congelacion(pred)
    if congelacion.get("error"):
        errores.append(congelacion["error"])
    elif congelacion.get("aviso"):
        avisos.append(congelacion["aviso"])

    if jornada:
        jornada_path = JORNADAS / f"jornada_{jornada}.json"
        if not jornada_path.exists():
            avisos.append(f"No existe data/jornadas/jornada_{jornada}.json para la prediccion publicada. Aviso no bloqueante.")

    # Comparacion CRONOLOGICA, no por numero: la numeracion se reinicia
    # cada temporada, asi que "jornada 4 <= max(76)" avisaba en falso cada
    # ciclo desde el arranque de la 26/27 (auditoria 01/09/2026, mismo
    # patron numero-vs-fecha que en control_calidad/diagnostico_sistema).
    def fecha_orden(data):
        fechas = sorted(
            str(p.get("fecha") or "")[:10]
            for p in data.get("partidos", [])
            if re.match(r"^\d{4}-\d{2}-\d{2}", str(p.get("fecha") or ""))
        )
        return fechas[-1] if fechas else ""

    existentes = jornadas_existentes()
    cerradas = []
    for n in existentes:
        data_j = cargar_json(JORNADAS / f"jornada_{n}.json", {})
        if jornada_cerrada(data_j):
            cerradas.append((fecha_orden(data_j), n))
    jornada_num = entero(jornada)
    fecha_publicada = fecha_orden(cargar_json(JORNADAS / f"jornada_{jornada_num}.json", {})) if jornada_num else ""
    if cerradas and fecha_publicada:
        fecha_ultima_cerrada, num_ultima_cerrada = max(cerradas)
        if fecha_publicada < fecha_ultima_cerrada:
            avisos.append(
                f"La prediccion publicada es jornada {jornada} ({fecha_publicada}), pero hay una jornada cerrada mas reciente: {num_ultima_cerrada} ({fecha_ultima_cerrada})."
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

        if isinstance(pred, dict) and pred.get("publicar_prediccion", True):
            distintas = diferencias_espejo(pred)
            if distintas:
                avisos.append(
                    f"El espejo predicciones/jornada_{pred.get('jornada')}.json no coincide con "
                    f"ultima_prediccion.json en: {', '.join(distintas[:8])}."
                )
        cronicos = fallos_cronicos()
        for fallo in cronicos:
            avisos.append(
                f"Fallo cronico del pipeline: {fallo['script']} lleva "
                f"{fallo['fallos_consecutivos']} ejecuciones seguidas fallando."
            )

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
            "fallos_cronicos": cronicos,
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
