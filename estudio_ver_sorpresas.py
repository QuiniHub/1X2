"""Estudio VER sorpresas (peticion de Marc, 17/10/2026): ¿que sucedio ANTES
de nuestras sorpresas reales, medible y sin fuga de futuro?

La investigacion mundial (INVESTIGACION_SORPRESAS.md, 14/10/2026) dejo claro
que NADIE predice la sorpresa concreta. Lo que queda abierto es minar NUESTROS
datos en busca de precursores medibles. Este estudio lo hace con prerregistro:
la lista de features y los umbrales de veredicto estan escritos AQUI, antes de
calcular nada, y no se amplian despues de ver los numeros.

SORPRESA (definicion): no gana el favorito. En el dataset del motor el
favorito es el signo con mayor probabilidad del motor; en el historico con
cuotas, el signo de cuota minima. Sub-tipo "sorpresa maxima": gana el TERCER
signo (el menos probable).

PRERREGISTRO — features (todas conocibles antes del cierre; ninguna usa
informacion posterior al partido):

Dataset A — partidos evaluados por el motor (historial_permanente.json,
temporadas 25/26 y 26/27 con probabilidades y resultado):
  A1  banda de prob del favorito motor: <45 / 45-54.9 / >=55
      (contraste prerregistrado: banda <45 vs banda >=55)
  A2  favorito del motor != favorito del mercado losilla (snapshot pre-cierre)
  A3  masa LAE del favorito >= 70% (favorito caro del publico; solo 26/27)
  A4  sobrecompra: masa LAE favorito - prob motor favorito >= +10 pts
  A5  racha: el equipo favorito trae >=2 sorpresas positivas (gano sin ser
      favorito del motor) en sus ultimos 3 partidos evaluados (cronologico,
      solo partidos anteriores)
  A6  equipo empatador en el partido (x_pct >= 32, equipos_x_fiabilidad)
  A7  equipo nemesis nuestro en el partido (>=6 apariciones, <=33% acierto)
  A8  H2H caotico historico (tasa >= 50%, >= 2 casos con cuotas; SOLO filas
      26/27 porque el archivo H2H se construyo con 23/24-25/26)
  A9  favorito visitante (signo 2) vs favorito local
  A10 partido entre semana (martes-jueves) vs resto

Dataset B — historico espanol 3 temporadas con cuotas
(historico_ligas_espana.json, favorito = cuota minima):
  B1  banda de cuota del favorito: <1.50 / 1.50-1.99 / 2.00-2.49 / >=2.50
      (contraste prerregistrado: <1.50 vs >=2.50)
  B2  favorito visitante
  B3  partido entre semana (martes-jueves)
  B4  racha: favorito con >=2 sorpresas positivas en sus ultimos 3 partidos
      del dataset (acumulado cronologico, sin fuga)
  B5  H2H previo caotico: >=2 cruces ANTERIORES del par con >=50% de
      sorpresas (acumulado cronologico, sin fuga)
  B6  favorito con competicion europea esa temporada (solo Primera; lista
      estatica por temporada, abajo). NOTA honesta: "jugo en Europa ESA
      semana" NO es medible con nuestros datos; esto es el proxy medible.

Clustering / pregunta estrella ("¿las sorpresas vienen en grupo?"):
  C1  test de permutacion ESTRATIFICADA (estratos = banda del % del favorito
      del publico) de la varianza del nº de sorpresas por jornada, con el
      historico LAE completo (favorito del publico = signo mas apostado).
      2000 permutaciones, semilla fija. p = fraccion de varianzas permutadas
      >= observada.
  C2  persistencia: P(jornada con >=8 sorpresas | la anterior tuvo >=8) vs
      base, en orden cronologico DENTRO de cada temporada (la numeracion se
      reinicia: jamas se ordena por numero entre temporadas).
  C3  C1 restringido a favoritos claros del publico (>=60% de masa).
  C4  jornada entre semana (mar-jue) vs fin de semana: tasa de sorpresa del
      favorito del publico.
  C5  dispersion con el motor (dataset A): varianza observada del nº de
      sorpresas por jornada vs varianza teorica si los partidos fueran
      independientes (E[Var] + Var[E] con p_i = 1 - prob_favorito).
  C6  descriptivo (sin veredicto): en jornadas locas (>=8 sorpresas), ¿que %
      de las sorpresas son de favoritos claros (>=60%)? vs jornadas normales.

VEREDICTO prerregistrado por feature binaria:
  diff = tasa_con - tasa_sin; SE = sqrt(p1(1-p1)/n1 + p2(1-p2)/n2)
  UTILIZABLE: n_con >= 30 y |diff| >= 2*SE
  DEBIL:      n_con >= 30 y |diff| >= 1*SE
  NADA:       el resto
Para bandas (A1/B1) el contraste es entre las bandas extremas indicadas.
Para C1/C3: UTILIZABLE si p < 0.05. Con ~14 contrastes, UN falso positivo a
2 SE es estadisticamente esperable: una feature solo entra en la lista de
candidatas a señal de La Valiente si es UTILIZABLE y, cuando existe en ambos
datasets, apunta en la MISMA direccion en los dos.

CANDIDATA a señal nueva: feature UTILIZABLE cuya presencia SUBE la tasa de
sorpresa (sirve para elegir donde ser valiente). Queda "pendiente de backtest
de señal": este estudio NO toca senal_valiente.py.

Avisos de honestidad incorporados al JSON:
 - equipos_x_fiabilidad.json incluye los pocos partidos ya jugados de 26/27
   en su x_pct (fuga minima: ~8 de ~120 pj por equipo); se usa igual y se
   declara.
 - El archivo H2H agregado solo se aplica a filas 26/27 (A8); en el dataset B
   el H2H se recalcula acumulado y limpio (B5).

Salida: data/memoria_ia/estudio_ver_sorpresas.json + resumen por pantalla.
On-demand (patron estudio_distribucion_signos.py); NO forma parte del
pipeline.
"""
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from modelo_dixon_coles import clave_equipo
from motor_prediccion_quiniela import clave_par_equipos_h2h

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
HISTORIAL_PERMANENTE = DATA / "memoria_ia" / "historial_permanente.json"
HISTORICO_LIGAS = DATA / "memoria_ia" / "historico_ligas_espana.json"
HISTORICO_LAE = DATA / "memoria_ia" / "historico_quinielas_lae.json"
ESTUDIO_X = DATA / "memoria_ia" / "equipos_x_fiabilidad.json"
HISTORIAL_H2H = DATA / "memoria_ia" / "historial_enfrentamientos.json"
PORCENTAJES_LAE_DIR = DATA / "memoria_ia" / "porcentajes_lae"
PRE_CIERRE_DIR = DATA / "backtesting" / "pre_cierre"
SALIDA = DATA / "memoria_ia" / "estudio_ver_sorpresas.json"

