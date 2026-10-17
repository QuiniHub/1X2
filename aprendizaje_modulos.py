"""Meta-aprendizaje por modulo (15/10/2026, aprobado por Marc).

Cada modulo con promesa propia (Dixon-Coles, boleto EV del premio, La
Valiente, revulsivo) lleva su CUADERNO: que prometio, que entrego jornada a
jornada, medido con datos estrictamente pre-cierre (snapshots inmutables de
data/backtesting/pre_cierre + % LAE versionados, sin fuga de futuro). Del
cuaderno salen tres cosas, cada una con su freno escrito aqui y en
DECISION_LOG.md:

1) CUADERNO (data/memoria_ia/aprendizaje_modulos.json): por jornada cerrada,
   - dixon_coles: D-C re-entrenado a la vispera (patron test_b del backtest),
     RPS propio vs motor completo vs mercado Losilla, aciertos, sesgo por signo;
   - boleto_ev: signos propuestos, aciertos y premio hipotetico con la TABLA
     REAL del escrutinio (calcular_premio_multicolumna), vs la conservadora y
     vs lo realmente jugado (quinielas_jugadas.json, solo lectura);
   - valiente: la fila del marcador de sombra (o del backtest prerregistrado
     mientras el marcador se estrena);
   - revulsivo: cada caso activado, con resultado y veredicto ayudo/neutro/
     perjudico segun la direccion del empuje vs el signo real.

2) AUTO-CORRECCIONES ACOTADAS (solo parametros finos; NINGUN parametro
   estructural -peso D-C, umbrales/vetos de la Valiente- se auto-cambia):
   - factor de overdispersion de acertantes del reparto EV: mediana
     real/modelo sobre celdas con >=10 acertantes reales, SOLO con >=10
     escrutinios, acotado a [0,5x - 2x] (data/memoria_ia/
     ajustes_automaticos.json, lo lee optimizador_ev_premio.py);
   - re-estimacion del efecto revulsivo: añade los casos 26/27 al estudio
     base (70 ceses 23/24-25/26) SOLO con >=10 casos nuevos por lado,
     acotado a +-8 puntos (bloque reestimacion_2627 de efecto_revulsivo.json,
     lo lee el motor);
   - suspension por señal de La Valiente: vive en senal_valiente.py
     (>=8 valientes propias y aciertos < 50% de esperados).

3) AUTO-AUDITORIA CON PUERTA (cada 5 jornadas cerradas, data/memoria_ia/
   auditoria_automatica.json): re-corre los barridos prerregistrados -peso
   Dixon-Coles sobre la era-D-C acumulada (umbral de mejora RPS > 0,002 con
   >=60 partidos, DECISION_LOG 13/10) y los vetos v2 de La Valiente POR
   SEPARADO (veto grandes y veto 55% independientes, con >=25 jornadas y la
   regla de despliegue de DECISION_LOG 14/10)- y escribe "sin cambios" o
   "CANDIDATO A CAMBIO: que, numeros, umbral" SIN aplicar nada. Decide Marc.
"""
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from actualizar_porcentajes_lae import ruta_porcentajes, temporada_etiqueta
from calcular_premios import calcular_premio_multicolumna, tipo_por_signo
from generar_artefactos_compuerta_aprendizaje import rps_partido
from modelo_dixon_coles import DixonColes, cargar_partidos
from modelo_reparto_quiniela import PRECIO_APUESTA, distribucion_aciertos_masa
from optimizador_ev_premio import cargar_json, guardar_json

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORIA = DATA / "memoria_ia"
CUADERNO = MEMORIA / "aprendizaje_modulos.json"
AUDITORIA = MEMORIA / "auditoria_automatica.json"
AJUSTES = MEMORIA / "ajustes_automaticos.json"
EFECTO_REVULSIVO = MEMORIA / "efecto_revulsivo.json"
MARCADOR_VALIENTE = MEMORIA / "marcador_valiente.json"
BACKTEST_VALIENTE = MEMORIA / "backtest_valiente.json"
BACKTEST_EV = MEMORIA / "backtest_ev_premio.json"
QUINIELAS_JUGADAS = DATA / "quinielas_jugadas.json"
METRICAS_PROBABILISTICAS = MEMORIA / "metricas_probabilisticas.json"
PRE_CIERRE = DATA / "backtesting" / "pre_cierre"
JORNADAS = DATA / "jornadas"
PREDICCIONES = DATA / "predicciones"

SIGNOS = ("1", "X", "2")
CATEGORIAS = (10, 11, 12, 13, 14)

# --- Frenos prerregistrados (escritos ANTES de mirar los datos; ver
# DECISION_LOG.md 15/10/2026. No se tocan sin nuevo prerregistro). ---
OVERDISPERSION_MIN_ESCRUTINIOS = 10
OVERDISPERSION_RANGO = (0.5, 2.0)
OVERDISPERSION_MIN_ACERTANTES_CELDA = 10
REVULSIVO_MIN_CASOS_NUEVOS = 10
REVULSIVO_EFECTO_MAX_PTS = 8.0
AUDITORIA_CADA_JORNADAS = 5
AUDITORIA_DC_UMBRAL_RPS = 0.002       # DECISION_LOG 13/10: mejora minima real
AUDITORIA_DC_MIN_PARTIDOS = 60        # DECISION_LOG 13/10: ~60 partidos era-D-C
AUDITORIA_VETOS_MIN_JORNADAS = 25     # DECISION_LOG 14/10: re-probar con ~25
VERSION_CALCULO_DC = 1                # subirla fuerza recalcular filas D-C cacheadas
FIJOS_BANDA_N_MINIMO = 30             # DECISION_LOG 17/10: una banda solo "promete" con n>=30
FIJOS_BANDA_MUESTRA_MINIMA = 10       # con menos fijos evaluados, el semaforo se queda en ambar

# Estudio base del revulsivo (70 ceses 23/24-25/26, efecto_revulsivo.json):
# el efecto en puntos se mapeo linealmente desde sorpresa_vs_mercado_media
# (+0,26 fuera -> +5 pts; -0,48 en casa -> 3,5 pts de recorte). La
# re-estimacion agrega los casos 26/27 a ese pool con el MISMO factor de
# conversion -nada de inventar un mapeo nuevo despues de ver los datos.
BASE_REVULSIVO = {
    "fuera": {"casos": 33, "sorpresa_media": 0.26, "pts": 5.0},
    "casa": {"casos": 37, "sorpresa_media": -0.48, "pts": 3.5},
}

FRENOS_TEXTO = {
    "factor_acertantes": (
        f"Solo con >={OVERDISPERSION_MIN_ESCRUTINIOS} escrutinios reales; mediana real/modelo "
        f"sobre celdas con >={OVERDISPERSION_MIN_ACERTANTES_CELDA} acertantes; acotado a "
        f"[{OVERDISPERSION_RANGO[0]}x - {OVERDISPERSION_RANGO[1]}x]."
    ),
    "revulsivo": (
        f"Solo con >={REVULSIVO_MIN_CASOS_NUEVOS} casos nuevos 26/27 por lado; se agregan al "
        f"estudio base (70 ceses) con su factor de conversion; acotado a +-{REVULSIVO_EFECTO_MAX_PTS:.0f} pts."
    ),
    "valiente": (
        "Una señal con >=8 valientes propias y aciertos < 50% de esperados se suspende sola "
        "(senal_valiente.py) y se anuncia. Ningun umbral estructural se auto-cambia."
    ),
    "auditoria": (
        f"Cada {AUDITORIA_CADA_JORNADAS} jornadas cerradas; peso D-C: candidato solo con mejora "
        f"RPS > {AUDITORIA_DC_UMBRAL_RPS} y >={AUDITORIA_DC_MIN_PARTIDOS} partidos era-D-C; vetos "
        f"Valiente por separado: candidato solo con >={AUDITORIA_VETOS_MIN_JORNADAS} jornadas, "
        "veredicto VERDE y ratio >= al del criterio vivo. NUNCA aplica nada: decide Marc."
    ),
}


