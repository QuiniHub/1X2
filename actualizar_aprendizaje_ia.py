import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


DATA = Path("data")
JORNADAS = DATA / "jornadas"
OUT = DATA / "aprendizaje_ia.json"
QUINIELAS_JUGADAS = DATA / "quinielas_jugadas.json"
HISTORIAL_QUINIELAS = DATA / "historial_quinielas.json"
PREDICCIONES = DATA / "predicciones"
SNAPSHOTS = DATA / "backtesting" / "pre_cierre"
PESOS_DINAMICOS = DATA / "memoria_ia" / "pesos_dinamicos.json"
HISTORIAL_PREMIOS = DATA / "premios" / "historial_premios.json"

SIGNOS_VALIDOS = {"1", "X", "2"}

# Tabla orientativa ya usada por calcular_premios.py. Se mantiene aqui para
# que el cierre automatico pueda escribir historial_premios.json aunque el
# registro anterior exista con 0 aciertos / 0 fallos.
TABLA_PREMIOS_ESTIMADOS = {
    15: 0.0,
    14: 0.0,
    13: 25.0,
    12: 8.0,
    11: 4.0,
    10: 0.0,
}


def cargar_json(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ahora_iso():
    return datetime.now(timezone.utc).isoformat()


def normalizar_signo(valor):
    texto = str(valor or "").strip().upper()
    return texto if texto in SIGNOS_VALIDOS else ""


def signo_resultado(resultado):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(resultado or ""))
    if not m:
        return None
    gl, gv = int(m.group(1)), int(m.group(2))
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def signo_oficial_partido(partido):
    oficial = normalizar_signo(partido.get("signo_oficial"))
    if oficial:
        return oficial
    return signo_resultado(partido.get("resultado"))


def signos_pronostico(valor):
    texto = str(valor or "").strip().upper()
    return {signo for signo in ("1", "X", "2") if signo in texto}


def acierta(pron, real):
    return real in signos_pronostico(pron)


def tipo_pronostico(valor):
    total = len(signos_pronostico(valor))
    if total >= 3:
        return "TRIPLE"
    if total == 2:
        return "DOBLE"
    if total == 1:
        return "FIJO"
    return "NO_VALIDO"


def pronostico_valido(valor):
    texto = str(valor or "").strip().upper()
    if not texto or texto in {"NO JUGADA", "NO VALIDADA", "PENDIENTE"}:
        return False
    return bool(signos_pronostico(texto))


def extraer_signos_jugada(valor):
    if isinstance(valor, list):
        return [str(s).strip().upper() for s in valor if str(s).strip()]
    texto = str(valor or "").strip().upper()
    if not texto or texto in {"NO VALIDADA", "NO JUGADA", "PENDIENTE"}:
        return []
    partes = [p for p in texto.split() if p]
    if len(partes) > 1:
        return partes
    if re.fullmatch(r"[12X]{14}", texto):
        return list(texto)
    return []


def normalizar_jugada(jugada, origen):
    jornada = jugada.get("jornada")
    jornada_num = int(jornada) if str(jornada or "").isdigit() else None
    signos = extraer_signos_jugada(jugada.get("signos") or jugada.get("nuestra_quiniela"))
    if jornada_num and len(signos) >= 14:
        return jornada_num, {
            "signos": signos[:14],
            "pleno15": str(jugada.get("pleno15") or jugada.get("pleno15_nuestro") or "").strip(),
            "elige8": [int(x) for x in jugada.get("elige8", []) if str(x).isdigit()],
            "origen": jugada.get("origen") or origen,
        }
    return None, None


def cargar_jugadas_validadas():
    jugadas = {}
    memoria = cargar_json(QUINIELAS_JUGADAS, {"jugadas": []})
    historial = cargar_json(HISTORIAL_QUINIELAS, {"jornadas": []})
    for jugada in memoria.get("jugadas", []):
        jornada, normalizada = normalizar_jugada(jugada, "data/quinielas_jugadas.json")
        if normalizada:
            jugadas[jornada] = normalizada
    for jugada in historial.get("jornadas", []):
        jornada, normalizada = normalizar_jugada(jugada, "data/historial_quinielas.json")
        if normalizada and jornada not in jugadas:
            jugadas[jornada] = normalizada
    return jugadas


def indexar_partidos_prediccion(prediccion):
    return {
        int(partido.get("num") or 0): partido
        for partido in (prediccion or {}).get("partidos", [])
        if str(partido.get("num") or "").isdigit()
    }