SIGNOS = ("1", "X", "2")

# Umbrales prerregistrados (ver docstring; no tocar despues de calcular)
BANDA_PROB_BAJA = 45.0
BANDA_PROB_ALTA = 55.0
MASA_FAVORITO_CARO = 70.0
SOBRECOMPRA_PUNTOS = 10.0
RACHA_SORPRESAS_MIN = 2
RACHA_VENTANA = 3
EMPATADOR_X_PCT = 32.0
NEMESIS_APARICIONES_MIN = 6
NEMESIS_ACIERTO_MAX = 33.0
H2H_TASA_MIN = 50.0
H2H_CASOS_MIN = 2
FAVORITO_CLARO_PUBLICO = 60.0
JORNADA_LOCA_SORPRESAS = 8
PERMUTACIONES = 2000
SEMILLA = 20261017
N_MINIMO = 30

# B6: equipos de Primera con competicion europea por temporada (lista
# estatica, nombres tal cual aparecen en historico_ligas_espana.json)
EUROPEOS = {
    "2023/2024": {"Real Madrid", "Barcelona", "Atletico Madrid", "Sociedad",
                  "Sevilla", "Real Betis", "Villarreal", "Osasuna"},
    "2024/2025": {"Real Madrid", "Barcelona", "Atletico Madrid",
                  "Athletic Club", "Girona", "Sociedad", "Real Betis"},
    "2025/2026": {"Real Madrid", "Barcelona", "Atletico Madrid",
                  "Athletic Club", "Villarreal", "Real Betis", "Celta Vigo",
                  "Vallecano"},
}

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def cargar_json(ruta, defecto=None):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def parsear_fecha(valor):
    """Fecha real desde los formatos que conviven en los datos: ISO
    (YYYY-MM-DD), DD/MM/YYYY, DD-MM-YYYY y 'D de <mes> de YYYY' (con o sin
    prefijos tipo 'La Quiniela Domingo,'). None si no se puede."""
    texto = str(valor or "").strip()
    if not texto:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", texto)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date()
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})\s+de\s+([A-Za-zñÑ]+)\s+de\s+(\d{4})", texto, re.IGNORECASE)
    if m:
        mes = MESES.get(m.group(2).lower())
        if mes:
            try:
                return datetime(int(m.group(3)), mes, int(m.group(1))).date()
            except ValueError:
                return None
    return None


def es_entre_semana(fecha):
    """Martes (1), miercoles (2) o jueves (3)."""
    return fecha is not None and fecha.weekday() in (1, 2, 3)


def favorito_de(valores):
    """Signo con el valor maximo; empates se resuelven en orden 1, X, 2
    (prerregistrado; el caso es raro)."""
    return max(SIGNOS, key=lambda s: (float(valores.get(s) or 0), -SIGNOS.index(s)))


def tercer_signo_de(valores):
    return min(SIGNOS, key=lambda s: (float(valores.get(s) or 0), SIGNOS.index(s)))


def contraste(tasa_con, n_con, tasa_sin, n_sin):
    """Diferencia de proporciones con su error estandar y veredicto
    prerregistrado (UTILIZABLE / DEBIL / NADA)."""
    if not n_con or not n_sin:
        return {"diff": None, "se": None, "z": None, "veredicto": "NADA",
                "motivo": "sin muestra en alguno de los grupos"}
    p1, p2 = tasa_con / 100.0, tasa_sin / 100.0
    se = (p1 * (1 - p1) / n_con + p2 * (1 - p2) / n_sin) ** 0.5
    diff = p1 - p2
    z = diff / se if se > 0 else 0.0
    if n_con >= N_MINIMO and abs(z) >= 2:
        veredicto = "UTILIZABLE"
    elif n_con >= N_MINIMO and abs(z) >= 1:
        veredicto = "DEBIL"
    else:
        veredicto = "NADA"
    return {"diff_puntos": round(100 * diff, 1), "se_puntos": round(100 * se, 1),
            "z": round(z, 2), "veredicto": veredicto}