def ahora_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Fuentes por jornada (todas pre-cierre; el fixture oficial solo aporta el
# signo real, que es justo lo que se evalua)
# ---------------------------------------------------------------------------

def fixture_jornada(jornada, dir_jornadas=None):
    datos = cargar_json(Path(dir_jornadas or JORNADAS) / f"jornada_{jornada}.json", {})
    fixture = {}
    for p in datos.get("partidos") or []:
        num = p.get("num")
        if isinstance(num, int) and 1 <= num <= 14:
            fixture[num] = {
                "local": p.get("local"),
                "visitante": p.get("visitante"),
                "fecha": p.get("fecha"),
                "signo_oficial": str(p.get("signo_oficial") or "").upper(),
            }
    return fixture


def jornada_cerrada(fixture):
    return len(fixture) == 14 and all(f["signo_oficial"] in SIGNOS for f in fixture.values())


def snapshot_prediccion(jornada, dir_pre_cierre=None):
    datos = cargar_json(Path(dir_pre_cierre or PRE_CIERRE) / f"jornada_{jornada}.json", {})
    return datos.get("prediccion") or {}


def partidos_snapshot(prediccion):
    return sorted(
        [p for p in prediccion.get("partidos") or []
         if isinstance(p.get("num"), int) and 1 <= p["num"] <= 14],
        key=lambda p: p["num"],
    )


def jornadas_cerradas_temporada(etiqueta, hasta=60, dir_jornadas=None):
    """Jornadas de ESTA temporada (filtradas por % LAE versionados, el mismo
    truco anti-reinicio-de-numeracion que senal_valiente) ya cerradas con los
    14 signos oficiales."""
    cerradas = []
    for j in range(1, hasta + 1):
        if not ruta_porcentajes(j, etiqueta).exists():
            continue
        if jornada_cerrada(fixture_jornada(j, dir_jornadas)):
            cerradas.append(j)
    return cerradas


def fecha_corte_jornada(fixture):
    """Vispera de la jornada: el dia del primer partido a las 00:00 (los
    partidos de ese mismo dia quedan FUERA del entrenamiento walk-forward)."""
    fechas = []
    for f in fixture.values():
        try:
            fechas.append(datetime.strptime(str(f.get("fecha") or "")[:10], "%Y-%m-%d"))
        except ValueError:
            continue
    return min(fechas) if fechas else None


# ---------------------------------------------------------------------------
# (a) Cuaderno Dixon-Coles
# ---------------------------------------------------------------------------

def fila_dixon_coles(partidos, fixture, modelo):
    """Evalua D-C walk-forward contra el motor completo (probabilidades del
    snapshot pre-cierre) y el mercado Losilla (campo mercado_losilla del
    mismo snapshot) sobre los partidos que el modelo cubre."""
    evaluados = []
    sin_cobertura = 0
    for p in partidos:
        signo_real = (fixture.get(p["num"]) or {}).get("signo_oficial")
        if signo_real not in SIGNOS:
            continue
        dc = modelo.probabilidades(p.get("local"), p.get("visitante")) if modelo else None
        if dc is None:
            sin_cobertura += 1
            continue
        evaluados.append({
            "dc": {s: float(dc[s]) * 100.0 for s in SIGNOS},
            "motor": p.get("probabilidades") or {},
            "mercado": p.get("mercado_losilla") or {},
            "real": signo_real,
        })
    if not evaluados:
        return {
            "estado": "sin_cobertura",
            "partidos": 0,
            "sin_cobertura": sin_cobertura,
            "motivo": "Dixon-Coles no cubre ningun partido de la jornada (selecciones/ligas extranjeras).",
            "version_calculo": VERSION_CALCULO_DC,
        }

    def _evaluar(clave):
        rps_valores, aciertos, n = [], 0, 0
        for e in evaluados:
            probs = e[clave]
            r = rps_partido(probs, e["real"])
            if r is None:
                continue
            rps_valores.append(r)
            if max(SIGNOS, key=lambda s: float(probs.get(s) or 0)) == e["real"]:
                aciertos += 1
            n += 1
        if not n:
            return None, None, 0
        return round(sum(rps_valores) / n, 5), aciertos, n

    rps_dc, aciertos_dc, n_dc = _evaluar("dc")
    rps_motor, aciertos_motor, _ = _evaluar("motor")
    rps_mercado, aciertos_mercado, n_mercado = _evaluar("mercado")

    sesgo = {}
    for s in SIGNOS:
        prob_media = sum(e["dc"][s] for e in evaluados) / len(evaluados)
        frecuencia = 100.0 * sum(1 for e in evaluados if e["real"] == s) / len(evaluados)
        sesgo[s] = {
            "prob_media": round(prob_media, 1),
            "frecuencia_real_pct": round(frecuencia, 1),
            "sesgo_puntos": round(prob_media - frecuencia, 1),
        }
    return {
        "estado": "ok",
        "partidos": n_dc,
        "sin_cobertura": sin_cobertura,
        "rps_dc": rps_dc,
        "rps_motor": rps_motor,
        "rps_mercado": rps_mercado,
        "partidos_con_mercado": n_mercado,
        "aciertos_dc": aciertos_dc,
        "aciertos_motor": aciertos_motor,
        "aciertos_mercado": aciertos_mercado,
        "sesgo_dc_por_signo": sesgo,
        "version_calculo": VERSION_CALCULO_DC,
    }


# ---------------------------------------------------------------------------
# (b) Cuaderno boleto EV del premio
# ---------------------------------------------------------------------------

def _fecha_validado(valor):
    texto = str(valor or "").strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto.split(",")[0].split("T")[0].strip(), formato)
        except ValueError:
            continue
    return None


def jugada_temporada(jornada, etiqueta, datos_jugadas=None):
    """Signos realmente jugados de la jornada DE ESTA temporada (la numeracion
    se reinicia: el filtro es la fecha de validacion, no el numero)."""
    datos = datos_jugadas if datos_jugadas is not None else cargar_json(QUINIELAS_JUGADAS, {})
    for jugada in datos.get("jugadas") or []:
        if jugada.get("jornada") != jornada:
            continue
        fecha = _fecha_validado(jugada.get("validado_en"))
        if fecha is None or temporada_etiqueta(fecha) != etiqueta:
            continue
        signos = [str(s or "").strip().upper() for s in (jugada.get("signos") or [])[:14]]
        if len(signos) == 14:
            return signos
    return None


def tabla_real_jornada(jornada, etiqueta):
    """Tabla de premios por apuesta del escrutinio REAL capturado (10-14).
    None si la jornada aun no tiene escrutinio versionado."""
    registro = cargar_json(ruta_porcentajes(jornada, etiqueta), {})
    categorias = (registro.get("escrutinio") or {}).get("categorias") or {}
    tabla = {}
    for cat in CATEGORIAS:
        premio = (categorias.get(str(cat)) or {}).get("premio_eur")
        if isinstance(premio, (int, float)):
            tabla[str(cat)] = float(premio)
    return tabla if len(tabla) == len(CATEGORIAS) else None


def _prediccion_desde_signos(signos):
    return {
        "partidos": [
            {"num": i, "signo_base": s, "signo_final": s, "tipo": tipo_por_signo(s)}
            for i, s in enumerate(signos, start=1)
        ]
    }


def _resultados_desde_fixture(fixture):
    return {
        "partidos": [
            {"num": num, "signo_oficial": f["signo_oficial"]}
            for num, f in sorted(fixture.items())
        ]
    }


def _aciertos_boleto(signos, fixture):
    aciertos = 0
    for i, s in enumerate(signos, start=1):
        real = (fixture.get(i) or {}).get("signo_oficial")
        if real in SIGNOS and real in str(s or "").upper():
            aciertos += 1
    return aciertos


def _apuestas_boleto(signos):
    total = 1
    for s in signos:
        total *= max(len([c for c in SIGNOS if c in str(s or "").upper()]), 1)
    return total


