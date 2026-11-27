import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cronologia_jornadas


DATA = Path("data")
JORNADAS = DATA / "jornadas"
OUT = DATA / "aprendizaje_ia.json"
QUINIELAS_JUGADAS = DATA / "quinielas_jugadas.json"
HISTORIAL_QUINIELAS = DATA / "historial_quinielas.json"
PREDICCIONES = DATA / "predicciones"
SNAPSHOTS = DATA / "backtesting" / "pre_cierre"
PESOS_DINAMICOS = DATA / "memoria_ia" / "pesos_dinamicos.json"
HISTORIAL_PREMIOS = DATA / "premios" / "historial_premios.json"
FUENTE_LOSILLA = DATA / "memoria_ia" / "fuente_losilla.json"
SORPRESAS_MERCADO = DATA / "memoria_ia" / "sorpresas_mercado.json"

SIGNOS_VALIDOS = {"1", "X", "2"}

# Umbral de probabilidad de mercado a partir del cual un favorito que no
# gana cuenta como "sorpresa" en registrar_sorpresas_mercado(). Bajado de
# 75.0 a 52.0 el 19/08/2026 a peticion explicita de Marc: revisando a mano
# los % reales de eduardolosilla.es de la J1, senalo el mismo los 5 partidos
# que considera sorpresa real (P3 Racing-Villarreal, P7 Cadiz-Celta Fortuna,
# P10 Eibar-Tenerife, P12 Girona-Leganes, P14 Sporting-Sabadell -favoritos
# del 53,7% al 61,3% segun la media de las 3 columnas de Losilla, Jugados/
# LAE/Probables- y dejo fuera a proposito P8 Oviedo-Granada (51,7%, el mas
# parecido mas debil). 52.0 es el umbral mas alto que cubre los 5 sin colar
# el que Marc excluyo. Ojo: no bajar mucho mas de aqui -en 3 temporadas
# completas el 48,6% de TODOS los partidos de Primera+Segunda son "sorpresa"
# frente al favorito de las cuotas (ver project_sorpresas_por_temporada en
# la memoria), asi que un umbral por debajo de ~50% deja de ser una señal
# rara y empieza a marcar casi cualquier resultado como sorpresa.
UMBRAL_PROBABILIDAD_SORPRESA = 52.0

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
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def _jornada_empezada(datos_jornada):
    """True si la jornada ya tiene algun signo oficial (ha empezado o cerrado)."""
    return any(
        signo_oficial_partido(partido) in SIGNOS_VALIDOS
        for partido in (datos_jornada or {}).get("partidos") or []
        if isinstance(partido, dict)
    )


def _prediccion_posterior_a_la_jornada(prediccion, datos_jornada):
    """True si el fichero de prediccion se genero DESPUES del dia del primer
    partido: no puede ser 'lo que se dijo antes' y no sirve para aprender."""
    generada = cronologia_jornadas.parsear_fecha((prediccion or {}).get("generado_en"))
    primer_partido = cronologia_jornadas.fecha_real_jornada(datos_jornada or {})
    if generada is None or primer_partido is None:
        return False
    return generada > primer_partido