def medir_feature(filas, tiene_feature, etiqueta, descripcion):
    """Tasa de sorpresa con/sin la feature + contraste. `tiene_feature`
    devuelve True/False/None (None = no evaluable, fuera de la muestra)."""
    con, sin = [], []
    for f in filas:
        v = tiene_feature(f)
        if v is True:
            con.append(f["sorpresa"])
        elif v is False:
            sin.append(f["sorpresa"])
    tasa_con = round(100 * sum(con) / len(con), 1) if con else None
    tasa_sin = round(100 * sum(sin) / len(sin), 1) if sin else None
    resultado = {
        "feature": etiqueta,
        "descripcion": descripcion,
        "n_con": len(con), "tasa_sorpresa_con_pct": tasa_con,
        "n_sin": len(sin), "tasa_sorpresa_sin_pct": tasa_sin,
    }
    if tasa_con is not None and tasa_sin is not None:
        resultado.update(contraste(tasa_con, len(con), tasa_sin, len(sin)))
    else:
        resultado.update({"veredicto": "NADA", "motivo": "muestra vacia"})
    return resultado


# ---------------------------------------------------------------------------
# Dataset A: partidos evaluados por el motor
# ---------------------------------------------------------------------------

def construir_dataset_motor(historial=None):
    """Filas del motor con probabilidades validas y resultado oficial,
    ordenadas cronologicamente (temporada, jornada: la numeracion se reinicia
    cada temporada, jamas se ordena por numero a secas)."""
    historial = historial if historial is not None else cargar_json(HISTORIAL_PERMANENTE, {})
    filas = []
    for p in historial.get("partidos") or []:
        probs = p.get("probabilidades") or {}
        signo_real = str(p.get("signo_real") or "").upper()
        if signo_real not in SIGNOS:
            continue
        try:
            valores = {s: float(probs.get(s)) for s in SIGNOS}
        except (TypeError, ValueError):
            continue
        if sum(valores.values()) < 50:  # probabilidades rotas o vacias
            continue
        favorito = favorito_de(valores)
        filas.append({
            "temporada": p.get("temporada"),
            "jornada": p.get("jornada"),
            "num": p.get("num"),
            "local": p.get("local"),
            "visitante": p.get("visitante"),
            "fecha": parsear_fecha(p.get("fecha")),
            "probs": valores,
            "favorito": favorito,
            "prob_favorito": valores[favorito],
            "signo_real": signo_real,
            "sorpresa": signo_real != favorito,
            "sorpresa_maxima": signo_real == tercer_signo_de(valores),
        })
    filas.sort(key=lambda f: (str(f["temporada"]), int(f["jornada"] or 0), int(f["num"] or 0)))
    return filas


def cargar_masa_lae(etiqueta="2026_2027", hasta=60):
    """{(jornada, num): {signo: pct}} de los archivos versionados de % LAE."""
    masa = {}
    base = PORCENTAJES_LAE_DIR / etiqueta
    for jornada in range(1, hasta + 1):
        datos = cargar_json(base / f"jornada_{jornada}.json")
        if not datos:
            continue
        for p in datos.get("partidos") or []:
            pct = p.get("porcentajes") or {}
            try:
                masa[(jornada, int(p.get("numero")))] = {s: float(pct.get(s)) for s in SIGNOS}
            except (TypeError, ValueError):
                continue
    return masa


def cargar_mercado_pre_cierre():
    """{(jornada, num): {'mercado': probs, 'claves': {clave_local, clave_visit}}}
    desde los snapshots inmutables pre-cierre (mercado_losilla por partido)."""
    mercado = {}
    for ruta in sorted(PRE_CIERRE_DIR.glob("jornada_*.json")):
        datos = cargar_json(ruta, {})
        prediccion = datos.get("prediccion") or {}
        jornada = prediccion.get("jornada") or datos.get("jornada")
        for p in prediccion.get("partidos") or []:
            ml = p.get("mercado_losilla") or {}
            try:
                probs = {s: float(ml.get(s)) for s in SIGNOS}
            except (TypeError, ValueError):
                continue
            mercado[(jornada, p.get("num"))] = {
                "mercado": probs,
                "claves": {clave_equipo(p.get("local")), clave_equipo(p.get("visitante"))},
            }
    return mercado


def rachas_previas_por_fila(filas):
    """Para cada fila (ya cronologica), ¿trae el equipo FAVORITO >=2 sorpresas
    positivas (gano sin ser favorito del motor) en sus ultimos 3 partidos
    evaluados ANTERIORES? None si el favorito es X o sin historial previo
    suficiente (menos de 3 partidos previos)."""
    historia = {}
    resultado = []
    for f in filas:
        if f["favorito"] == "X":
            resultado.append(None)
        else:
            equipo = f["local"] if f["favorito"] == "1" else f["visitante"]
            previos = historia.get(clave_equipo(equipo)) or []
            if len(previos) < RACHA_VENTANA:
                resultado.append(None)
            else:
                resultado.append(sum(previos[-RACHA_VENTANA:]) >= RACHA_SORPRESAS_MIN)
        # actualizar historial DESPUES de decidir la fila (sin fuga)
        for equipo, signo_equipo in ((f["local"], "1"), (f["visitante"], "2")):
            clave = clave_equipo(equipo)
            if not clave:
                continue
            sorpresa_positiva = f["signo_real"] == signo_equipo and f["favorito"] != signo_equipo
            historia.setdefault(clave, []).append(sorpresa_positiva)
    return resultado