def _premio_tabla_real(signos, fixture, tabla):
    if not signos or not tabla:
        return None
    resultado = calcular_premio_multicolumna(
        _prediccion_desde_signos(signos), _resultados_desde_fixture(fixture), tabla
    )
    return round(float(resultado["total"]), 2) if resultado else 0.0


def boleto_ev_de_jornada(jornada, prediccion_snapshot, backtest_ev=None):
    """(signos, fuente): el bloque boleto_ev_premio del snapshot pre-cierre
    (desde la J14, ya congelado antes del cierre) o, para las jornadas previas
    al candidato 3, la reconstruccion walk-forward del backtest prerregistrado."""
    bloque = prediccion_snapshot.get("boleto_ev_premio") or {}
    if bloque.get("estado") == "ok":
        partidos = sorted(
            [p for p in bloque.get("partidos") or [] if isinstance(p.get("num"), int)],
            key=lambda p: p["num"],
        )
        if len(partidos) == 14:
            return [str(p.get("signo") or "").upper() for p in partidos], "snapshot_pre_cierre"
    backtest = backtest_ev if backtest_ev is not None else cargar_json(BACKTEST_EV, {})
    for fila in (backtest.get("test_b_ev_walk_forward") or {}).get("detalle") or []:
        if fila.get("jornada") == jornada and len(fila.get("boleto_ev") or []) == 14:
            return [str(s).upper() for s in fila["boleto_ev"]], "backtest_ev_premio (reconstruido walk-forward)"
    return None, None


def fila_boleto_ev(jornada, fixture, prediccion_snapshot, etiqueta,
                   backtest_ev=None, datos_jugadas=None, tabla=None):
    signos_ev, fuente = boleto_ev_de_jornada(jornada, prediccion_snapshot, backtest_ev)
    if not signos_ev:
        return {
            "estado": "sin_boleto_ev",
            "motivo": "Jornada sin bloque boleto_ev_premio pre-cierre ni fila en el backtest.",
        }
    partidos = partidos_snapshot(prediccion_snapshot)
    signos_conservador = [
        str(p.get("signo_final") or p.get("signo_base") or "").upper() for p in partidos
    ] if len(partidos) == 14 else None
    signos_jugado = jugada_temporada(jornada, etiqueta, datos_jugadas)
    if tabla is None:
        tabla = tabla_real_jornada(jornada, etiqueta)
    fila = {
        "estado": "ok",
        "fuente_boleto_ev": fuente,
        "signos_ev": signos_ev,
        "apuestas_ev": _apuestas_boleto(signos_ev),
        "aciertos_ev": _aciertos_boleto(signos_ev, fixture),
        "aciertos_conservador": _aciertos_boleto(signos_conservador, fixture) if signos_conservador else None,
        "aciertos_jugado": _aciertos_boleto(signos_jugado, fixture) if signos_jugado else None,
        "nota": (
            "Premios hipoteticos de quiniela (categorias 10-14) con la tabla REAL del "
            "escrutinio; sin Elige 8 ni Pleno al 15, igual para los tres boletos."
        ),
    }
    if tabla:
        fila["premios_tabla_real_eur"] = {
            "ev": _premio_tabla_real(signos_ev, fixture, tabla),
            "conservador": _premio_tabla_real(signos_conservador, fixture, tabla) if signos_conservador else None,
            "jugado": _premio_tabla_real(signos_jugado, fixture, tabla) if signos_jugado else None,
        }
    else:
        fila["premios_tabla_real_eur"] = None
        fila["motivo_sin_premios"] = "Sin escrutinio real capturado todavia para esta jornada."
    return fila


# ---------------------------------------------------------------------------
# (c) Cuaderno La Valiente (la atribucion POR SEÑAL vive en el marcador,
# senal_valiente._atribucion_por_senal; aqui solo se copia la fila)
# ---------------------------------------------------------------------------

def fila_valiente(jornada, etiqueta, marcador=None, backtest=None):
    marcador = marcador if marcador is not None else cargar_json(MARCADOR_VALIENTE, {})
    for v in marcador.get("valientes") or []:
        if v.get("jornada") == jornada and v.get("temporada") == etiqueta:
            return {"estado": "valiente", "fuente": "marcador_sombra", **{
                k: v.get(k) for k in ("partido", "signo", "prob_declarada", "masa_pct",
                                      "senales", "signo_real", "acierto", "pago_hipotetico_eur")
            }}
    backtest = backtest if backtest is not None else cargar_json(BACKTEST_VALIENTE, {})
    for fila in backtest.get("jornadas") or []:
        if fila.get("jornada") != jornada:
            continue
        if fila.get("estado") == "valiente":
            return {"estado": "valiente", "fuente": "backtest_prerregistrado", **{
                k: fila.get(k) for k in ("partido", "signo", "prob_declarada", "masa_pct",
                                         "senales", "signo_real", "acierto", "pago_hipotetico_eur")
            }}
        return {"estado": fila.get("estado"), "fuente": "backtest_prerregistrado"}
    return {"estado": "sin_dato", "fuente": None}


# ---------------------------------------------------------------------------
# (d) Cuaderno revulsivo
# ---------------------------------------------------------------------------

def _puntos_por_signo(signo_real, signo_equipo):
    if signo_real == signo_equipo:
        return 3.0
    if signo_real == "X":
        return 1.0
    return 0.0


def veredicto_revulsivo(lado, signo_real):
    """Direccion del empuje vs signo real. Fuera (sube el 2 del equipo):
    ayudo si salio 2, neutro si X (el recorte a la X fue menor, -0,3),
    perjudico si 1. En casa (recorta el 1 del equipo, sube rival y X):
    ayudo si NO salio el equipo, perjudico si salio (el recorte estorbo)."""
    if lado == "visitante":
        return {"2": "ayudo", "X": "neutro", "1": "perjudico"}.get(signo_real, "pendiente")
    if lado == "local":
        return {"1": "perjudico", "X": "ayudo", "2": "ayudo"}.get(signo_real, "pendiente")
    return "pendiente"


def fila_revulsivo(partidos, fixture):
    """Casos de revulsivo activados en la prediccion pre-cierre de la jornada,
    cada uno con su resultado y veredicto. `partidos` debe traer la traza
    ajuste_revulsivo (snapshot pre-cierre o, si el snapshot es anterior al
    modulo, el espejo de prediccion de la jornada)."""
    if not any("ajuste_revulsivo" in p for p in partidos):
        return {
            "estado": "sin_traza",
            "motivo": "La prediccion de esta jornada es anterior al modulo revulsivo (06/10/2026).",
            "casos": [],
        }
    casos = []
    for p in partidos:
        traza = p.get("ajuste_revulsivo") or {}
        if not traza.get("activo"):
            continue
        lado = traza.get("lado")
        signo_equipo = "1" if lado == "local" else "2"
        signo_real = (fixture.get(p["num"]) or {}).get("signo_oficial")
        signo_real = signo_real if signo_real in SIGNOS else None
        mercado = p.get("mercado_losilla") or {}
        sorpresa = None
        if signo_real and all(mercado.get(s) is not None for s in SIGNOS):
            total = sum(float(mercado[s]) for s in SIGNOS) or 1.0
            p_gana = float(mercado[signo_equipo]) / total
            p_empata = float(mercado["X"]) / total
            esperado = 3.0 * p_gana + p_empata
            sorpresa = round(_puntos_por_signo(signo_real, signo_equipo) - esperado, 2)
        casos.append({
            "num": p["num"],
            "partido": f"{p.get('local')} - {p.get('visitante')}",
            "equipo": traza.get("equipo"),
            "lado": lado,
            "etapa": traza.get("etapa"),
            "tecnico": traza.get("tecnico"),
            "signo_real": signo_real,
            "veredicto": veredicto_revulsivo(lado, signo_real) if signo_real else "pendiente",
            "sorpresa_vs_mercado": sorpresa,
        })
    return {"estado": "ok", "casos": casos}