def cargar_predicciones_detalladas_por_jornada():
    predicciones = {}
    if PREDICCIONES.exists():
        for path in sorted(PREDICCIONES.glob("jornada_*.json")):
            data = cargar_json(path, {})
            jornada = data.get("jornada")
            if str(jornada or "").isdigit() and data.get("prediccion_disponible") is not False:
                predicciones[int(jornada)] = {
                    "path": path,
                    "data": data,
                    "partidos": indexar_partidos_prediccion(data),
                }
    if SNAPSHOTS.exists():
        for path in sorted(SNAPSHOTS.glob("jornada_*.json")):
            snap = cargar_json(path, {})
            pred = snap.get("prediccion") or snap
            jornada = snap.get("jornada") or pred.get("jornada")
            if str(jornada or "").isdigit() and int(jornada) not in predicciones:
                predicciones[int(jornada)] = {
                    "path": path,
                    "data": pred,
                    "partidos": indexar_partidos_prediccion(pred),
                }
    return predicciones


def cargar_predicciones_por_jornada():
    return {
        jornada: info.get("partidos", {})
        for jornada, info in cargar_predicciones_detalladas_por_jornada().items()
    }


def signo_prediccion(partido_pred):
    if not partido_pred:
        return ""
    for campo in (
        "signo_final",
        "signo_base",
        "signo",
        "pronostico_ia",
        "signo_recomendado",
        "prediccion",
    ):
        valor = partido_pred.get(campo)
        if pronostico_valido(valor):
            return str(valor).strip().upper()
    return ""


def fuentes_utilizadas(prediccion):
    fuentes = []
    if not prediccion:
        return fuentes
    origen = prediccion.get("origen_probabilidades")
    if origen:
        fuentes.append(origen)
    trazabilidad = prediccion.get("trazabilidad_datos") or {}
    memoria = trazabilidad.get("memoria_estadistica") or {}
    fuente_memoria = memoria.get("fuente")
    if fuente_memoria:
        fuentes.append(fuente_memoria)
    if trazabilidad.get("noticias_recientes", {}).get("local") or trazabilidad.get("noticias_recientes", {}).get("visitante"):
        fuentes.append("contexto_equipos")
    if trazabilidad.get("contexto_competitivo", {}).get("local") or trazabilidad.get("contexto_competitivo", {}).get("visitante"):
        fuentes.append("contexto_competitivo")
    return sorted(dict.fromkeys(str(f) for f in fuentes if f))


def extraer_clasificacion(prediccion, partido):
    return {
        "local": {
            "equipo": partido.get("local"),
            "posicion": prediccion.get("posicion_local") or partido.get("posicion_local"),
            "puntos": prediccion.get("puntos_local") or partido.get("puntos_local"),
        },
        "visitante": {
            "equipo": partido.get("visitante"),
            "posicion": prediccion.get("posicion_visitante") or partido.get("posicion_visitante"),
            "puntos": prediccion.get("puntos_visitante") or partido.get("puntos_visitante"),
        },
    }


def extraer_forma_reciente(prediccion, partido):
    contexto_local = prediccion.get("contexto_local") or {}
    contexto_visitante = prediccion.get("contexto_visitante") or {}
    return {
        "local": contexto_local.get("forma_reciente") or partido.get("forma_local") or contexto_local.get("racha") or {},
        "visitante": contexto_visitante.get("forma_reciente") or partido.get("forma_visitante") or contexto_visitante.get("racha") or {},
    }


def detalle_modelo(prediccion):
    if not prediccion:
        return {}
    return {
        "probabilidades_usadas": prediccion.get("probabilidades") or {},
        "fuentes_utilizadas": fuentes_utilizadas(prediccion),
        "cuotas": prediccion.get("cuotas") or {},
        "explicacion_modelo": prediccion.get("explicabilidad_ia") or prediccion.get("razonamiento") or "",
        "ajuste_aprendizaje": prediccion.get("ajuste_aprendizaje") or {},
        "ajuste_pesos_dinamicos": prediccion.get("ajuste_pesos_dinamicos") or {},
        "ajuste_perfiles_autonomos": prediccion.get("ajuste_perfiles_autonomos") or {},
        "perfil_autonomo_local": prediccion.get("perfil_autonomo_local") or {},
        "perfil_autonomo_visitante": prediccion.get("perfil_autonomo_visitante") or {},
    }


def clasificar_fallo(pron, real):
    signos = signos_pronostico(pron)
    if "X" not in signos and real == "X":
        return "No cubrio empate"
    if len(signos) == 1:
        return "Fijo fallado"
    if len(signos) == 2:
        return "Doble insuficiente"
    return "Triple fallado"