def analizar_dataset_motor():
    filas = construir_dataset_motor()
    masa = cargar_masa_lae()
    mercado = cargar_mercado_pre_cierre()
    estudio_x = cargar_json(ESTUDIO_X, {}) or {}
    empatadores = {f.get("equipo") for f in estudio_x.get("equipos_empatadores") or []
                   if (f.get("x_pct") or 0) >= EMPATADOR_X_PCT}
    nemesis = {f.get("equipo") for f in estudio_x.get("fiabilidad_nuestra_por_equipo") or []
               if (f.get("apariciones") or 0) >= NEMESIS_APARICIONES_MIN
               and (f.get("acierto_pct") or 100) <= NEMESIS_ACIERTO_MAX}
    h2h = (cargar_json(HISTORIAL_H2H, {}) or {}).get("enfrentamientos") or {}
    rachas = rachas_previas_por_fila(filas)
    for f, racha in zip(filas, rachas):
        f["racha_favorito"] = racha

    def masa_de(f):
        if f["temporada"] != "2026_2027":
            return None
        return masa.get((f["jornada"], f["num"]))

    def mercado_de(f):
        if f["temporada"] != "2026_2027":
            return None
        reg = mercado.get((f["jornada"], f["num"]))
        if not reg:
            return None
        if clave_equipo(f["local"]) not in reg["claves"] and clave_equipo(f["visitante"]) not in reg["claves"]:
            return None  # mismo numero de jornada pero otra temporada
        return reg["mercado"]

    def f_banda(f):
        # contraste prerregistrado: <45 vs >=55 (la banda intermedia queda fuera)
        if f["prob_favorito"] < BANDA_PROB_BAJA:
            return True
        if f["prob_favorito"] >= BANDA_PROB_ALTA:
            return False
        return None

    def f_favorito_distinto_mercado(f):
        m = mercado_de(f)
        return None if m is None else favorito_de(m) != f["favorito"]

    def f_masa_cara(f):
        m = masa_de(f)
        return None if m is None else m.get(f["favorito"], 0) >= MASA_FAVORITO_CARO

    def f_sobrecompra(f):
        m = masa_de(f)
        if m is None:
            return None
        return m.get(f["favorito"], 0) - f["prob_favorito"] >= SOBRECOMPRA_PUNTOS

    def f_racha(f):
        return f["racha_favorito"]

    def f_empatador(f):
        return clave_equipo(f["local"]) in empatadores or clave_equipo(f["visitante"]) in empatadores

    def f_nemesis(f):
        return clave_equipo(f["local"]) in nemesis or clave_equipo(f["visitante"]) in nemesis

    def f_h2h(f):
        if f["temporada"] != "2026_2027":
            return None  # el archivo H2H incluye 25/26: solo sin fuga en 26/27
        reg = h2h.get(clave_par_equipos_h2h(f["local"] or "", f["visitante"] or ""))
        if not reg or (reg.get("casos_con_cuotas") or 0) < H2H_CASOS_MIN:
            return False
        tasa = reg.get("tasa_sorpresa_historica")
        return tasa is not None and tasa >= H2H_TASA_MIN

    def f_visitante(f):
        if f["favorito"] == "X":
            return None
        return f["favorito"] == "2"

    def f_entre_semana(f):
        return None if f["fecha"] is None else es_entre_semana(f["fecha"])

    features = [
        medir_feature(filas, f_banda, "A1_banda_prob_favorito",
                      f"Favorito motor <{BANDA_PROB_BAJA:.0f}% (con) vs >={BANDA_PROB_ALTA:.0f}% (sin); banda intermedia excluida."),
        medir_feature(filas, f_favorito_distinto_mercado, "A2_favorito_distinto_mercado",
                      "El favorito del motor no coincide con el del mercado losilla pre-cierre."),
        medir_feature(filas, f_masa_cara, "A3_masa_favorito_cara",
                      f"La masa LAE juega el favorito al >={MASA_FAVORITO_CARO:.0f}% (solo 26/27 con % versionados)."),
        medir_feature(filas, f_sobrecompra, "A4_sobrecompra_publico",
                      f"Masa LAE del favorito >= prob motor + {SOBRECOMPRA_PUNTOS:.0f} pts."),
        medir_feature(filas, f_racha, "A5_racha_favorito",
                      f"El favorito trae >={RACHA_SORPRESAS_MIN} sorpresas positivas en sus ultimos {RACHA_VENTANA} evaluados."),
        medir_feature(filas, f_empatador, "A6_empatador_en_partido",
                      f"Algun equipo empatador historico (x_pct >= {EMPATADOR_X_PCT:.0f}%)."),
        medir_feature(filas, f_nemesis, "A7_nemesis_en_partido",
                      f"Algun equipo nemesis nuestro (>={NEMESIS_APARICIONES_MIN} apariciones, <={NEMESIS_ACIERTO_MAX:.0f}% acierto)."),
        medir_feature(filas, f_h2h, "A8_h2h_caotico",
                      f"Cruce con tasa de sorpresa historica >={H2H_TASA_MIN:.0f}% ({H2H_CASOS_MIN}+ casos); solo filas 26/27."),
        medir_feature(filas, f_visitante, "A9_favorito_visitante",
                      "El favorito del motor juega fuera (signo 2) vs en casa (signo 1)."),
        medir_feature(filas, f_entre_semana, "A10_entre_semana",
                      "Partido en martes-jueves vs resto (solo filas con fecha por partido)."),
    ]
    n = len(filas)
    return filas, {
        "partidos": n,
        "temporadas": sorted({f["temporada"] for f in filas}),
        "tasa_sorpresa_base_pct": round(100 * sum(f["sorpresa"] for f in filas) / n, 1) if n else None,
        "tasa_sorpresa_maxima_pct": round(100 * sum(f["sorpresa_maxima"] for f in filas) / n, 1) if n else None,
        "features": features,
    }