def partidos_con_traza_revulsivo(jornada, prediccion_snapshot, dir_predicciones=None):
    """Partidos con la traza ajuste_revulsivo: el snapshot pre-cierre si ya la
    trae; si el snapshot es anterior al modulo (se congela al cerrar la
    jornada previa), el espejo de prediccion de la MISMA jornada. La traza
    depende solo de ceses y calendario pre-partido: sin fuga de futuro."""
    partidos = partidos_snapshot(prediccion_snapshot)
    if any("ajuste_revulsivo" in p for p in partidos):
        return partidos, "snapshot_pre_cierre"
    espejo = cargar_json(Path(dir_predicciones or PREDICCIONES) / f"jornada_{jornada}.json", {})
    if espejo.get("jornada") == jornada:
        partidos_espejo = partidos_snapshot(espejo)
        if any("ajuste_revulsivo" in p for p in partidos_espejo):
            return partidos_espejo, "espejo_prediccion"
    return partidos, "snapshot_pre_cierre"


# ---------------------------------------------------------------------------
# Auto-correccion 1: factor de overdispersion de acertantes (reparto EV)
# ---------------------------------------------------------------------------

def celdas_overdispersion(escrutinios):
    """escrutinios: lista de {pcts: [14 dicts], signos: [14], recaudacion_eur,
    categorias: {"10": {acertantes...}}}. Devuelve los ratios real/modelo de
    las celdas con >=10 acertantes reales (las pequeñas son puro ruido)."""
    ratios = []
    for e in escrutinios:
        dist = distribucion_aciertos_masa(e["pcts"], e["signos"])
        apuestas = float(e["recaudacion_eur"]) / PRECIO_APUESTA
        for cat in CATEGORIAS:
            real = ((e.get("categorias") or {}).get(str(cat)) or {}).get("acertantes")
            if not isinstance(real, (int, float)) or real < OVERDISPERSION_MIN_ACERTANTES_CELDA:
                continue
            modelo = apuestas * dist[cat]
            if modelo > 0:
                ratios.append(float(real) / modelo)
    return ratios


def calcular_factor_overdispersion(escrutinios):
    """Freno prerregistrado: sin ajuste (factor 1,0) con <10 escrutinios;
    con >=10, mediana de los ratios acotada a [0,5x - 2x]."""
    ratios = celdas_overdispersion(escrutinios)
    n = len(escrutinios)
    if n < OVERDISPERSION_MIN_ESCRUTINIOS:
        return {
            "estado": "sin_ajuste",
            "valor": 1.0,
            "escrutinios": n,
            "celdas": len(ratios),
            "motivo": (
                f"Freno: hacen falta >={OVERDISPERSION_MIN_ESCRUTINIOS} escrutinios reales "
                f"y hay {n}."
            ),
            "freno": FRENOS_TEXTO["factor_acertantes"],
        }
    mediana = statistics.median(ratios) if ratios else 1.0
    valor = min(max(mediana, OVERDISPERSION_RANGO[0]), OVERDISPERSION_RANGO[1])
    return {
        "estado": "ajustado",
        "valor": round(valor, 3),
        "mediana_sin_acotar": round(mediana, 3),
        "escrutinios": n,
        "celdas": len(ratios),
        "freno": FRENOS_TEXTO["factor_acertantes"],
    }


def escrutinios_temporada(etiqueta, jornadas):
    escrutinios = []
    for j in jornadas:
        registro = cargar_json(ruta_porcentajes(j, etiqueta), {})
        escrutinio = registro.get("escrutinio") or {}
        categorias = escrutinio.get("categorias") or {}
        recaudacion = escrutinio.get("recaudacion_eur")
        partidos = {
            p.get("numero"): p.get("porcentajes")
            for p in registro.get("partidos") or []
            if isinstance(p.get("numero"), int) and p.get("porcentajes")
        }
        fixture = fixture_jornada(j)
        if not categorias or not recaudacion or len(partidos) < 14 or not jornada_cerrada(fixture):
            continue
        escrutinios.append({
            "jornada": j,
            "pcts": [partidos[n] for n in range(1, 15)],
            "signos": [fixture[n]["signo_oficial"] for n in range(1, 15)],
            "recaudacion_eur": recaudacion,
            "categorias": categorias,
        })
    return escrutinios


def actualizar_factor_overdispersion(etiqueta, jornadas, ahora=None, ruta=None):
    bloque = calcular_factor_overdispersion(escrutinios_temporada(etiqueta, jornadas))
    ruta = Path(ruta or AJUSTES)
    datos = cargar_json(ruta, {})
    anterior = (datos.get("factor_acertantes") or {}).get("valor")
    bloque["actualizado_en"] = ahora or ahora_iso()
    historial = (datos.get("factor_acertantes") or {}).get("historial") or []
    if anterior != bloque["valor"]:
        historial.append({
            "fecha": bloque["actualizado_en"],
            "valor": bloque["valor"],
            "escrutinios": bloque["escrutinios"],
            "celdas": bloque["celdas"],
        })
    bloque["historial"] = historial[-20:]
    datos.update({
        "version": 1,
        "descripcion": (
            "Auto-correcciones acotadas del meta-aprendizaje (15/10/2026). Cada una lleva su "
            "freno prerregistrado escrito; ningun parametro estructural se auto-cambia."
        ),
        "actualizado_en": bloque["actualizado_en"],
        "factor_acertantes": bloque,
    })
    guardar_json(ruta, datos)
    return bloque


# ---------------------------------------------------------------------------
# Auto-correccion 2: re-estimacion del efecto revulsivo (26/27 sobre el base)
# ---------------------------------------------------------------------------

def reestimar_efecto_revulsivo(casos, base=None):
    """casos: filas del cuaderno revulsivo (con lado y sorpresa_vs_mercado).
    Freno prerregistrado: solo lados con >=10 casos nuevos; el efecto re-estimado
    agrega 26/27 al estudio base con el factor de conversion original y queda
    acotado a +-8 pts. Devuelve el bloque reestimacion_2627 (o estado sin_ajuste)."""
    base = base or BASE_REVULSIVO
    por_lado = {"fuera": [], "casa": []}
    for c in casos:
        lado = {"visitante": "fuera", "local": "casa"}.get(c.get("lado"))
        if lado and isinstance(c.get("sorpresa_vs_mercado"), (int, float)):
            por_lado[lado].append(float(c["sorpresa_vs_mercado"]))
    bloque = {
        "descripcion": (
            "Re-estimacion automatica del efecto revulsivo agregando los casos 26/27 al estudio "
            "base (70 ceses 23/24-25/26) con su mismo factor de conversion pts/sorpresa."
        ),
        "freno": FRENOS_TEXTO["revulsivo"],
        "casos_nuevos": {lado: len(valores) for lado, valores in por_lado.items()},
        "estado": "sin_ajuste",
    }
    for lado, campo, signo_pts in (("fuera", "debut_fuera_pts", 1.0), ("casa", "debut_casa_pts", 1.0)):
        valores = por_lado[lado]
        if len(valores) < REVULSIVO_MIN_CASOS_NUEVOS:
            continue
        b = base[lado]
        conversion = b["pts"] / b["sorpresa_media"] if b["sorpresa_media"] else 0.0
        pool = (b["casos"] * b["sorpresa_media"] + sum(valores)) / (b["casos"] + len(valores))
        pts = max(-REVULSIVO_EFECTO_MAX_PTS, min(REVULSIVO_EFECTO_MAX_PTS, pool * conversion * signo_pts))
        bloque[campo] = round(pts, 2)
        bloque[f"sorpresa_media_2627_{lado}"] = round(sum(valores) / len(valores), 3)
        bloque["estado"] = "ajustado"
    if bloque["estado"] == "sin_ajuste":
        bloque["motivo"] = (
            f"Freno: hacen falta >={REVULSIVO_MIN_CASOS_NUEVOS} casos nuevos 26/27 por lado "
            f"(hay fuera={len(por_lado['fuera'])}, casa={len(por_lado['casa'])})."
        )
    return bloque