def numero_jornada(path):
    m = re.search(r"(\d+)", path.stem)
    return int(m.group(1)) if m else 0


def porcentaje(parte, total):
    return round(float(parte) / max(float(total), 1.0) * 100, 2)


def precision(aciertos, total):
    return porcentaje(aciertos, total)


def resumen_por_counter(aciertos, totales):
    salida = {}
    for clave in sorted(set(aciertos) | set(totales)):
        total = int(totales.get(clave, 0))
        ok = int(aciertos.get(clave, 0))
        salida[clave] = {
            "total": total,
            "aciertos": ok,
            "fallos": max(total - ok, 0),
            "precision": precision(ok, total),
        }
    return salida


def generar_ajuste_motor(resumen):
    total = int(resumen.get("partidos_revisados") or 0)
    fallos = int(resumen.get("fallos") or 0)
    fallos_por_tipo = resumen.get("fallos_por_tipo") or {}
    no_cubrio_empate = int(fallos_por_tipo.get("No cubrio empate") or 0)
    fijo_fallado = int(fallos_por_tipo.get("Fijo fallado") or 0)
    doble_insuficiente = int(fallos_por_tipo.get("Doble insuficiente") or 0)

    if total < 28:
        muestra = "baja"
    elif total < 84:
        muestra = "media"
    else:
        muestra = "suficiente"

    no_cubrio_empate_sobre_fallos = porcentaje(no_cubrio_empate, fallos)
    no_cubrio_empate_sobre_total = porcentaje(no_cubrio_empate, total)
    fijo_fallado_sobre_fallos = porcentaje(fijo_fallado, fallos)
    fijo_fallado_sobre_total = porcentaje(fijo_fallado, total)
    doble_insuficiente_sobre_total = porcentaje(doble_insuficiente, total)

    if muestra == "baja":
        boost_empate = 0.0
        riesgo_fijo = 0.0
        riesgo_triple = 0.0
    else:
        boost_empate = round(min(
            6.0,
            max(0.0, no_cubrio_empate_sobre_fallos - 15.0) * 0.18
            + max(0.0, no_cubrio_empate_sobre_total - 5.0) * 0.40,
        ), 2)
        riesgo_fijo = round(min(
            18.0,
            max(0.0, fijo_fallado_sobre_total - 12.0) * 0.80
            + max(0.0, fijo_fallado_sobre_fallos - 35.0) * 0.20,
        ), 2)
        riesgo_triple = round(min(
            10.0,
            max(0.0, doble_insuficiente_sobre_total - 4.0) * 0.90,
        ), 2)

    reglas = []
    if boost_empate:
        reglas.append("Subir X en partidos de margen corto o tendencia de empate porque el historial propio dejo empates sin cubrir.")
    if riesgo_fijo:
        reglas.append("Penalizar fijo limpio si el favorito no supera un umbral fuerte de probabilidad/margen.")
    if riesgo_triple:
        reglas.append("Elevar riesgo de triple cuando el tercer signo sigue vivo y los dobles propios fueron insuficientes.")
    if not reglas:
        reglas.append("Muestra todavia insuficiente o sin sesgo fuerte: mantener aprendizaje conservador.")

    return {
        "version": "1.0",
        "partidos_base": total,
        "muestra": muestra,
        "tasas_error": {
            "fallos_total_pct": porcentaje(fallos, total),
            "no_cubrio_empate_sobre_fallos_pct": no_cubrio_empate_sobre_fallos,
            "no_cubrio_empate_sobre_total_pct": no_cubrio_empate_sobre_total,
            "fijo_fallado_sobre_fallos_pct": fijo_fallado_sobre_fallos,
            "fijo_fallado_sobre_total_pct": fijo_fallado_sobre_total,
            "doble_insuficiente_sobre_total_pct": doble_insuficiente_sobre_total,
        },
        "boost_empate_zona_riesgo": boost_empate,
        "riesgo_extra_fijo_fragil": riesgo_fijo,
        "riesgo_extra_triple_insuficiente": riesgo_triple,
        "min_dobles_auto": 3 if muestra != "baja" and fijo_fallado_sobre_total >= 15 else 0,
        "min_triples_auto": 1 if muestra != "baja" and doble_insuficiente_sobre_total >= 6 else 0,
        "umbral_fijo_seguro": 58 if muestra != "baja" and fijo_fallado_sobre_total >= 15 else 54,
        "reglas": reglas,
    }