# ---------------------------------------------------------------------------
# Dataset B: historico espanol con cuotas
# ---------------------------------------------------------------------------

def construir_dataset_cuotas(historico=None):
    historico = historico if historico is not None else cargar_json(HISTORICO_LIGAS, {})
    filas = []
    for liga, bloque in (historico.get("ligas") or {}).items():
        for temporada, t in (bloque.get("temporadas") or {}).items():
            for p in t.get("partidos") or []:
                signo = str(p.get("signo") or "").upper()
                if signo not in SIGNOS:
                    continue
                try:
                    cuotas = {"1": float(p["cuota_1"]), "X": float(p["cuota_x"]), "2": float(p["cuota_2"])}
                except (KeyError, TypeError, ValueError):
                    continue
                favorito = min(SIGNOS, key=lambda s: (cuotas[s], SIGNOS.index(s)))
                filas.append({
                    "liga": liga,
                    "temporada": temporada,
                    "fecha": parsear_fecha(p.get("fecha")),
                    "local": p.get("local"),
                    "visitante": p.get("visitante"),
                    "cuota_favorito": cuotas[favorito],
                    "favorito": favorito,
                    "signo_real": signo,
                    "sorpresa": signo != favorito,
                })
    filas.sort(key=lambda f: (f["fecha"] or datetime(1900, 1, 1).date(), f["local"] or ""))
    return filas


def analizar_dataset_cuotas():
    filas = construir_dataset_cuotas()

    # B4: racha del favorito, acumulada cronologicamente (sin fuga)
    historia = {}
    for f in filas:
        equipo = f["local"] if f["favorito"] == "1" else (f["visitante"] if f["favorito"] == "2" else None)
        if equipo is None:
            f["racha_favorito"] = None
        else:
            previos = historia.get(clave_equipo(equipo)) or []
            f["racha_favorito"] = (sum(previos[-RACHA_VENTANA:]) >= RACHA_SORPRESAS_MIN
                                   if len(previos) >= RACHA_VENTANA else None)
        for equipo2, signo_eq in ((f["local"], "1"), (f["visitante"], "2")):
            clave = clave_equipo(equipo2)
            if clave:
                historia.setdefault(clave, []).append(
                    f["signo_real"] == signo_eq and f["favorito"] != signo_eq)

    # B5: H2H previo caotico, acumulado (sin fuga)
    h2h_prev = {}
    for f in filas:
        par = clave_par_equipos_h2h(f["local"] or "", f["visitante"] or "")
        previos = h2h_prev.get(par) or []
        f["h2h_previo"] = (sum(previos) / len(previos) >= H2H_TASA_MIN / 100.0
                           if len(previos) >= H2H_CASOS_MIN else None)
        h2h_prev.setdefault(par, []).append(f["sorpresa"])

    def f_banda(f):
        if f["cuota_favorito"] < 1.50:
            return True   # "con" = favorito clarisimo
        if f["cuota_favorito"] >= 2.50:
            return False  # "sin" = favorito dudoso
        return None

    def f_visitante(f):
        return None if f["favorito"] == "X" else f["favorito"] == "2"

    def f_entre_semana(f):
        return None if f["fecha"] is None else es_entre_semana(f["fecha"])

    def f_racha(f):
        return f["racha_favorito"]

    def f_h2h(f):
        return f["h2h_previo"]

    def f_europeo(f):
        if f["liga"] != "primera":
            return None
        equipos = EUROPEOS.get(f["temporada"])
        if not equipos:
            return None
        equipo = f["local"] if f["favorito"] == "1" else (f["visitante"] if f["favorito"] == "2" else None)
        return None if equipo is None else equipo in equipos

    features = [
        medir_feature(filas, f_banda, "B1_banda_cuota_favorito",
                      "Favorito a cuota <1.50 (con) vs >=2.50 (sin); bandas intermedias excluidas."),
        medir_feature(filas, f_visitante, "B2_favorito_visitante",
                      "El favorito por cuotas juega fuera vs en casa."),
        medir_feature(filas, f_entre_semana, "B3_entre_semana",
                      "Partido en martes-jueves vs resto."),
        medir_feature(filas, f_racha, "B4_racha_favorito",
                      f"Favorito con >={RACHA_SORPRESAS_MIN} sorpresas positivas en sus ultimos {RACHA_VENTANA} partidos (acumulado sin fuga)."),
        medir_feature(filas, f_h2h, "B5_h2h_previo_caotico",
                      f"El par trae >={H2H_TASA_MIN:.0f}% de sorpresas en >={H2H_CASOS_MIN} cruces anteriores (acumulado sin fuga)."),
        medir_feature(filas, f_europeo, "B6_favorito_europeo",
                      "El favorito disputa competicion europea esa temporada (solo Primera; proxy, no 'jugo esa semana')."),
    ]
    n = len(filas)
    bandas = {}
    for f in filas:
        c = f["cuota_favorito"]
        banda = "<1.50" if c < 1.5 else "1.50-1.99" if c < 2.0 else "2.00-2.49" if c < 2.5 else ">=2.50"
        reg = bandas.setdefault(banda, {"n": 0, "sorpresas": 0})
        reg["n"] += 1
        reg["sorpresas"] += f["sorpresa"]
    for reg in bandas.values():
        reg["tasa_pct"] = round(100 * reg["sorpresas"] / reg["n"], 1)
    return filas, {
        "partidos": n,
        "tasa_sorpresa_base_pct": round(100 * sum(f["sorpresa"] for f in filas) / n, 1) if n else None,
        "tasa_por_banda_cuota": {k: bandas[k] for k in sorted(bandas)},
        "features": features,
    }