def actualizar_reestimacion_revulsivo(casos, ahora=None, ruta=None):
    bloque = reestimar_efecto_revulsivo(casos)
    bloque["actualizado_en"] = ahora or ahora_iso()
    ruta = Path(ruta or EFECTO_REVULSIVO)
    datos = cargar_json(ruta, {})
    datos["reestimacion_2627"] = bloque
    guardar_json(ruta, datos)
    return bloque


# ---------------------------------------------------------------------------
# Resumen por modulo + semaforos (la web los pinta tal cual; la logica vive
# aqui para que este testeada, no en el navegador)
# ---------------------------------------------------------------------------

def _fmt(valor, dec=2):
    if valor is None:
        return "—"
    return f"{valor:.{dec}f}".replace(".", ",")


def resumen_dixon_coles(filas, ultimo_ajuste=None):
    """Promesa del D-C: igualar o batir al mercado en RPS (menor = mejor)."""
    con_datos = [f for f in filas if f.get("estado") == "ok" and f.get("partidos")]
    if not con_datos:
        return {
            "semaforo": "ambar", "texto_semaforo": "en vigilancia: sin partidos evaluables aun",
            "titular": "sin datos", "valor": None, "comparacion": None,
            "promesa": "Igualar o batir al mercado en RPS (menor = mejor).",
            "ultimo_ajuste": ultimo_ajuste,
        }
    def _media(clave, peso):
        pares = [(f[clave], f[peso]) for f in con_datos if f.get(clave) is not None and f.get(peso)]
        total = sum(p for _, p in pares)
        return round(sum(v * p for v, p in pares) / total, 5) if total else None
    rps_dc = _media("rps_dc", "partidos")
    rps_mercado = _media("rps_mercado", "partidos_con_mercado")
    rps_motor = _media("rps_motor", "partidos")
    n = sum(f["partidos"] for f in con_datos)
    if rps_mercado is None:
        semaforo, texto = "ambar", "en vigilancia: sin mercado comparable"
    elif rps_dc is not None and rps_dc <= rps_mercado:
        semaforo, texto = "verde", "cumple su promesa: iguala o bate al mercado"
    elif rps_dc is not None and rps_dc <= rps_mercado + 0.01:
        semaforo, texto = "ambar", "en vigilancia: pegado al mercado, sin batirlo"
    else:
        semaforo, texto = "rojo", "bajo promesa: pierde contra el mercado"
    return {
        "semaforo": semaforo, "texto_semaforo": texto,
        "titular": f"RPS {_fmt(rps_dc, 3)} vs mercado {_fmt(rps_mercado, 3)}",
        "valor": rps_dc, "comparacion": rps_mercado, "rps_motor": rps_motor,
        "partidos": n,
        "promesa": "Igualar o batir al mercado en RPS (menor = mejor; referencia mundial 0,19-0,21).",
        "ultimo_ajuste": ultimo_ajuste,
    }


def resumen_boleto_ev(filas, ultimo_ajuste=None):
    """Promesa honesta del EV (umbral de sanidad prerregistrado del backtest):
    cobrar al menos el 50% de lo que cobro lo realmente jugado."""
    con_premios = [f for f in filas if f.get("estado") == "ok" and f.get("premios_tabla_real_eur")]
    ev = sum(f["premios_tabla_real_eur"].get("ev") or 0 for f in con_premios)
    jugado = sum(f["premios_tabla_real_eur"].get("jugado") or 0 for f in con_premios)
    conservador = sum(f["premios_tabla_real_eur"].get("conservador") or 0 for f in con_premios)
    if not con_premios:
        return {
            "semaforo": "ambar", "texto_semaforo": "en vigilancia: sin escrutinios comparables aun",
            "titular": "sin datos", "valor": None, "comparacion": None,
            "promesa": "Umbral de sanidad prerregistrado: cobrar >=50% de lo realmente jugado.",
            "ultimo_ajuste": ultimo_ajuste,
        }
    if ev >= jugado:
        semaforo, texto = "verde", "cumple su promesa: cobraria mas que lo jugado"
    elif jugado > 0 and ev >= 0.5 * jugado:
        semaforo, texto = "ambar", "en vigilancia: >=50% de lo jugado (umbral de sanidad)"
    else:
        semaforo, texto = "rojo", "bajo promesa: <50% de lo jugado (estrategia de cola sin cola aun)"
    return {
        "semaforo": semaforo, "texto_semaforo": texto,
        "titular": f"{_fmt(ev)} € hipoteticos vs {_fmt(jugado)} € nuestros",
        "valor": round(ev, 2), "comparacion": round(jugado, 2),
        "conservador_eur": round(conservador, 2),
        "jornadas": len(con_premios),
        "promesa": (
            "Maximizar euros, no aciertos. Umbral de sanidad prerregistrado: cobrar >=50% de lo "
            "realmente jugado (es estrategia de cola: pierde premios pequeños a cambio de colas raras)."
        ),
        "ultimo_ajuste": ultimo_ajuste,
    }


def resumen_valiente(marcador=None, backtest=None, ultimo_ajuste=None):
    marcador = marcador if marcador is not None else cargar_json(MARCADOR_VALIENTE, {})
    backtest = backtest if backtest is not None else cargar_json(BACKTEST_VALIENTE, {})
    resumen_m = marcador.get("resumen") or {}
    suspendidas = resumen_m.get("senales_suspendidas") or []
    if resumen_m.get("evaluadas"):
        aciertos, esperados = resumen_m.get("aciertos", 0), resumen_m.get("esperados", 0)
        fuente, evaluadas = "marcador de sombra", resumen_m.get("evaluadas")
        estado = resumen_m.get("estado")
    else:
        resumen_b = backtest.get("resumen") or {}
        aciertos, esperados = resumen_b.get("aciertos", 0), resumen_b.get("esperados", 0)
        fuente, evaluadas = "backtest prerregistrado", resumen_b.get("valientes", 0)
        estado = "en_sombra"
    if suspendidas or estado == "suspendida":
        semaforo = "rojo"
        texto = ("suspendida" if estado == "suspendida"
                 else "señal(es) suspendida(s): " + ", ".join(suspendidas))
    elif estado == "candidata_a_dinero":
        semaforo, texto = "verde", "cumple su promesa: candidata a dinero (avisar a Marc)"
    elif evaluadas and aciertos >= esperados:
        semaforo, texto = "verde", "cumple su promesa: acierta mas de lo que declara"
    elif not evaluadas:
        semaforo, texto = "ambar", "en vigilancia: aun sin valientes evaluadas"
    else:
        semaforo, texto = "ambar", "en vigilancia: por debajo de lo esperado, sin suspender"
    return {
        "semaforo": semaforo, "texto_semaforo": texto,
        "titular": f"{aciertos} aciertos vs {_fmt(esperados, 1)} esperados",
        "valor": aciertos, "comparacion": esperados,
        "evaluadas": evaluadas, "fuente": fuente,
        "senales_suspendidas": suspendidas,
        "por_senal": resumen_m.get("por_senal") or {},
        "promesa": "En sombra: aciertos reales >= esperados (suma de probabilidades declaradas).",
        "ultimo_ajuste": ultimo_ajuste,
    }