def cargar_predicciones_detalladas_por_jornada():
    """Prediccion con la que se evalua cada jornada.

    Auditoria 26/11 (fuga de futuro): se cargaba primero
    data/predicciones/jornada_N.json y el snapshot pre-cierre solo si faltaba
    ese fichero. Pero el motor reescribia data/predicciones/jornada_N.json
    despues del primer partido (y a veces despues del ultimo): en 21 de las 22
    jornadas de 26/27 con snapshot los signos eran distintos, y la J72 daba
    14/14 con el fichero regenerado y 6/14 con lo que se dijo de verdad.
    Ese aprendizaje inflado vuelve al motor por ajuste_motor.

    Regla ahora:
      * jornada EMPEZADA o cerrada: manda el snapshot pre-cierre (comprobado
        por cronologia_jornadas como de la MISMA jornada real, no de otra
        temporada con el mismo numero);
      * sin snapshot, la prediccion de data/predicciones solo vale si no se
        genero despues del dia del primer partido;
      * jornada sin empezar: data/predicciones (es la prediccion viva).
    """
    predicciones = {}
    if PREDICCIONES.exists():
        for path in sorted(PREDICCIONES.glob("jornada_*.json")):
            data = cargar_json(path, {})
            jornada = data.get("jornada")
            if not (str(jornada or "").isdigit() and data.get("prediccion_disponible") is not False):
                continue
            datos_jornada = cronologia_jornadas.cargar_jornada(int(jornada), JORNADAS)
            if datos_jornada is not None:
                # Mismo numero no basta: tienen que ser los mismos partidos.
                if (
                    cronologia_jornadas.coincidencia_equipos(data, datos_jornada)[1] >= 7
                    and not cronologia_jornadas.misma_jornada(data, datos_jornada)
                ):
                    continue
                if _jornada_empezada(datos_jornada) and _prediccion_posterior_a_la_jornada(data, datos_jornada):
                    continue
            predicciones[int(jornada)] = {
                "path": path,
                "data": data,
                "partidos": indexar_partidos_prediccion(data),
                "origen": "prediccion",
            }
    if SNAPSHOTS.exists():
        for path in sorted(SNAPSHOTS.glob("jornada_*.json")):
            m = re.search(r"(\d+)", path.stem)
            if not m:
                continue
            jornada = int(m.group(1))
            pred = cronologia_jornadas.prediccion_del_cierre(jornada, SNAPSHOTS, JORNADAS)
            if not isinstance(pred, dict) or not pred.get("partidos"):
                continue
            datos_jornada = cronologia_jornadas.cargar_jornada(jornada, JORNADAS)
            if jornada in predicciones and not _jornada_empezada(datos_jornada):
                continue
            predicciones[jornada] = {
                "path": path,
                "data": pred,
                "partidos": indexar_partidos_prediccion(pred),
                "origen": "snapshot_pre_cierre",
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


def orden_cronologico_jornada(path):
    """Clave de orden por FECHA real de la jornada, con el numero solo como
    desempate.

    El detalle de revisiones se recorta a las ultimas 250 entradas, dando por
    hecho que "ultimas" equivale a "numero mas alto". La Quiniela reinicia su
    numeracion cada temporada, asi que la J1 de 26/27 -la mas reciente de
    todas- se colocaba la PRIMERA de la lista y era justo la que el recorte
    tiraba: sus 14 revisiones nunca llegaban a aprendizaje_ia.json y la
    compuerta dejaba la prediccion de la J2 bloqueada para siempre.
    """
    data = cargar_json(path, {})
    fechas = [
        str(p.get("fecha") or "")
        for p in (data.get("partidos") or [])
        if isinstance(p, dict) and p.get("fecha")
    ]
    return (min(fechas) if fechas else "", numero_jornada(path))


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



def clave_jornada_losilla(jornada):
    try:
        return f"jornada_{int(jornada):02d}"
    except (TypeError, ValueError):
        return None


def probabilidades_jornada_losilla(fuente_losilla, jornada_num):
    """Devuelve el bloque de probabilidades de mercado de ESA jornada.

    Prioriza el historico por jornada (`historico_probabilidades`, ver
    actualizar_fuente_losilla.archivar_probabilidades_historico) y solo cae
    al bloque "actual" si de verdad corresponde a la misma jornada -nunca lo
    usa a ciegas, porque en cuanto Losilla pasa a la jornada siguiente ese
    bloque deja de representar la jornada que se esta puntuando aqui.
    """
    historico = (fuente_losilla or {}).get("historico_probabilidades") or {}
    clave = clave_jornada_losilla(jornada_num)
    bloque = historico.get(clave) if clave else None
    if bloque:
        return bloque
    actual = (fuente_losilla or {}).get("probabilidades") or {}
    try:
        if int(actual.get("jornada") or 0) == int(jornada_num):
            return actual
    except (TypeError, ValueError):
        pass
    return {}


def mercado_partido_losilla(fuente_losilla, jornada_num, numero_partido):
    partidos = probabilidades_jornada_losilla(fuente_losilla, jornada_num).get("partidos") or []
    for item in partidos:
        try:
            if int(item.get("numero") or 0) == int(numero_partido):
                signos = item.get("probabilidades_signo") or {}
                valores = {
                    "1": float(signos.get("1") if signos.get("1") is not None else item.get("probabilidad_1") or 0),
                    "X": float(signos.get("X") if signos.get("X") is not None else item.get("probabilidad_X") or 0),
                    "2": float(signos.get("2") if signos.get("2") is not None else item.get("probabilidad_2") or 0),
                }
                favorito = max(valores, key=lambda signo: valores.get(signo, 0.0))
                return favorito, valores[favorito], valores
        except Exception:
            continue
    return "", 0.0, {}


def alertas_motivacion_prediccion(prediccion):
    ajuste = (prediccion or {}).get("ajuste_motivacion") or {}
    alertas = ajuste.get("alertas") or (prediccion or {}).get("alertas_motivacion") or []
    if isinstance(alertas, str):
        alertas = [alertas]
    return [str(a).strip() for a in alertas if str(a).strip()]


def categoria_sorpresa_mercado(prediccion):
    alertas = alertas_motivacion_prediccion(prediccion)
    if "derbi_todo_puede_pasar" in alertas:
        return "derbi"
    if any(a in alertas for a in ("equipo_sin_objetivos", "ambos_clasificados_sin_tension")):
        return "partido_sin_presion"
    if alertas:
        return "motivacion_competitiva"
    texto = json.dumps(prediccion or {}, ensure_ascii=False).lower()
    if "racha" in texto or "racha_rota" in texto:
        return "racha_rota"
    return "desconocido"


def inicializar_sorpresas_mercado():
    if not SORPRESAS_MERCADO.exists():
        guardar_json(SORPRESAS_MERCADO, {"version": "1.0", "sorpresas": []})


ORIGEN_SORPRESA_MERCADO = "mercado_favorito_no_gano"
ORIGEN_SORPRESA_DIARIO = "diario_aprendizaje_fallo_fijo"


def origen_sorpresa(item):
    """Origen de una entrada. Las antiguas sin campo 'origen' se deducen:
    solo las de mercado llevan probabilidad_mercado_favorito."""
    origen = str((item or {}).get("origen") or "").strip()
    if origen:
        return origen
    if "probabilidad_mercado_favorito" in (item or {}):
        return ORIGEN_SORPRESA_MERCADO
    return ORIGEN_SORPRESA_DIARIO


def ruta_posix(ruta):
    """Ruta con barras normales: en Windows str(Path) escribia barras
    invertidas en los JSON publicados."""
    if not ruta:
        return ""
    return Path(str(ruta)).as_posix()


def numero_partido_sorpresa(item):
    """Numero de partido de una entrada de sorpresas_mercado.json.

    Auditoria 26/11: el fichero tiene DOS escritores. Este script usaba la
    clave 'numero_partido' y alimentar_sorpresas_mercado.py 'num_partido' (y
    borraba en cada ciclo todo lo que no la tuviera). Esquema unico: las dos
    claves se escriben siempre y se aceptan las dos al leer.
    """
    for clave in ("num_partido", "numero_partido"):
        valor = (item or {}).get(clave)
        if str(valor or "").isdigit():
            return int(valor)
    return 0


def temporada_sorpresa(item, jornadas_dir=None):
    """Temporada de una entrada: la guardada, o la de su fecha, o la del
    fichero de jornada. La jornada 5 de una temporada no es la de la otra."""
    guardada = (item or {}).get("temporada")
    if guardada:
        return str(guardada)
    try:
        numero = int(item.get("jornada") or 0) or None
    except (TypeError, ValueError):
        numero = None
    for campo in ("fecha", "registrada_en"):
        fecha = cronologia_jornadas.parsear_fecha(item.get(campo))
        if fecha is not None:
            return cronologia_jornadas.temporada_de_fecha(fecha, numero)
    if numero:
        datos = cronologia_jornadas.cargar_jornada(numero, jornadas_dir or JORNADAS)
        fecha = cronologia_jornadas.fecha_real_jornada(datos) if datos else None
        if fecha is not None:
            return cronologia_jornadas.temporada_de_fecha(fecha, numero)
    return None


def registrar_sorpresas_mercado(jornada_num, jornada_data, pred_info):
    fuente_losilla = cargar_json(FUENTE_LOSILLA, {})
    memoria = cargar_json(SORPRESAS_MERCADO, {"version": "1.0", "sorpresas": []})
    sorpresas = memoria.setdefault("sorpresas", [])
    fecha_jornada = cronologia_jornadas.fecha_real_jornada(jornada_data)
    temporada = (
        cronologia_jornadas.temporada_de_fecha(fecha_jornada, int(jornada_num))
        if fecha_jornada else None
    )
    # Identidad de una sorpresa: (temporada, jornada, partido, origen). El
    # origen entra en la clave porque un mismo partido puede ser a la vez
    # sorpresa de mercado (este script) y fijo fallado del diario (el otro
    # escritor): son dos hechos distintos y uno no debe tapar al otro.
    existentes = {
        (
            temporada_sorpresa(item),
            int(item.get("jornada") or 0),
            numero_partido_sorpresa(item),
        )
        for item in sorpresas
        if str(item.get("jornada") or "").isdigit()
        and numero_partido_sorpresa(item)
        and origen_sorpresa(item) == ORIGEN_SORPRESA_MERCADO
    }
    pred_por_num = (pred_info or {}).get("partidos") or {}
    nuevas = 0
    for partido in jornada_data.get("partidos", []):
        num = partido.get("num")
        if not str(num or "").isdigit():
            continue
        num = int(num)
        real = signo_oficial_partido(partido)
        if real not in SIGNOS_VALIDOS:
            continue
        signo_fav, prob_fav, mercado = mercado_partido_losilla(fuente_losilla, jornada_num, num)
        if not signo_fav or prob_fav <= UMBRAL_PROBABILIDAD_SORPRESA or signo_fav == real:
            continue
        prediccion = pred_por_num.get(num, {})
        alertas = alertas_motivacion_prediccion(prediccion)
        clave = (temporada, int(jornada_num), num)
        if clave in existentes:
            continue
        # partido / pronostico_jugado / resultado / registrada_en: los lee el
        # chat de la web (index.html) en cada entrada del fichero; sin ellos
        # pintaba 'undefined'. pronostico_jugado es lo que decia el motor al
        # cierre (puede ser un doble que acerto): la sorpresa es del MERCADO.
        entrada = {
            "jornada": int(jornada_num),
            "temporada": temporada,
            "num_partido": num,
            "numero_partido": num,
            "origen": ORIGEN_SORPRESA_MERCADO,
            "partido": f"{num}. {partido.get('local') or ''} - {partido.get('visitante') or ''}",
            "local": partido.get("local"),
            "visitante": partido.get("visitante"),
            "pronostico_jugado": signo_prediccion(prediccion),
            "resultado": partido.get("resultado") or "",
            "registrada_en": ahora_iso(),
            "probabilidad_mercado_favorito": round(float(prob_fav), 2),
            "signo_favorito_mercado": signo_fav,
            "signo_real": real,
            "alerta_motivacion_detectada": alertas[0] if alertas else "",
            "alertas_motivacion_detectadas": alertas,
            "categoria_sorpresa": categoria_sorpresa_mercado(prediccion),
            "fecha": partido.get("fecha") or ahora_iso(),
            "mercado_losilla": mercado,
            "origen_prediccion": ruta_posix((pred_info or {}).get("path")),
        }
        sorpresas.append(entrada)
        existentes.add(clave)
        nuevas += 1
    if nuevas or not SORPRESAS_MERCADO.exists():
        memoria["actualizado_en"] = ahora_iso()
        memoria["total_sorpresas"] = len(sorpresas)
        guardar_json(SORPRESAS_MERCADO, memoria)
    return nuevas

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
        "origen": ruta_posix(pred_info.get("path")) or "data/predicciones",
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


def temporadas_con_jugada_real():
    """{numero de jornada: {temporadas}} de las quinielas REALMENTE jugadas
    (data/quinielas_jugadas.json), con la temporada de su fecha de validacion."""
    resultado = {}
    memoria = cargar_json(QUINIELAS_JUGADAS, {"jugadas": []})
    jugadas = memoria.get("jugadas", []) if isinstance(memoria, dict) else []
    for jugada in jugadas:
        if not isinstance(jugada, dict) or not str(jugada.get("jornada") or "").isdigit():
            continue
        numero = int(jugada["jornada"])
        fecha = cronologia_jornadas.parsear_fecha(jugada.get("validado_en") or jugada.get("fecha"))
        temporada = cronologia_jornadas.temporada_de_fecha(fecha, numero) if fecha else None
        resultado.setdefault(numero, set()).add(temporada)
    return resultado


def construir_registro_premios(jornada, pred_info, comparacion, temporada=None):
    prediccion = (pred_info or {}).get("data") or {}
    detalle = comparacion.get("detalle") or []
    premio, fuente = estimar_premio(comparacion["aciertos"], prediccion, detalle)
    boleto = "".join(
        str(item.get("signo_predicho") or "?")
        for item in sorted(detalle, key=lambda x: x.get("num") or 0)
    )
    return {
        "jornada": jornada,
        "temporada": temporada,
        "aciertos": comparacion["aciertos"],
        "fallos": comparacion["fallos"],
        "partidos_comparados": comparacion["comparados"],
        "premio_eur": premio,
        "fuente_premio": fuente,
        "boleto": boleto,
        "detalle_partidos": detalle,
        "origen_prediccion": ruta_posix((pred_info or {}).get("path")),
        "actualizado_en": ahora_iso(),
        "notas": "Comparado automaticamente contra data/predicciones/jornada_X.json al cerrarse la jornada.",
    }


FUENTES_PREMIO_PROTEGIDAS = ("manual", "confirmado_usuario")
# "manual" es el bloqueo propio de este script; "confirmado_usuario" es el
# que usa calcular_premios.py para premios verificados a mano contra el
# escrutinio oficial (p.ej. jornada 71). Sin esto, este script no reconocia
# ese segundo bloqueo y sobrescribia un premio ya verificado con su propia
# estimacion (mucho mas simple, sin la combinatoria multicolumna real).


def aciertos_verificados_con_jugada_real(actual):
    """True si el registro ya guardado refleja los aciertos de la quiniela
    REALMENTE jugada (calcular_premios.py los marca asi al usar
    data/quinielas_jugadas.json), no la comparacion generica prediccion-vs-
    realidad que hace este script. Esos aciertos/boleto/detalle no se deben
    tocar nunca desde aqui -aunque el premio si sea "manual"/
    "confirmado_usuario"-, o se reproduce el mismo bug que ya se arreglo en
    calcular_premios.py, pero por otra via.
    """
    return bool(actual) and (
        bool(actual.get("aciertos_confirmados")) or actual.get("fuente_aciertos") == "quinielas_jugadas"
    )


def debe_reemplazar_registro_premios(actual, nuevo):
    if not actual:
        return True
    if aciertos_verificados_con_jugada_real(actual):
        return False
    if actual.get("fuente_premio") in FUENTES_PREMIO_PROTEGIDAS:
        # Conserva el premio protegido, pero permite actualizar aciertos/fallos y detalle.
        return True
    campos = ("aciertos", "fallos", "partidos_comparados", "boleto", "detalle_partidos")
    return any(actual.get(campo) != nuevo.get(campo) for campo in campos)


def actualizar_historial_premios(registros, jugadas_reales=None):
    """jugadas_reales: {numero: {temporadas}} de quinielas_jugadas.json.

    Revision 27/11: al evaluar con el snapshot pre-cierre, la comparacion
    generica de este script dejo de coincidir con la guardada en J66 y J67
    (jornadas JUGADAS por Marc) y las reescribia (11 -> 10 aciertos, otro
    boleto, sin temporada). El registro de una jornada jugada es de
    calcular_premios.py (sale de la quiniela real), no de la prediccion del
    motor: si ya existe, aqui no se toca. Ademas el registro nuevo conserva
    la temporada.
    """
    if not registros:
        return 0
    jugadas_reales = jugadas_reales or {}
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
        if actual:
            temporada_actual = actual.get("temporada") or nuevo.get("temporada")
            misma_temporada = (
                not actual.get("temporada")
                or not nuevo.get("temporada")
                or actual.get("temporada") == nuevo.get("temporada")
            )
            if misma_temporada and temporada_actual in jugadas_reales.get(jornada, set()):
                continue
            if misma_temporada and not nuevo.get("temporada"):
                nuevo["temporada"] = actual.get("temporada")
        if actual and actual.get("fuente_premio") in FUENTES_PREMIO_PROTEGIDAS:
            nuevo["premio_eur"] = actual.get("premio_eur", nuevo["premio_eur"])
            nuevo["fuente_premio"] = actual.get("fuente_premio")
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

    for path in sorted(JORNADAS.glob("jornada_*.json"), key=orden_cronologico_jornada):
        data = cargar_json(path, {})
        revisados_jornada = 0
        jornada_num = data.get("jornada") if str(data.get("jornada") or "").isdigit() else numero_jornada(path)
        pred_info = predicciones_detalladas.get(int(jornada_num or 0))
        jugada = jugadas.get(jornada_num)

        comparacion_cierre = cerrar_jornada_con_prediccion(path, data, pred_info)
        if comparacion_cierre:
            fecha_real = cronologia_jornadas.fecha_real_jornada(data)
            registros_premios[int(jornada_num)] = construir_registro_premios(
                int(jornada_num), pred_info, comparacion_cierre,
                temporada=cronologia_jornadas.temporada_de_fecha(fecha_real, int(jornada_num)) if fecha_real else None,
            )
            registrar_sorpresas_mercado(int(jornada_num), data, pred_info)
            jornadas_cerradas_actualizadas += 1
            data = cargar_json(path, data)

        for idx, partido in enumerate(data.get("partidos", [])):
            real = signo_oficial_partido(partido)
            num = int(partido.get("num") or idx + 1) if str(partido.get("num") or idx + 1).isdigit() else idx + 1
            prediccion = predicciones.get(int(jornada_num or 0), {}).get(num, {})
            pron_prediccion = signo_prediccion(prediccion)
            if pronostico_valido(pron_prediccion):
                pron = pron_prediccion
                origen = Path((pred_info or {}).get("path") or f"data/predicciones/jornada_{int(jornada_num)}.json").as_posix()
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

    cambios_premios = actualizar_historial_premios(registros_premios, temporadas_con_jugada_real())
    salida = construir_salida(resumen, fuentes_jugadas)
    guardar_json(OUT, salida)
    print(f"Aprendizaje IA generado: {OUT}")
    print(f"Jornadas cerradas comparadas con prediccion: {jornadas_cerradas_actualizadas}")
    print(f"Registros de premios actualizados: {cambios_premios}")

    # Retroalimentación de factores psicológicos
    try:
        registrar_retroalimentacion_factores()
    except Exception as exc:
        print(f"AVISO: retroalimentacion_factores no critica: {exc}")


def registrar_retroalimentacion_factores():
    """
    Analiza qué factores psicológicos/competitivos estaban activos
    en cada partido y si el resultado confirmó o contradijo el factor.
    Guarda en data/memoria_ia/retroalimentacion_factores.json
    Sin tocar ningún archivo existente de aprendizaje.
    """
    SALIDA = DATA / "memoria_ia" / "retroalimentacion_factores.json"

    # Auditoria 26/11: se cargaba el fichero anterior y se hacia casos += 1
    # recorriendo TODAS las jornadas en cada ciclo, asi que cada ejecucion del
    # pipeline habria vuelto a sumar todas las jornadas. Los contadores se
    # reconstruyen desde cero: el resultado depende solo de los datos.
    memoria = {
        "version": "1.1",
        "descripcion": "Retroalimentacion de factores psicologicos sobre resultados reales",
        "factores": {},
        "partidos_analizados": 0,
        "actualizado_en": ""
    }

    factores = memoria["factores"]
    # La prediccion que se evalua es la del cierre (snapshot), no la regenerada.
    predicciones_cierre = cargar_predicciones_detalladas_por_jornada()

    FACTORES_CONOCIDOS = {
        "ultimo_partido_orgullo": "Equipo eliminado en su ultimo partido — factor orgullo",
        "favorito_relajado_rival_desesperado": "Favorito clasificado vs rival desesperado",
        "presion_descenso": "Equipo en zona de descenso — se juega la vida",
        "presion_europea_o_ascenso": "Equipo peleando por Europa o ascenso",
        "derbi_todo_puede_pasar": "Derbi o rivalidad historica",
        "partido_sin_presion": "Ambos equipos sin objetivos — peligro de sorpresa",
        "motivacion_competitiva": "Factor motivacional competitivo activo",
    }

    for factor_key, descripcion in FACTORES_CONOCIDOS.items():
        if factor_key not in factores:
            factores[factor_key] = {
                "descripcion": descripcion,
                "casos": 0,
                "confirmo_patron": 0,
                "contradijo_patron": 0,
                "tasa_confirmacion": 0.0,
                "ejemplos": []
            }

    partidos_procesados = 0

    for path in sorted(JORNADAS.glob("jornada_*.json"), key=orden_cronologico_jornada):
        jornada_data = cargar_json(path, {})
        jornada_num = int(jornada_data.get("jornada", 0) or 0)
        if not jornada_num:
            continue

        pred_data = (predicciones_cierre.get(jornada_num) or {}).get("data") or {}
        partidos_pred = {}
        for p in (pred_data.get("partidos") or []):
            num = p.get("num") or p.get("numero")
            if num:
                try:
                    partidos_pred[int(num)] = p
                except (ValueError, TypeError):
                    pass

        for partido in jornada_data.get("partidos", []):
            signo_real = signo_oficial_partido(partido)
            if not signo_real:
                continue

            try:
                num = int(partido.get("num", 0) or 0)
            except (ValueError, TypeError):
                num = 0
            pred_partido = partidos_pred.get(num, {})

            # Recoger alertas de motivación
            alertas = []
            for campo in ("alertas_motivacion", "alertas_motivacion_detectadas",
                          "alerta_motivacion_detectada", "factores_activos"):
                valor = pred_partido.get(campo)
                if isinstance(valor, list):
                    alertas.extend(valor)
                elif isinstance(valor, str) and valor:
                    alertas.append(valor)

            ajuste = pred_partido.get("ajuste_motivacion", {})
            if isinstance(ajuste, dict):
                alertas_ajuste = ajuste.get("alertas", [])
                if isinstance(alertas_ajuste, list):
                    alertas.extend(alertas_ajuste)

            if not alertas:
                continue

            signo_pred = str(
                pred_partido.get("signo") or
                pred_partido.get("pronostico") or
                pred_partido.get("signo_predicho") or
                signo_prediccion(pred_partido) or ""
            ).strip()

            local = partido.get("local", "")
            visitante = partido.get("visitante", "")

            for alerta in alertas:
                if alerta not in factores:
                    continue

                factor = factores[alerta]

                # Lógica de confirmación por tipo de factor
                if alerta == "ultimo_partido_orgullo":
                    confirma = signo_real in ("X", "2") if signo_pred == "1" else signo_real in ("X", "1")
                elif alerta == "favorito_relajado_rival_desesperado":
                    confirma = signo_real != signo_pred
                elif alerta == "presion_descenso":
                    confirma = signo_real == "1"
                elif alerta == "derbi_todo_puede_pasar":
                    confirma = signo_real == "X"
                elif alerta == "partido_sin_presion":
                    confirma = signo_real != signo_pred
                else:
                    confirma = signo_real == signo_pred

                factor["casos"] += 1
                if confirma:
                    factor["confirmo_patron"] += 1
                else:
                    factor["contradijo_patron"] += 1

                if len(factor["ejemplos"]) < 5:
                    factor["ejemplos"].append({
                        "jornada": jornada_num,
                        "partido": f"{local} vs {visitante}",
                        "resultado_real": signo_real,
                        "predicho": signo_pred,
                        "confirmo": confirma
                    })

                factor["tasa_confirmacion"] = round(
                    factor["confirmo_patron"] / factor["casos"] * 100, 1
                ) if factor["casos"] > 0 else 0.0

                partidos_procesados += 1

    memoria["partidos_analizados"] = partidos_procesados
    memoria["actualizado_en"] = ahora_iso()
    guardar_json(SALIDA, memoria)

    print(f"\n=== Retroalimentacion factores: {partidos_procesados} casos ===")
    for key, f in factores.items():
        if f["casos"] > 0:
            print(f"  {key}: {f['casos']} casos | "
                  f"confirma={f['confirmo_patron']} | "
                  f"contradice={f['contradijo_patron']} | "
                  f"tasa={f['tasa_confirmacion']}%")


if __name__ == "__main__":
    main()