def resumen_vacio():
    return {
        "jornadas_revisadas": 0,
        "partidos_revisados": 0,
        "aciertos": 0,
        "fallos": 0,
        "fallos_por_tipo": Counter(),
        "fallos_por_signo_real": Counter(),
        "signos_omitidos_en_fallo": Counter(),
        "totales_por_tipo": Counter(),
        "aciertos_por_tipo": Counter(),
        "totales_por_signo_real": Counter(),
        "aciertos_por_signo_real": Counter(),
        "detalle": [],
    }


def registrar_revision(resumen, jornada_num, partido, pron, real, origen, prediccion=None, pesos_modelo=None):
    ok = acierta(pron, real)
    tipo = tipo_pronostico(pron)
    signos = signos_pronostico(pron)
    motivo_error = "" if ok else clasificar_fallo(pron, real)
    resumen["partidos_revisados"] += 1
    resumen["totales_por_tipo"][tipo] += 1
    resumen["totales_por_signo_real"][real] += 1

    if ok:
        resumen["aciertos"] += 1
        resumen["aciertos_por_tipo"][tipo] += 1
        resumen["aciertos_por_signo_real"][real] += 1
    else:
        resumen["fallos"] += 1
        resumen["fallos_por_tipo"][motivo_error] += 1
        resumen["fallos_por_signo_real"][real] += 1
        if real not in signos:
            resumen["signos_omitidos_en_fallo"][real] += 1

    modelo = detalle_modelo(prediccion or {})
    resumen["detalle"].append({
        "jornada": jornada_num,
        "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
        "pronostico": pron,
        "tipo_pronostico": tipo,
        "resultado": partido.get("resultado"),
        "resultado_final": partido.get("resultado"),
        "signo_real": real,
        "signos_cubiertos": "".join(signo for signo in ("1", "X", "2") if signo in signos),
        "signo_omitido": real if real not in signos else "",
        "acierto": ok,
        "motivo_error": motivo_error,
        "origen": origen,
        "probabilidades_usadas": modelo.get("probabilidades_usadas", {}),
        "pesos_modelo": (pesos_modelo or {}).get("pesos", pesos_modelo or {}),
        "fuentes_utilizadas": modelo.get("fuentes_utilizadas", []),
        "clasificacion": extraer_clasificacion(prediccion or {}, partido),
        "forma_reciente": extraer_forma_reciente(prediccion or {}, partido),
        "cuotas": modelo.get("cuotas", {}),
        "explicacion_modelo": modelo.get("explicacion_modelo", ""),
        "ajuste_aprendizaje": modelo.get("ajuste_aprendizaje", {}),
        "ajuste_pesos_dinamicos": modelo.get("ajuste_pesos_dinamicos", {}),
        "ajuste_perfiles_autonomos": modelo.get("ajuste_perfiles_autonomos", {}),
        "perfil_autonomo_local": modelo.get("perfil_autonomo_local", {}),
        "perfil_autonomo_visitante": modelo.get("perfil_autonomo_visitante", {}),
    })


def construir_salida(resumen, fuentes_jugadas):
    total = max(resumen["partidos_revisados"], 1)
    salida = {
        "version": "1.2",
        "precision": round(resumen["aciertos"] / total * 100, 2),
        "jornadas_revisadas": resumen["jornadas_revisadas"],
        "partidos_revisados": resumen["partidos_revisados"],
        "aciertos": resumen["aciertos"],
        "fallos": resumen["fallos"],
        "fallos_por_tipo": dict(resumen["fallos_por_tipo"]),
        "fallos_por_signo_real": dict(resumen["fallos_por_signo_real"]),
        "signos_omitidos_en_fallo": dict(resumen["signos_omitidos_en_fallo"]),
        "precision_por_tipo": resumen_por_counter(resumen["aciertos_por_tipo"], resumen["totales_por_tipo"]),
        "precision_por_signo_real": resumen_por_counter(
            resumen["aciertos_por_signo_real"],
            resumen["totales_por_signo_real"],
        ),
        "detalle": resumen["detalle"][-250:],
        "ajustes_recomendados": [
            "Subir peso del empate si aumenta No cubrio empate.",
            "Reducir fijos en partidos con margen probabilistico bajo.",
            "Asignar triples a partidos con historial de sorpresa alta.",
        ],
        "fuentes_jugadas": dict(fuentes_jugadas),
    }
    salida["ajuste_motor"] = generar_ajuste_motor(salida)
    return salida