# ---------------------------------------------------------------------------
# Clustering: ¿las sorpresas vienen en grupo? (pregunta estrella)
# ---------------------------------------------------------------------------

def jornadas_publico(historico=None):
    """Jornadas LAE completas con % de apostantes: por jornada, lista de
    (pct_favorito_publico, sorpresa, fecha). Orden cronologico dentro de cada
    temporada (orden del archivo, jamas por numero entre temporadas)."""
    historico = historico if historico is not None else cargar_json(HISTORICO_LAE, {})
    jornadas = []
    for temporada, bloque in (historico.get("temporadas") or {}).items():
        for j in bloque.get("jornadas") or []:
            partidos = []
            for p in j.get("partidos") or []:
                if not (1 <= int(p.get("num") or 0) <= 14):
                    continue
                real = str(p.get("signo_oficial") or "").upper()
                porc = {"1": p.get("porc1"), "X": p.get("porcX"), "2": p.get("porc2")}
                if real not in SIGNOS or not all(isinstance(porc[s], (int, float)) for s in SIGNOS):
                    partidos = []
                    break
                favorito = favorito_de(porc)
                partidos.append({"pct_favorito": float(porc[favorito]),
                                 "sorpresa": real != favorito})
            if len(partidos) == 14:
                jornadas.append({"temporada": temporada, "jornada": j.get("jornada"),
                                 "fecha": parsear_fecha(j.get("fecha")), "partidos": partidos})
    return jornadas


def banda_publico(pct):
    if pct < 40:
        return "<40"
    if pct < 50:
        return "40-49"
    if pct < 60:
        return "50-59"
    if pct < 70:
        return "60-69"
    return ">=70"


def test_permutacion_varianza(jornadas, filtro_pct=None, permutaciones=PERMUTACIONES, semilla=SEMILLA):
    """Varianza observada del nº de sorpresas por jornada vs la distribucion
    nula por permutacion estratificada (se barajan las sorpresas entre
    partidos de la MISMA banda de % del favorito, rompiendo la agrupacion por
    jornada pero conservando la dificultad de cada partido)."""
    partidos = []  # (indice_jornada, banda, sorpresa)
    for idx, j in enumerate(jornadas):
        for p in j["partidos"]:
            if filtro_pct is not None and p["pct_favorito"] < filtro_pct:
                continue
            partidos.append((idx, banda_publico(p["pct_favorito"]), p["sorpresa"]))
    if not partidos:
        return None
    n_jornadas = len(jornadas)

    def varianza_conteos(sorpresas):
        conteos = [0] * n_jornadas
        for (idx, _, _), s in zip(partidos, sorpresas):
            conteos[idx] += 1 if s else 0
        media = sum(conteos) / n_jornadas
        return sum((c - media) ** 2 for c in conteos) / (n_jornadas - 1)

    observada = varianza_conteos([s for (_, _, s) in partidos])
    por_banda = {}
    for pos, (_, banda, s) in enumerate(partidos):
        por_banda.setdefault(banda, []).append(pos)
    rng = random.Random(semilla)
    mayores = 0
    suma = 0.0
    sorpresas = [s for (_, _, s) in partidos]
    for _ in range(permutaciones):
        permutada = list(sorpresas)
        for posiciones in por_banda.values():
            valores = [permutada[p] for p in posiciones]
            rng.shuffle(valores)
            for p, v in zip(posiciones, valores):
                permutada[p] = v
        var = varianza_conteos(permutada)
        suma += var
        if var >= observada:
            mayores += 1
    p_valor = mayores / permutaciones
    return {
        "jornadas": n_jornadas,
        "partidos": len(partidos),
        "varianza_observada": round(observada, 2),
        "varianza_media_permutada": round(suma / permutaciones, 2),
        "ratio": round(observada / (suma / permutaciones), 2) if suma else None,
        "p_valor": round(p_valor, 4),
        "permutaciones": permutaciones,
        "veredicto": "UTILIZABLE" if p_valor < 0.05 else "NADA",
    }