def resumen_revulsivo(filas, ultimo_ajuste=None):
    casos = [c for f in filas if f.get("estado") == "ok" for c in f.get("casos") or []]
    evaluados = [c for c in casos if c.get("veredicto") in ("ayudo", "neutro", "perjudico")]
    ayudo = sum(1 for c in evaluados if c["veredicto"] == "ayudo")
    perjudico = sum(1 for c in evaluados if c["veredicto"] == "perjudico")
    if not evaluados:
        semaforo, texto = "ambar", "en vigilancia: aun sin casos evaluados"
    elif len(evaluados) < 3:
        semaforo, texto = ("ambar", "en vigilancia: muestra minima "
                           f"({len(evaluados)} caso{'s' if len(evaluados) != 1 else ''})")
    elif ayudo > perjudico:
        semaforo, texto = "verde", "cumple su promesa: el ajuste ayuda mas de lo que estorba"
    elif ayudo == perjudico:
        semaforo, texto = "ambar", "en vigilancia: empate entre ayudas y estorbos"
    else:
        semaforo, texto = "rojo", "bajo promesa: el ajuste estorba mas de lo que ayuda"
    return {
        "semaforo": semaforo, "texto_semaforo": texto,
        "titular": f"ayudo {ayudo} de {len(evaluados)} casos",
        "valor": ayudo, "comparacion": len(evaluados), "perjudico": perjudico,
        "promesa": "El ajuste (+5 fuera / -3,5 casa, del estudio de 70 ceses) debe ayudar mas de lo que estorba.",
        "ultimo_ajuste": ultimo_ajuste,
    }


# ---------------------------------------------------------------------------
# (e) Cuaderno "fijos por banda" (17/10/2026, proyecto fijos calibrados):
# de los FIJOS realmente jugados (quinielas_jugadas.json, solo lectura),
# cuantos acerto cada banda de probabilidad pre-cierre, comparado con lo que
# esa banda PROMETE segun la calibracion real del favorito
# (rps_calibracion.calibracion_favorito). SOLO reporta: ninguna
# auto-correccion nueva -la colocacion calibrada tiene su propio backtest
# prerregistrado (backtest_fijos_calibrados.py, DECISION_LOG 17/10).
# ---------------------------------------------------------------------------

def fila_fijos_banda(jornada, etiqueta, fixture, prediccion_snapshot, datos_jugadas=None):
    """Los FIJOS realmente jugados de la jornada, con la probabilidad
    pre-cierre de su signo, su banda y si acertaron."""
    jugada = jugada_temporada(jornada, etiqueta, datos_jugadas)
    if not jugada:
        return {"estado": "sin_jugada_real", "motivo": "Jornada sin quiniela validada esta temporada."}
    partidos = {p["num"]: p for p in partidos_snapshot(prediccion_snapshot)}
    if not partidos:
        return {"estado": "sin_snapshot", "motivo": "Sin snapshot pre-cierre inmutable."}
    fijos = []
    sin_probabilidad = 0
    for num, signo in enumerate(jugada, start=1):
        limpio = "".join(s for s in SIGNOS if s in signo)
        if len(limpio) != 1:
            continue  # dobles y triples no son fijos
        probs = (partidos.get(num) or {}).get("probabilidades") or {}
        try:
            prob = float(probs[limpio])
        except (KeyError, TypeError, ValueError):
            sin_probabilidad += 1
            continue
        real = (fixture.get(num) or {}).get("signo_oficial")
        p = partidos.get(num) or {}
        fijos.append({
            "num": num,
            "partido": f"{p.get('local', '')} - {p.get('visitante', '')}",
            "signo": limpio,
            "probabilidad": round(prob, 1),
            "banda": f"{int(prob // 10) * 10}-{int(prob // 10) * 10 + 10}",
            "acierto": (real == limpio) if real in SIGNOS else None,
        })
    return {"estado": "ok", "fijos": fijos, "fijos_sin_probabilidad": sin_probabilidad}


def resumen_fijos_banda(filas, bandas_promesa=None):
    """Promesa: los fijos jugados deben acertar al menos lo que promete su
    banda REAL medida. El esperado de cada fijo es el acierto_real_pct de su
    banda (solo bandas con n>=30); sin promesa medida, su propia probabilidad
    dicha (identidad honesta)."""
    if bandas_promesa is None:
        metricas = cargar_json(METRICAS_PROBABILISTICAS, {})
        bandas_promesa = ((metricas.get("rps_calibracion") or {}).get("calibracion_favorito") or {})
    fijos = [f for fila in filas if fila.get("estado") == "ok" for f in fila.get("fijos") or []]
    evaluados = [f for f in fijos if f.get("acierto") is not None]
    por_banda = {}
    esperados = 0.0
    for f in evaluados:
        datos = (bandas_promesa or {}).get(f["banda"]) or {}
        promesa = None
        try:
            if int(datos.get("n") or 0) >= FIJOS_BANDA_N_MINIMO:
                promesa = float(datos["acierto_real_pct"])
        except (KeyError, TypeError, ValueError):
            promesa = None
        reg = por_banda.setdefault(f["banda"], {"jugados": 0, "aciertos": 0, "promesa_pct": None})
        reg["jugados"] += 1
        reg["aciertos"] += 1 if f["acierto"] else 0
        if promesa is not None:
            reg["promesa_pct"] = promesa
        esperados += (promesa if promesa is not None else f["probabilidad"]) / 100.0
    for reg in por_banda.values():
        reg["acierto_pct"] = round(100.0 * reg["aciertos"] / reg["jugados"], 1)
    aciertos = sum(1 for f in evaluados if f["acierto"])
    esperados = round(esperados, 2)
    if not evaluados:
        semaforo, texto = "ambar", "en vigilancia: aun sin fijos evaluables"
    elif len(evaluados) < FIJOS_BANDA_MUESTRA_MINIMA:
        semaforo, texto = "ambar", f"en vigilancia: muestra minima ({len(evaluados)} fijos)"
    elif aciertos >= esperados:
        semaforo, texto = "verde", "cumple su promesa: tus fijos rinden lo que promete su banda real"
    elif aciertos >= esperados - 2:
        semaforo, texto = "ambar", "en vigilancia: algo por debajo de lo que prometen sus bandas"
    else:
        semaforo, texto = "rojo", "bajo promesa: los fijos jugados rinden claramente menos que su banda real"
    return {
        "semaforo": semaforo, "texto_semaforo": texto,
        "titular": f"{aciertos} de {len(evaluados)} fijos vs {_fmt(esperados, 1)} esperados",
        "valor": aciertos, "comparacion": esperados,
        "fijos_evaluados": len(evaluados),
        "por_banda": dict(sorted(por_banda.items())),
        "promesa": (
            "Los fijos realmente jugados deben acertar al menos lo que promete su banda real "
            f"(calibracion del favorito, solo bandas con n>={FIJOS_BANDA_N_MINIMO})."
        ),
        "ultimo_ajuste": None,
    }


# ---------------------------------------------------------------------------
# Auto-auditoria con puerta (cada 5 jornadas cerradas; NUNCA aplica nada)
# ---------------------------------------------------------------------------

def auditoria_pendiente(cerradas, previa):
    ultimas = (previa or {}).get("jornadas_cerradas_al_auditar")
    if not isinstance(ultimas, int):
        return cerradas >= AUDITORIA_CADA_JORNADAS
    return cerradas >= ultimas + AUDITORIA_CADA_JORNADAS


def jornadas_era_dc(jornadas, dir_pre_cierre=None):
    """Jornadas cuyo snapshot pre-cierre ya traza dixon_coles (pipeline de la
    era D-C): el barrido solo compara contra el motor que YA lleva D-C dentro
    (DECISION_LOG 13/10: comparar contra el motor viejo era el espejismo)."""
    era = []
    for j in jornadas:
        partidos = partidos_snapshot(snapshot_prediccion(j, dir_pre_cierre))
        if any("dixon_coles" in (p.get("trazabilidad_datos") or {}) for p in partidos):
            era.append(j)
    return era