def jornada_cerrada(data):
    partidos = data.get("partidos") or []
    return bool(partidos) and all(signo_oficial_partido(partido) in SIGNOS_VALIDOS for partido in partidos)


def comparar_jornada_con_prediccion(jornada_data, pred_info):
    pred_por_num = (pred_info or {}).get("partidos") or {}
    detalle = []
    aciertos = 0
    fallos = 0
    comparados = 0

    for partido in jornada_data.get("partidos", []):
        num = partido.get("num")
        if not str(num or "").isdigit():
            continue
        real = signo_oficial_partido(partido)
        pron = signo_prediccion(pred_por_num.get(int(num)))
        if real not in SIGNOS_VALIDOS or not pronostico_valido(pron):
            continue
        ok = acierta(pron, real)
        comparados += 1
        aciertos += int(ok)
        fallos += int(not ok)
        detalle.append({
            "num": int(num),
            "local": partido.get("local"),
            "visitante": partido.get("visitante"),
            "signo_predicho": pron,
            "signo_nuestro": pron,
            "tipo": tipo_pronostico(pron),
            "signo_oficial": real,
            "resultado": partido.get("resultado"),
            "acertado": ok,
        })

    return {
        "comparados": comparados,
        "aciertos": aciertos,
        "fallos": fallos,
        "detalle": sorted(detalle, key=lambda item: item["num"]),
    }


def cerrar_jornada_con_prediccion(path, jornada_data, pred_info):
    if not jornada_cerrada(jornada_data) or not pred_info:
        return None

    comparacion = comparar_jornada_con_prediccion(jornada_data, pred_info)
    if not comparacion["comparados"]:
        return None

    pred_por_num = pred_info.get("partidos") or {}
    cambiado = False
    for partido in jornada_data.get("partidos", []):
        num = partido.get("num")
        if not str(num or "").isdigit():
            continue
        real = signo_oficial_partido(partido)
        pron = signo_prediccion(pred_por_num.get(int(num)))
        if real not in SIGNOS_VALIDOS or not pronostico_valido(pron):
            continue
        ok = acierta(pron, real)
        if partido.get("signo_nuestro") != pron:
            partido["signo_nuestro"] = pron
            cambiado = True
        if partido.get("acierto_nuestro") is not ok:
            partido["acierto_nuestro"] = ok
            cambiado = True

    resumen_nuestro = {
        "origen": str(pred_info.get("path") or "data/predicciones"),
        "comparados": comparacion["comparados"],
        "aciertos": comparacion["aciertos"],
        "fallos": comparacion["fallos"],
        "precision": precision(comparacion["aciertos"], comparacion["comparados"]),
        "actualizado_en": ahora_iso(),
    }
    if jornada_data.get("resumen_nuestro") != resumen_nuestro:
        jornada_data["resumen_nuestro"] = resumen_nuestro
        cambiado = True

    if cambiado:
        guardar_json(path, jornada_data)
    return comparacion


def hay_coberturas(prediccion, detalle):
    resumen = prediccion.get("resumen") or {}
    configuracion = prediccion.get("configuracion") or {}
    if int(resumen.get("dobles") or configuracion.get("dobles") or 0) > 0:
        return True
    if int(resumen.get("triples") or configuracion.get("triples") or 0) > 0:
        return True
    return any(len(signos_pronostico(item.get("signo_predicho"))) > 1 for item in detalle)


def estimar_premio(aciertos, prediccion, detalle):
    if hay_coberturas(prediccion, detalle):
        return 0.0, "pendiente"
    if aciertos in TABLA_PREMIOS_ESTIMADOS:
        premio = TABLA_PREMIOS_ESTIMADOS[aciertos]
        fuente = "calculado" if premio > 0 else "pendiente"
        return premio, fuente
    return 0.0, "pendiente"


def construir_registro_premios(jornada, pred_info, comparacion):
    prediccion = (pred_info or {}).get("data") or {}
    detalle = comparacion.get("detalle") or []
    premio, fuente = estimar_premio(comparacion["aciertos"], prediccion, detalle)
    boleto = "".join(
        str(item.get("signo_predicho") or "?")
        for item in sorted(detalle, key=lambda x: x.get("num") or 0)
    )
    return {
        "jornada": jornada,
        "aciertos": comparacion["aciertos"],
        "fallos": comparacion["fallos"],
        "partidos_comparados": comparacion["comparados"],
        "premio_eur": premio,
        "fuente_premio": fuente,
        "boleto": boleto,
        "detalle_partidos": detalle,
        "origen_prediccion": str((pred_info or {}).get("path") or ""),
        "actualizado_en": ahora_iso(),
        "notas": "Comparado automaticamente contra data/predicciones/jornada_X.json al cerrarse la jornada.",
    }