def analizar_clustering(filas_motor):
    jornadas = jornadas_publico()

    # C1 y C3
    c1 = test_permutacion_varianza(jornadas)
    c3 = test_permutacion_varianza(jornadas, filtro_pct=FAVORITO_CLARO_PUBLICO)

    # C2: persistencia de jornadas locas, dentro de cada temporada
    por_temporada = {}
    for j in jornadas:
        por_temporada.setdefault(j["temporada"], []).append(
            sum(p["sorpresa"] for p in j["partidos"]))
    locas, tras_loca, locas_tras_loca, total = 0, 0, 0, 0
    for serie in por_temporada.values():
        es_loca = [c >= JORNADA_LOCA_SORPRESAS for c in serie]
        total += len(es_loca)
        locas += sum(es_loca)
        for i in range(1, len(es_loca)):
            if es_loca[i - 1]:
                tras_loca += 1
                locas_tras_loca += 1 if es_loca[i] else 0
    base = 100 * locas / total if total else None
    tras = 100 * locas_tras_loca / tras_loca if tras_loca else None
    c2 = {
        "definicion": f"jornada loca = >={JORNADA_LOCA_SORPRESAS} sorpresas del favorito del publico (de 14)",
        "jornadas": total,
        "jornadas_locas": locas,
        "base_pct": round(base, 1) if base is not None else None,
        "tras_loca_n": tras_loca,
        "tras_loca_pct": round(tras, 1) if tras is not None else None,
    }
    if base is not None and tras is not None and tras_loca:
        c2.update(contraste(tras, tras_loca, base, total))
    else:
        c2["veredicto"] = "NADA"

    # C4: jornadas entre semana vs fin de semana (tasa de sorpresa del publico)
    entre, finde = [], []
    for j in jornadas:
        destino = entre if es_entre_semana(j["fecha"]) else (finde if j["fecha"] else None)
        if destino is None:
            continue
        destino.extend(p["sorpresa"] for p in j["partidos"])
    c4 = {
        "n_entre_semana": len(entre),
        "tasa_entre_semana_pct": round(100 * sum(entre) / len(entre), 1) if entre else None,
        "n_fin_de_semana": len(finde),
        "tasa_fin_de_semana_pct": round(100 * sum(finde) / len(finde), 1) if finde else None,
    }
    if entre and finde:
        c4.update(contraste(c4["tasa_entre_semana_pct"], len(entre),
                            c4["tasa_fin_de_semana_pct"], len(finde)))
    else:
        c4["veredicto"] = "NADA"

    # C5: dispersion con las probabilidades del motor (jornadas completas de A)
    por_jornada = {}
    for f in filas_motor:
        por_jornada.setdefault((f["temporada"], f["jornada"]), []).append(f)
    completas = [v for v in por_jornada.values() if len(v) == 14]
    c5 = None
    if len(completas) >= 5:
        conteos = [sum(f["sorpresa"] for f in v) for v in completas]
        esperados = [sum(1 - f["prob_favorito"] / 100 for f in v) for v in completas]
        var_dentro = [sum((1 - f["prob_favorito"] / 100) * (f["prob_favorito"] / 100) for f in v)
                      for v in completas]
        n = len(completas)
        media_c = sum(conteos) / n
        var_obs = sum((c - media_c) ** 2 for c in conteos) / (n - 1)
        media_e = sum(esperados) / n
        var_entre = sum((e - media_e) ** 2 for e in esperados) / (n - 1)
        var_teorica = sum(var_dentro) / n + var_entre
        c5 = {
            "jornadas_completas": n,
            "sorpresas_medias_por_jornada": round(media_c, 2),
            "esperadas_por_el_motor": round(media_e, 2),
            "varianza_observada": round(var_obs, 2),
            "varianza_si_independientes": round(var_teorica, 2),
            "ratio_dispersion": round(var_obs / var_teorica, 2) if var_teorica else None,
        }

    # C6 descriptivo: perfil de las sorpresas en jornadas locas vs normales
    sorpresas_locas, claras_locas, sorpresas_norm, claras_norm = 0, 0, 0, 0
    for j in jornadas:
        cuenta = sum(p["sorpresa"] for p in j["partidos"])
        for p in j["partidos"]:
            if not p["sorpresa"]:
                continue
            clara = p["pct_favorito"] >= FAVORITO_CLARO_PUBLICO
            if cuenta >= JORNADA_LOCA_SORPRESAS:
                sorpresas_locas += 1
                claras_locas += clara
            else:
                sorpresas_norm += 1
                claras_norm += clara
    c6 = {
        "descripcion": (
            "De las sorpresas de cada tipo de jornada, % que tumbaron a un favorito "
            f"claro del publico (>={FAVORITO_CLARO_PUBLICO:.0f}% de masa). Descriptivo, sin veredicto."),
        "sorpresas_en_jornadas_locas": sorpresas_locas,
        "pct_favorito_claro_en_locas": round(100 * claras_locas / sorpresas_locas, 1) if sorpresas_locas else None,
        "sorpresas_en_jornadas_normales": sorpresas_norm,
        "pct_favorito_claro_en_normales": round(100 * claras_norm / sorpresas_norm, 1) if sorpresas_norm else None,
    }

    return {
        "C1_permutacion_estratificada": c1,
        "C2_persistencia_jornada_loca": c2,
        "C3_permutacion_favoritos_claros": c3,
        "C4_jornada_entre_semana": c4,
        "C5_dispersion_motor": c5,
        "C6_perfil_sorpresas_jornada_loca": c6,
    }