def barrido_peso_dc(jornadas, proveedor_modelo, dir_pre_cierre=None, dir_jornadas=None):
    """Barrido walk-forward del peso extra de D-C sobre el pipeline actual:
    mezcla (1-u)*probs_finales_pre_cierre + u*dc para u en 0..1. Candidato a
    cambio solo si el mejor u mejora el RPS de u=0 en mas de 0,002 con >=60
    partidos (umbral prerregistrado, DECISION_LOG 13/10)."""
    pesos = [round(u / 10.0, 1) for u in range(0, 11)]
    acumulado = {u: [] for u in pesos}
    n = 0
    for j in jornadas:
        fixture = fixture_jornada(j, dir_jornadas)
        partidos = partidos_snapshot(snapshot_prediccion(j, dir_pre_cierre))
        modelo = proveedor_modelo(j)
        if modelo is None:
            continue
        for p in partidos:
            real = (fixture.get(p["num"]) or {}).get("signo_oficial")
            probs = p.get("probabilidades") or {}
            if real not in SIGNOS or not probs:
                continue
            dc = modelo.probabilidades(p.get("local"), p.get("visitante"))
            if dc is None:
                continue
            total = sum(float(probs.get(s) or 0) for s in SIGNOS) or 1.0
            motor = {s: float(probs.get(s) or 0) / total for s in SIGNOS}
            for u in pesos:
                mezcla = {s: (1 - u) * motor[s] + u * float(dc[s]) for s in SIGNOS}
                acumulado[u].append(rps_partido(mezcla, real))
            n += 1
    if not n:
        return {"estado": "sin_datos", "partidos": 0}
    rps = {str(u): round(sum(v) / len(v), 5) for u, v in acumulado.items() if v}
    mejor_u = min(rps, key=rps.get)
    mejora = round(rps["0.0"] - rps[mejor_u], 5)
    candidato = mejora > AUDITORIA_DC_UMBRAL_RPS and n >= AUDITORIA_DC_MIN_PARTIDOS
    return {
        "estado": "ok",
        "partidos": n,
        "jornadas": list(jornadas),
        "rps_por_peso_extra": rps,
        "mejor_peso_extra": float(mejor_u),
        "mejora_rps_vs_actual": mejora,
        "umbral_mejora": AUDITORIA_DC_UMBRAL_RPS,
        "minimo_partidos": AUDITORIA_DC_MIN_PARTIDOS,
        "candidato": candidato,
    }


def auditoria_vetos_valiente():
    """Re-corre el criterio vivo y cada veto v2 POR SEPARADO (DECISION_LOG
    14/10: el veto grandes solo quito fallos; el del 55% corto carne). Importa
    backtest_valiente en diferido para no cargar su cadena si no toca."""
    from backtest_valiente import evaluar_criterio
    _, vivo = evaluar_criterio(aplicar_vetos=False)
    resultados = {"criterio_vivo": vivo}
    ratio_vivo = (vivo["aciertos"] / vivo["esperados"]) if vivo.get("esperados") else None
    for nombre, tipos in (("veto_grandes", {"grande_favorito"}),
                          ("veto_favorito_55", {"favorito_claro"})):
        _, resumen = evaluar_criterio(aplicar_vetos=True, tipos_vetos=tipos)
        ratio = (resumen["aciertos"] / resumen["esperados"]) if resumen.get("esperados") else None
        candidato = bool(
            resumen.get("jornadas_evaluadas", 0) >= AUDITORIA_VETOS_MIN_JORNADAS
            and str(resumen.get("veredicto", "")).startswith("VERDE")
            and ratio is not None and ratio_vivo is not None and ratio >= ratio_vivo
        )
        resultados[nombre] = {
            "resumen": resumen,
            "ratio": round(ratio, 2) if ratio is not None else None,
            "ratio_vivo": round(ratio_vivo, 2) if ratio_vivo is not None else None,
            "minimo_jornadas": AUDITORIA_VETOS_MIN_JORNADAS,
            "candidato": candidato,
        }
    return resultados


def construir_auditoria(cerradas, dc, vetos, ahora=None):
    resultados = []
    candidatos = []

    if dc.get("estado") == "ok":
        if dc["candidato"]:
            mensaje = (
                f"CANDIDATO A CAMBIO: subir el peso extra de Dixon-Coles a {dc['mejor_peso_extra']} "
                f"mejoraria el RPS en {dc['mejora_rps_vs_actual']} sobre {dc['partidos']} partidos "
                f"era-D-C (umbral {AUDITORIA_DC_UMBRAL_RPS}). Exige backtest prerregistrado y "
                "entrada en DECISION_LOG antes de tocar PESO_DIXON_COLES. Decides tu."
            )
            candidatos.append({"modulo": "dixon_coles", "mensaje": mensaje})
            detalle, estado = mensaje, "candidato_a_cambio"
        else:
            detalle, estado = (
                f"Sin cambios: mejor peso extra {dc['mejor_peso_extra']} con mejora "
                f"{dc['mejora_rps_vs_actual']} sobre {dc['partidos']} partidos "
                f"(umbral {AUDITORIA_DC_UMBRAL_RPS} con >={AUDITORIA_DC_MIN_PARTIDOS} partidos).",
                "sin_cambios",
            )
    else:
        detalle, estado = "Sin cambios: aun no hay partidos de la era D-C que barrer.", "sin_cambios"
    resultados.append({
        "modulo": "dixon_coles",
        "titulo": "Peso Dixon-Coles (barrido era-D-C acumulada)",
        "estado": estado,
        "detalle": detalle,
        "numeros": dc,
    })

    for nombre, titulo in (("veto_grandes", "La Valiente: veto grandes (por separado)"),
                           ("veto_favorito_55", "La Valiente: veto favorito >=55% (por separado)")):
        datos = vetos.get(nombre) or {}
        resumen = datos.get("resumen") or {}
        if datos.get("candidato"):
            mensaje = (
                f"CANDIDATO A CAMBIO: el {titulo.lower()} mantiene VERDE con ratio "
                f"{datos['ratio']} >= {datos['ratio_vivo']} del criterio vivo sobre "
                f"{resumen.get('jornadas_evaluadas')} jornadas. Activarlo exige nuevo "
                "prerregistro y entrada en DECISION_LOG. Decides tu."
            )
            candidatos.append({"modulo": nombre, "mensaje": mensaje})
            detalle, estado = mensaje, "candidato_a_cambio"
        else:
            detalle, estado = (
                f"Sin cambios: {resumen.get('valientes', 0)} valientes, ratio {datos.get('ratio')}"
                f" vs {datos.get('ratio_vivo')} del vivo en {resumen.get('jornadas_evaluadas', 0)} "
                f"jornadas (hacen falta >={AUDITORIA_VETOS_MIN_JORNADAS}, VERDE y ratio >= vivo).",
                "sin_cambios",
            )
        resultados.append({
            "modulo": nombre, "titulo": titulo, "estado": estado,
            "detalle": detalle,
            "numeros": {k: datos.get(k) for k in ("ratio", "ratio_vivo", "candidato", "minimo_jornadas")},
            "resumen_backtest": resumen,
        })

    return {
        "version": 1,
        "descripcion": (
            "Auto-auditoria con puerta del meta-aprendizaje (15/10/2026): cada "
            f"{AUDITORIA_CADA_JORNADAS} jornadas cerradas re-corre los barridos prerregistrados "
            "y SOLO reporta. Nada se aplica sin decision explicita de Marc."
        ),
        "generado_en": ahora or ahora_iso(),
        "jornadas_cerradas_al_auditar": cerradas,
        "proxima_auditoria_con_jornadas": cerradas + AUDITORIA_CADA_JORNADAS,
        "frenos": FRENOS_TEXTO["auditoria"],
        "resultados": resultados,
        "candidatos": candidatos,
    }


# ---------------------------------------------------------------------------
# Orquestacion (la llama generar_artefactos_compuerta_aprendizaje en cada
# ciclo de aprendizaje; solo lo caro -entrenar D-C- se cachea por jornada)
# ---------------------------------------------------------------------------

class _ProveedorModelosDC:
    """Entrena D-C a la vispera de cada jornada UNA vez por proceso y lo
    comparte entre el cuaderno y la auditoria."""

    def __init__(self, dir_jornadas=None):
        self._historico = None
        self._modelos = {}
        self._dir_jornadas = dir_jornadas

    def modelo(self, jornada):
        if jornada in self._modelos:
            return self._modelos[jornada]
        corte = fecha_corte_jornada(fixture_jornada(jornada, self._dir_jornadas))
        modelo = None
        if corte is not None:
            if self._historico is None:
                self._historico = cargar_partidos()
            try:
                modelo = DixonColes().entrenar(self._historico, corte)
            except ValueError:
                modelo = None
        self._modelos[jornada] = modelo
        return modelo