def debe_reemplazar_registro_premios(actual, nuevo):
    if not actual:
        return True
    if actual.get("fuente_premio") == "manual":
        # Conserva el premio manual, pero permite actualizar aciertos/fallos y detalle.
        return True
    campos = ("aciertos", "fallos", "partidos_comparados", "boleto", "detalle_partidos")
    return any(actual.get(campo) != nuevo.get(campo) for campo in campos)


def actualizar_historial_premios(registros):
    if not registros:
        return 0
    historial = cargar_json(HISTORIAL_PREMIOS, {"jornadas": []})
    existentes = {
        int(entry.get("jornada")): entry
        for entry in historial.get("jornadas", [])
        if str(entry.get("jornada") or "").isdigit()
    }

    cambios = 0
    for jornada, nuevo in registros.items():
        actual = existentes.get(jornada)
        if not debe_reemplazar_registro_premios(actual, nuevo):
            continue
        if actual and actual.get("fuente_premio") == "manual":
            nuevo["premio_eur"] = actual.get("premio_eur", nuevo["premio_eur"])
            nuevo["fuente_premio"] = "manual"
            nuevo["notas"] = actual.get("notas") or nuevo.get("notas", "")
        existentes[jornada] = nuevo
        cambios += 1

    if cambios:
        historial["jornadas"] = [existentes[j] for j in sorted(existentes)]
        guardar_json(HISTORIAL_PREMIOS, historial)
    return cambios


def main():
    resumen = resumen_vacio()
    jugadas = cargar_jugadas_validadas()
    predicciones_detalladas = cargar_predicciones_detalladas_por_jornada()
    predicciones = {j: info.get("partidos", {}) for j, info in predicciones_detalladas.items()}
    pesos_modelo = cargar_json(PESOS_DINAMICOS, {})
    fuentes_jugadas = Counter(jugada.get("origen") or "desconocido" for jugada in jugadas.values())
    registros_premios = {}
    jornadas_cerradas_actualizadas = 0

    for path in sorted(JORNADAS.glob("jornada_*.json"), key=numero_jornada):
        data = cargar_json(path, {})
        revisados_jornada = 0
        jornada_num = data.get("jornada") if str(data.get("jornada") or "").isdigit() else numero_jornada(path)
        pred_info = predicciones_detalladas.get(int(jornada_num or 0))
        jugada = jugadas.get(jornada_num)

        comparacion_cierre = cerrar_jornada_con_prediccion(path, data, pred_info)
        if comparacion_cierre:
            registros_premios[int(jornada_num)] = construir_registro_premios(int(jornada_num), pred_info, comparacion_cierre)
            jornadas_cerradas_actualizadas += 1
            data = cargar_json(path, data)

        for idx, partido in enumerate(data.get("partidos", [])):
            real = signo_oficial_partido(partido)
            num = int(partido.get("num") or idx + 1) if str(partido.get("num") or idx + 1).isdigit() else idx + 1
            prediccion = predicciones.get(int(jornada_num or 0), {}).get(num, {})
            pron_prediccion = signo_prediccion(prediccion)
            if pronostico_valido(pron_prediccion):
                pron = pron_prediccion
                origen = f"data/predicciones/jornada_{int(jornada_num)}.json"
            elif jugada and idx < len(jugada["signos"]):
                pron = jugada["signos"][idx]
                origen = jugada.get("origen") or "data/quinielas_jugadas.json"
            else:
                pron = partido.get("signo_nuestro") or partido.get("signo_final") or partido.get("pronostico_ia")
                origen = "partido"
            if not real or not pronostico_valido(pron):
                continue
            registrar_revision(resumen, jornada_num, partido, pron, real, origen, prediccion, pesos_modelo)
            revisados_jornada += 1
        if revisados_jornada:
            resumen["jornadas_revisadas"] += 1

    cambios_premios = actualizar_historial_premios(registros_premios)
    salida = construir_salida(resumen, fuentes_jugadas)
    guardar_json(OUT, salida)
    print(f"Aprendizaje IA generado: {OUT}")
    print(f"Jornadas cerradas comparadas con prediccion: {jornadas_cerradas_actualizadas}")
    print(f"Registros de premios actualizados: {cambios_premios}")


if __name__ == "__main__":
    main()