# ---------------------------------------------------------------------------
# Veredicto global y candidatas
# ---------------------------------------------------------------------------

def extraer_candidatas(bloque_a, bloque_b):
    """Candidatas a señal nueva de La Valiente: UTILIZABLE, con la feature
    SUBIENDO la tasa de sorpresa, y coherente entre datasets cuando la feature
    existe en ambos (prerregistrado en el docstring)."""
    pares_equivalentes = {
        "A5_racha_favorito": "B4_racha_favorito",
        "A8_h2h_caotico": "B5_h2h_previo_caotico",
        "A9_favorito_visitante": "B2_favorito_visitante",
        "A10_entre_semana": "B3_entre_semana",
    }
    por_nombre = {f["feature"]: f for f in bloque_a["features"] + bloque_b["features"]}
    candidatas = []
    for f in bloque_a["features"] + bloque_b["features"]:
        if f.get("veredicto") != "UTILIZABLE" or (f.get("diff_puntos") or 0) <= 0:
            continue
        nombre = f["feature"]
        if nombre in ("A1_banda_prob_favorito", "B1_banda_cuota_favorito"):
            continue  # calibracion, no señal accionable: la prob YA esta en el motor
        gemela = pares_equivalentes.get(nombre) or next(
            (a for a, b in pares_equivalentes.items() if b == nombre), None)
        coherente = True
        if gemela and gemela in por_nombre:
            g = por_nombre[gemela]
            if g.get("diff_puntos") is not None and g["diff_puntos"] * f["diff_puntos"] < 0:
                coherente = False
        candidatas.append({
            "feature": nombre,
            "descripcion": f["descripcion"],
            "diff_puntos": f["diff_puntos"],
            "z": f["z"],
            "n_con": f["n_con"],
            "coherente_entre_datasets": coherente,
            "estado": ("candidata_pendiente_de_backtest_de_senal" if coherente
                       else "descartada_por_incoherencia_entre_datasets"),
        })
    return [c for c in candidatas if c["coherente_entre_datasets"]], candidatas


def analizar():
    filas_motor, bloque_a = analizar_dataset_motor()
    filas_cuotas, bloque_b = analizar_dataset_cuotas()
    clustering = analizar_clustering(filas_motor)
    candidatas, todas = extraer_candidatas(bloque_a, bloque_b)
    salida = {
        "version": 1,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": (
            "Estudio prerregistrado de precursores de sorpresa en NUESTROS datos "
            "(sorpresa = no gana el favorito). Prerregistro completo en el docstring "
            "de estudio_ver_sorpresas.py; umbrales fijados antes de calcular."),
        "prerregistro": {
            "veredicto": (f"UTILIZABLE: n_con>={N_MINIMO} y |diff|>=2*SE; DEBIL: >=1*SE; "
                          "clustering: p<0.05. Candidata solo si UTILIZABLE, sube la tasa "
                          "y es coherente entre datasets."),
            "aviso_multiples_contrastes": (
                "Con ~14 contrastes, un falso positivo a 2 SE es esperable: ninguna "
                "candidata se integra sin su propio backtest de señal prerregistrado."),
            "avisos_fuga": [
                "equipos_x_fiabilidad.json incluye los pocos partidos ya jugados de 26/27 (fuga minima declarada en A6/A7).",
                "El archivo H2H agregado solo se aplica a filas 26/27 (A8); en B5 se recalcula acumulado y limpio.",
            ],
        },
        "dataset_motor": bloque_a,
        "dataset_cuotas": bloque_b,
        "clustering": clustering,
        "candidatas_senal_valiente": candidatas,
        "utilizables_descartadas": [c for c in todas if not c["coherente_entre_datasets"]],
    }
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return salida


def _imprimir(salida):
    a, b, c = salida["dataset_motor"], salida["dataset_cuotas"], salida["clustering"]
    print(f"Dataset motor: {a['partidos']} partidos | sorpresa base {a['tasa_sorpresa_base_pct']}% "
          f"| tercer signo {a['tasa_sorpresa_maxima_pct']}%")
    print(f"Dataset cuotas: {b['partidos']} partidos | sorpresa base {b['tasa_sorpresa_base_pct']}%")
    print("  por banda de cuota:", {k: v["tasa_pct"] for k, v in b["tasa_por_banda_cuota"].items()})
    for f in a["features"] + b["features"]:
        print(f"  [{f.get('veredicto','?'):10}] {f['feature']}: con={f['tasa_sorpresa_con_pct']}% "
              f"(n={f['n_con']}) sin={f['tasa_sorpresa_sin_pct']}% (n={f['n_sin']}) "
              f"diff={f.get('diff_puntos')} z={f.get('z')}")
    for nombre, reg in c.items():
        print(f"  {nombre}: {json.dumps(reg, ensure_ascii=False)}")
    print("CANDIDATAS a señal de La Valiente:",
          [x["feature"] for x in salida["candidatas_senal_valiente"]] or "NINGUNA")
    print("Guardado en", SALIDA)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _imprimir(analizar())