def actualizar_cuaderno(etiqueta=None, ahora=None, proveedor=None):
    """Reconstruye el cuaderno: las filas baratas (EV, valiente, revulsivo) se
    recalculan en cada ciclo (asi recogen datos que llegan tarde, p.ej. el
    escrutinio); la fila D-C, que exige re-entrenar el modelo, se cachea por
    jornada y version de calculo."""
    etiqueta = etiqueta or temporada_etiqueta(datetime.now())
    ahora = ahora or ahora_iso()
    proveedor = proveedor or _ProveedorModelosDC()
    cerradas = jornadas_cerradas_temporada(etiqueta)
    previo = cargar_json(CUADERNO, {})
    previas = previo.get("jornadas") or {} if previo.get("temporada") == etiqueta else {}

    marcador = cargar_json(MARCADOR_VALIENTE, {})
    backtest_valiente_json = cargar_json(BACKTEST_VALIENTE, {})
    backtest_ev = cargar_json(BACKTEST_EV, {})
    datos_jugadas = cargar_json(QUINIELAS_JUGADAS, {})

    jornadas = {}
    casos_revulsivo = []
    for j in cerradas:
        fixture = fixture_jornada(j)
        prediccion = snapshot_prediccion(j)
        partidos = partidos_snapshot(prediccion)

        fila_dc_previa = (previas.get(str(j)) or {}).get("dixon_coles") or {}
        if (fila_dc_previa.get("version_calculo") == VERSION_CALCULO_DC
                and fila_dc_previa.get("estado") in ("ok", "sin_cobertura")):
            fila_dc = fila_dc_previa
        elif not partidos:
            fila_dc = {"estado": "sin_snapshot", "motivo": "Sin snapshot pre-cierre inmutable."}
        else:
            modelo = proveedor.modelo(j)
            if modelo is None:
                fila_dc = {"estado": "sin_modelo", "motivo": "Historial insuficiente para entrenar D-C."}
            else:
                fila_dc = fila_dixon_coles(partidos, fixture, modelo)

        if partidos:
            fila_ev = fila_boleto_ev(j, fixture, prediccion, etiqueta,
                                     backtest_ev=backtest_ev, datos_jugadas=datos_jugadas)
        else:
            fila_ev = {"estado": "sin_snapshot", "motivo": "Sin snapshot pre-cierre inmutable."}

        partidos_traza, fuente_traza = partidos_con_traza_revulsivo(j, prediccion)
        fila_rev = fila_revulsivo(partidos_traza, fixture)
        fila_rev["fuente"] = fuente_traza if fila_rev.get("estado") == "ok" else None
        casos_revulsivo.extend(fila_rev.get("casos") or [])

        jornadas[str(j)] = {
            "dixon_coles": fila_dc,
            "boleto_ev": fila_ev,
            "valiente": fila_valiente(j, etiqueta, marcador, backtest_valiente_json),
            "revulsivo": fila_rev,
            "fijos_banda": fila_fijos_banda(j, etiqueta, fixture, prediccion, datos_jugadas),
        }

    # Auto-correcciones acotadas (cada una escribe su propio archivo y
    # devuelve el bloque para el "ultimo ajuste" de su tarjeta).
    ajuste_factor = actualizar_factor_overdispersion(etiqueta, cerradas, ahora)
    ajuste_revulsivo = actualizar_reestimacion_revulsivo(casos_revulsivo, ahora)
    resumen_marcador = (cargar_json(MARCADOR_VALIENTE, {}).get("resumen") or {})
    ajuste_valiente = {
        "estado": "ajustado" if resumen_marcador.get("senales_suspendidas") else "sin_ajuste",
        "senales_suspendidas": resumen_marcador.get("senales_suspendidas") or [],
        "freno": FRENOS_TEXTO["valiente"],
        "actualizado_en": ahora,
    }
    if ajuste_valiente["estado"] == "sin_ajuste":
        ajuste_valiente["motivo"] = "Ninguna señal cumple el freno de suspension (>=8 propias y <50% de esperados)."

    filas_dc = [jornadas[k]["dixon_coles"] for k in jornadas]
    filas_ev = [jornadas[k]["boleto_ev"] for k in jornadas]
    filas_rev = [jornadas[k]["revulsivo"] for k in jornadas]
    filas_fb = [jornadas[k]["fijos_banda"] for k in jornadas]
    cuaderno = {
        "version": 1,
        "descripcion": (
            "Cuaderno de meta-aprendizaje por modulo (15/10/2026): que prometio cada modulo y "
            "que entrego, jornada a jornada, con datos pre-cierre (snapshots inmutables + % LAE "
            "versionados). Los semaforos y auto-correcciones llevan sus frenos prerregistrados."
        ),
        "temporada": etiqueta,
        "actualizado_en": ahora,
        "jornadas_cerradas": cerradas,
        "jornadas": jornadas,
        "resumen": {
            "dixon_coles": resumen_dixon_coles(filas_dc),
            "boleto_ev": resumen_boleto_ev(filas_ev, ultimo_ajuste=ajuste_factor),
            "valiente": resumen_valiente(marcador, backtest_valiente_json, ultimo_ajuste=ajuste_valiente),
            "revulsivo": resumen_revulsivo(filas_rev, ultimo_ajuste=ajuste_revulsivo),
            "fijos_banda": resumen_fijos_banda(filas_fb),
        },
        "frenos": FRENOS_TEXTO,
    }
    guardar_json(CUADERNO, cuaderno)
    return cuaderno


def ejecutar_auditoria_si_toca(cuaderno, ahora=None, proveedor=None, forzar=False):
    cerradas = len(cuaderno.get("jornadas_cerradas") or [])
    previa = cargar_json(AUDITORIA, {})
    if not forzar and not auditoria_pendiente(cerradas, previa):
        return previa or None
    proveedor = proveedor or _ProveedorModelosDC()
    era = jornadas_era_dc(cuaderno.get("jornadas_cerradas") or [])
    dc = barrido_peso_dc(era, proveedor.modelo) if era else {"estado": "sin_datos", "partidos": 0}
    vetos = auditoria_vetos_valiente()
    auditoria = construir_auditoria(cerradas, dc, vetos, ahora)
    guardar_json(AUDITORIA, auditoria)
    return auditoria


def actualizar_todo(ahora=None, forzar_auditoria=False):
    """Punto de entrada del ciclo de aprendizaje: cuaderno + auto-correcciones
    + auditoria si toca. Devuelve un resumen pequeño para el log."""
    proveedor = _ProveedorModelosDC()
    cuaderno = actualizar_cuaderno(ahora=ahora, proveedor=proveedor)
    auditoria = ejecutar_auditoria_si_toca(cuaderno, ahora=ahora, proveedor=proveedor,
                                           forzar=forzar_auditoria)
    candidatos = (auditoria or {}).get("candidatos") or []
    return {
        "jornadas_cerradas": len(cuaderno.get("jornadas_cerradas") or []),
        "semaforos": {k: v.get("semaforo") for k, v in (cuaderno.get("resumen") or {}).items()},
        "candidatos_auditoria": len(candidatos),
    }


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    resumen = actualizar_todo()
    print(
        f"Meta-aprendizaje: cuaderno con {resumen['jornadas_cerradas']} jornadas cerradas; "
        f"semaforos {resumen['semaforos']}; candidatos de auditoria: {resumen['candidatos_auditoria']}."
    )
    if resumen["candidatos_auditoria"]:
        print("AUDITORIA_CANDIDATO_A_CAMBIO: revisar data/memoria_ia/auditoria_automatica.json (decide Marc).")


if __name__ == "__main__":
    main()
