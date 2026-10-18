"""La Valiente (modo sombra): UNA sorpresa formal por jornada, publicada y medida.

La investigacion mundial (INVESTIGACION_SORPRESAS.md, 14/10/2026) concluye que
nadie predice la sorpresa concreta, y el experimento del selector ingenuo
(maxima brecha modelo-vs-masa) lo confirmo en casa: 1/13 aciertos (8%) cuando
declaraba 28% -cosechaba las sobreestimaciones de X del propio motor (winner's
curse), no los errores de la masa. Las valientes que SI pagaron historicamente
(Regla 14a, 4 confirmaciones) tenian señal contextual dura detras. Este modulo
formaliza exactamente eso, SIN dinero hasta validarse.

CRITERIO PRERREGISTRADO (no se cambia despues de ver los datos):

Una valiente es un signo NO favorito del motor con probabilidad en [18, 45]
que cumple (a) y (b):

(a) SEÑAL contextual dura -al menos una de:
    - revulsivo_fuera: el equipo del signo juega el debut o 2o partido de un
      tecnico nuevo FUERA de casa (ceses_actuales.json + ajuste_revulsivo del
      motor; el unico escenario infravalorado por el mercado: +0,26 pts).
    - empatador / nemesis (solo signo X): equipo empatador historico de
      equipos_x_fiabilidad.json (x_pct>=32, o >=40 en su rol casa/fuera), o
      equipo nemesis nuestro (>=6 apariciones con <=33% de acierto).
    - h2h_caotico: tasa de sorpresa historica >=50% en este emparejamiento
      (historial_enfrentamientos.json, minimo 2 casos con cuotas).
    - sobrecompra_publico: el rival favorito viene de >=2 sorpresas positivas
      (victorias sin ser favorito del motor) en sus ultimos 3 partidos
      evaluados Y la masa LAE juega su signo >=10 puntos por encima de la
      probabilidad del motor -la overreaction documentada en la investigacion.

(b) FILTRO de pago: el % de apostantes LAE del signo esta al menos 8 puntos
    por debajo de la probabilidad del motor (si acierta, paga de verdad).

PRERREGISTRO v2 (14/10/2026, afinado aprobado por Marc tras revisar el
backtest v1: "meterle sorpresa al Real Madrid no es ser valiente, es suicidio
colectivo"): dos VETOS de partido, decididos y escritos ANTES de re-ejecutar
el backtest, con su regla de despliegue tambien prerregistrada (v2 se
despliega solo si mantiene el veredicto VERDE y el ratio aciertos/esperados
no baja del 1,30 de v1; si empeora, los vetos NO se despliegan y se reporta).
RESULTADO (14/10/2026): v2 dio 9 valientes, 3 aciertos vs 2,87 esperados
(ratio 1,05 < 1,30) y 17,10 EUR/9 EUR (vs 36,16/10 de v1) -los vetos quitaron
2 de los 4 aciertos (J6 Athletic 55,3% y J11 Castellon 55,8%) y los picks
sustitutos fallaron 3 de 4. El prerregistro manda: los vetos QUEDAN
DESACTIVADOS (VETOS_V2_ACTIVOS = False) y el criterio vivo sigue siendo v1;
el experimento completo esta en backtest_valiente.json y DECISION_LOG.md:

- VETO GRANDES: ningun pick en partidos donde participe un equipo con tasa
  historica de X < 18% (equipos_x_fiabilidad.json) Y ese equipo sea el
  favorito del motor (cubre Madrid 15,6% / Barcelona 9,8% / Atleti 17,2%
  sin hardcodear nombres; los grandes casi nunca empatan y Madrid es
  nuestro talisman 7/7).
- VETO FAVORITO CLARO: ningun pick en partidos donde el favorito del motor
  tenga probabilidad >= 55% -la valentia es para partidos parejos con
  señal, no para desafiar favoritos solidos.

Se elige COMO MAXIMO UNA por jornada: la de mayor ventaja sobre la masa
(prob motor - % masa); desempate por numero de señales y despues por numero de
partido. Si ninguna candidata cumple (a)+(b), NO hay valiente esa jornada:
decirlo es parte del diseño.

GRADUACION (marcador de sombra, data/memoria_ia/marcador_valiente.json):
con >=12 valientes evaluadas, si aciertos reales >= esperados (suma de
probabilidades declaradas) Y aciertos >= 3 -> "candidata_a_dinero" (avisar a
Marc); si aciertos < 60% de lo esperado -> "suspendida"; en otro caso sigue
"en_sombra". El pago hipotetico es ilustrativo: 1 EUR por valiente a cuota
justa pari-mutuel 100/% masa.

Exporta el bloque "valiente" en ultima_prediccion.json SIN tocar la
recomendacion conservadora, el boleto millonario ni el boleto EV. Jugar
dinero real lo decide siempre Marc.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from actualizar_porcentajes_lae import ruta_porcentajes, temporada_etiqueta
from modelo_dixon_coles import clave_equipo
from motor_prediccion_quiniela import (
    _norm_revulsivo,
    _partidos_oficiales_entre,
    clave_par_equipos_h2h,
)
from optimizador_ev_premio import cargar_json, guardar_json, porcentajes_masa

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCION = DATA / "predicciones" / "ultima_prediccion.json"
FUENTE_LOSILLA = DATA / "memoria_ia" / "fuente_losilla.json"
CESES = DATA / "memoria_ia" / "ceses_actuales.json"
ESTUDIO_X = DATA / "memoria_ia" / "equipos_x_fiabilidad.json"
HISTORIAL_H2H = DATA / "memoria_ia" / "historial_enfrentamientos.json"
APRENDIZAJE = DATA / "aprendizaje_ia.json"
MARCADOR = DATA / "memoria_ia" / "marcador_valiente.json"
BACKTEST = DATA / "memoria_ia" / "backtest_valiente.json"
JORNADAS_DIR = DATA / "jornadas"
PREDICCIONES_DIR = DATA / "predicciones"

SIGNOS = ("1", "X", "2")

# --- Umbrales prerregistrados (ver docstring; no tocar sin nuevo backtest) ---
PROB_MIN = 18.0
PROB_MAX = 45.0
FILTRO_PAGO_PUNTOS = 8.0
H2H_TASA_MIN = 50.0
H2H_CASOS_MIN = 2
SOBRECOMPRA_PUNTOS = 10.0
SORPRESAS_RECIENTES_MIN = 2
VENTANA_PARTIDOS_RIVAL = 3
EMPATADOR_X_PCT = 32.0
EMPATADOR_ROL_PCT = 40.0
NEMESIS_APARICIONES_MIN = 6
NEMESIS_ACIERTO_MAX = 33.0
VETO_GRANDES_X_PCT = 18.0
VETO_FAVORITO_CLARO_PROB = 55.0
# Prerregistro v2 fallido (14/10/2026): el backtest con vetos bajo el ratio
# aciertos/esperados de 1,30 a 1,05, asi que NO se despliegan. El codigo se
# conserva (testeado y reproducible) por si un futuro backtest con mas
# jornadas los reivindica -reactivarlos exige nuevo prerregistro.
VETOS_V2_ACTIVOS = False
GRADUACION_MIN_VALIENTES = 12
GRADUACION_MIN_ACIERTOS = 3
SUSPENSION_FRACCION = 0.6
APUESTA_HIPOTETICA_EUR = 1.0
# Freno de suspension POR SEÑAL (15/10/2026, meta-aprendizaje aprobado por
# Marc): una señal concreta (empatador, nemesis, h2h_caotico, revulsivo_fuera,
# sobrecompra_publico) se SUSPENDE sola -deja de contar como señal dura al
# elegir valiente- cuando acumula >=8 valientes propias en el marcador de
# sombra REAL y sus aciertos quedan por debajo del 50% de los esperados
# (suma de probabilidades declaradas). Se anuncia en el marcador y en el
# bloque publicado; ningun umbral estructural (18-45%, filtro de pago,
# vetos...) se auto-cambia. Reactivarla exige decision explicita de Marc.
SENAL_SUSPENSION_MIN_VALIENTES = 8
SENAL_SUSPENSION_FRACCION = 0.5
# Prerregistro v3 (17/10/2026, "los palpitos de la maquina"): señal nueva
# favorito_distinto_mercado (estudio_ver_sorpresas: favorito motor != mercado
# -> el del motor cae 64,3%, n=56, z=3,0) y jubilacion de h2h_caotico (sin
# soporte en nuestros datos), cada una con SU regla de despliegue escrita en
# DECISION_LOG ANTES del backtest. SENALES_RETIRADAS se fija con el resultado:
# las señales que esten aqui no cuentan en el criterio VIVO (el backtest las
# sigue pudiendo evaluar por variantes).
# RESULTADO v3 (17/10/2026, backtest por variantes en backtest_valiente.json):
# A (señal nueva) PASA su regla (v1+A VERDE, ratio 1,30>=1,15, aciertos 4>=4;
# en J1-J13 no cambio ningun pick: se estrena en vivo). B (jubilar h2h) PASA
# (v1-B: 9 valientes, mismos 4 aciertos, ratio sube 1,30->1,40: la unica
# valiente que aportaba era un fallo). Criterio vivo = v1 + A - B.
SENALES_RETIRADAS = frozenset({"h2h_caotico"})
PALPITOS_MAX = 3

CRITERIO_GRADUACION = (
    f"Prerregistrado: con >={GRADUACION_MIN_VALIENTES} valientes evaluadas, si aciertos "
    f"reales >= esperados (suma de probabilidades declaradas) y aciertos >= "
    f"{GRADUACION_MIN_ACIERTOS} -> 'candidata_a_dinero' (avisar a Marc); si aciertos < "
    f"{int(SUSPENSION_FRACCION * 100)}% de lo esperado -> 'suspendida'; en otro caso "
    "sigue 'en_sombra'. El criterio no se cambia despues de ver los datos."
)

AVISO_SOMBRA = (
    "Experimental, MODO SOMBRA: se publica y se mide, pero no entra en ningun boleto "
    "hasta graduarse con el criterio prerregistrado del marcador. Jugar dinero real "
    "lo decide siempre Marc."
)


# ---------------------------------------------------------------------------
# Señales contextuales duras
# ---------------------------------------------------------------------------

def senal_revulsivo(partido, signo, ceses=None, contador=None):
    """Señal revulsivo_fuera: el equipo del signo '2' juega el debut o el 2o
    partido de un tecnico nuevo FUERA de casa (el unico escenario que el
    mercado infravalora segun el estudio de 70 ceses). Usa la traza
    ajuste_revulsivo del motor si el partido la trae; si no (backtest),
    la reconstruye con ceses_actuales + calendarios, como el motor."""
    traza = partido.get("ajuste_revulsivo")
    if isinstance(traza, dict) and "activo" in traza:
        if traza.get("activo") and traza.get("lado") == "visitante" and signo == "2":
            return {
                "tipo": "revulsivo_fuera",
                "texto": (
                    f"{partido.get('visitante')} juega el {traza.get('etapa', 'debut')} de "
                    f"{traza.get('tecnico', 'su tecnico nuevo')} FUERA de casa: el unico escenario "
                    "de cambio de banquillo que el mercado infravalora (+0,26 pts, 70 ceses 23/24-25/26)."
                ),
            }
        return None
    if signo != "2":
        return None
    if ceses is None:
        ceses = (cargar_json(CESES, {}) or {}).get("ceses") or []
    try:
        fecha_partido = datetime.strptime(str(partido.get("fecha") or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    contador = contador or _partidos_oficiales_entre
    nombre = partido.get("visitante") or ""
    clave = _norm_revulsivo(nombre)
    for cese in ceses:
        if _norm_revulsivo(cese.get("equipo")) != clave:
            continue
        evento = None
        for campo in ("fecha_nuevo", "fecha_cese"):
            try:
                candidata = datetime.strptime(str(cese.get(campo) or "")[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
            if candidata <= fecha_partido and (evento is None or candidata > evento):
                evento = candidata
        if evento is None:
            continue
        jugados = contador(nombre, evento, fecha_partido)
        if jugados is None or jugados >= 2:
            continue
        etapa = "debut" if jugados == 0 else "2o partido"
        tecnico = cese.get("nuevo") or cese.get("interino") or "tecnico nuevo"
        return {
            "tipo": "revulsivo_fuera",
            "texto": (
                f"{nombre} juega el {etapa} de {tecnico} FUERA de casa: el unico escenario "
                "de cambio de banquillo que el mercado infravalora (+0,26 pts, 70 ceses 23/24-25/26)."
            ),
        }
    return None


def senal_empatador(partido, signo, estudio=None):
    """Señal empatador/nemesis, SOLO para signo X: alguno de los dos equipos
    es empatador historico (umbral general 32%, o 40% en su rol casa/fuera) o
    nemesis nuestro (>=6 apariciones con <=33% de acierto, fallos por X)."""
    if signo != "X":
        return None
    if estudio is None:
        estudio = cargar_json(ESTUDIO_X, {})
    empatadores = {f.get("equipo"): f for f in estudio.get("equipos_empatadores") or []}
    nemesis = {f.get("equipo"): f for f in estudio.get("fiabilidad_nuestra_por_equipo") or []}
    for nombre, rol in ((partido.get("local"), "casa"), (partido.get("visitante"), "fuera")):
        clave = clave_equipo(nombre)
        f = empatadores.get(clave)
        if f:
            rol_pct = f.get(f"x_{rol}_pct")
            if (f.get("x_pct") or 0) >= EMPATADOR_X_PCT:
                return {
                    "tipo": "empatador",
                    "texto": f"{nombre} empata el {f['x_pct']}% historico ({f.get('pj')} pj) -equipo empatador.",
                }
            if rol_pct is not None and rol_pct >= EMPATADOR_ROL_PCT:
                return {
                    "tipo": "empatador",
                    "texto": f"{nombre} empata el {rol_pct}% de sus partidos jugando {'en casa' if rol == 'casa' else 'fuera'} ({f.get('pj')} pj).",
                }
        n = nemesis.get(clave)
        if n and (n.get("apariciones") or 0) >= NEMESIS_APARICIONES_MIN and (n.get("acierto_pct") or 100) <= NEMESIS_ACIERTO_MAX:
            return {
                "tipo": "nemesis",
                "texto": (
                    f"{nombre} es nuestra nemesis: solo {n['acierto_pct']}% de acierto en "
                    f"{n['apariciones']} boletos ({n.get('fallos_por_x', 0)} fallos por X)."
                ),
            }
    return None


def senal_h2h(partido, historial=None):
    """Señal h2h_caotico: este emparejamiento concreto tiene una tasa de
    sorpresa historica >=50% con al menos 2 casos con cuotas."""
    if historial is None:
        historial = cargar_json(HISTORIAL_H2H, {})
    clave = clave_par_equipos_h2h(partido.get("local", ""), partido.get("visitante", ""))
    h2h = (historial.get("enfrentamientos") or {}).get(clave)
    if not h2h:
        return None
    casos = h2h.get("casos_con_cuotas") or 0
    tasa = h2h.get("tasa_sorpresa_historica")
    if casos >= H2H_CASOS_MIN and tasa is not None and tasa >= H2H_TASA_MIN:
        return {
            "tipo": "h2h_caotico",
            "texto": (
                f"Emparejamiento caotico: {tasa}% de sorpresas historicas entre "
                f"{partido.get('local')} y {partido.get('visitante')} ({casos} precedentes con cuotas)."
            ),
        }
    return None


def senal_favorito_mercado(partido, signo):
    """Señal favorito_distinto_mercado (prerregistro v3, 17/10/2026): el
    favorito del mercado Losilla en este partido es exactamente el signo
    candidato, distinto del favorito del motor. Fundamento: estudio propio
    estudio_ver_sorpresas.py -cuando motor y mercado no coinciden en
    favorito, el favorito del motor cae el 64,3% (n=56, z=3,0), la señal
    mas fuerte encontrada en casa. Usa mercado_losilla del propio partido
    (presente igual en la prediccion viva y en los snapshots pre-cierre:
    mismo camino, sin fuga)."""
    probs = partido.get("probabilidades") or {}
    mercado = partido.get("mercado_losilla") or {}
    if not probs or not mercado:
        return None
    try:
        fav_motor = max(SIGNOS, key=lambda s: float(probs.get(s) or 0))
        fav_mercado = max(SIGNOS, key=lambda s: float(mercado.get(s) or 0))
    except (TypeError, ValueError):
        return None
    if fav_mercado == fav_motor or fav_mercado != signo:
        return None
    return {
        "tipo": "favorito_distinto_mercado",
        "texto": (
            f"El mercado ve otro partido: Losilla hace favorito al {signo} "
            f"({float(mercado.get(signo) or 0):.0f}%) donde el motor prefiere el "
            f"{fav_motor} -cuando discrepan asi, el favorito del motor cae el 64% "
            "(56 casos propios, la señal mas fuerte de la casa)."
        ),
    }


def senal_sobrecompra(partido, signo, masa_partido, sorpresas_equipo):
    """Señal sobrecompra_publico: el rival (el equipo favorito del motor en
    este partido) viene de >=2 sorpresas positivas en sus ultimos 3 partidos
    evaluados Y la masa LAE juega su signo >=10 puntos por encima de la
    probabilidad del motor (overreaction del publico)."""
    probs = partido.get("probabilidades") or {}
    if not probs or not masa_partido:
        return None
    favorito = max(SIGNOS, key=lambda s: float(probs.get(s) or 0))
    if favorito == signo or favorito == "X":
        return None
    rival = partido.get("local") if favorito == "1" else partido.get("visitante")
    prob_fav = float(probs.get(favorito) or 0)
    masa_fav = float(masa_partido.get(favorito) or 0)
    if masa_fav < prob_fav + SOBRECOMPRA_PUNTOS:
        return None
    historial = (sorpresas_equipo or {}).get(clave_equipo(rival)) or []
    recientes = historial[-VENTANA_PARTIDOS_RIVAL:]
    n_sorpresas = sum(1 for s in recientes if s)
    if n_sorpresas < SORPRESAS_RECIENTES_MIN:
        return None
    return {
        "tipo": "sobrecompra_publico",
        "texto": (
            f"El publico sobre-compra a {rival}: viene de {n_sorpresas} sorpresas positivas en sus "
            f"ultimos {len(recientes)} partidos y la masa juega su signo al {masa_fav:.0f}% cuando el "
            f"motor le da {prob_fav:.0f}% (+{masa_fav - prob_fav:.0f} pts de overreaction)."
        ),
    }


def sorpresas_por_equipo(detalle, jornadas_validas, jornada_limite):
    """{clave_equipo: [bool, ...]} cronologico dentro de la temporada: True si
    el equipo GANO sin ser el favorito del motor (sorpresa positiva). Solo
    jornadas de jornadas_validas anteriores a jornada_limite -sin fuga de
    futuro, y sin mezclar temporadas (la numeracion se reinicia)."""
    por_equipo = {}
    items = [
        it for it in detalle or []
        if it.get("jornada") in jornadas_validas and it.get("jornada") < jornada_limite
        and str(it.get("signo_real") or "").upper() in SIGNOS
        and it.get("probabilidades_usadas")
    ]
    items.sort(key=lambda it: it.get("jornada"))
    for it in items:
        partes = str(it.get("partido") or "").split(" - ", 1)
        if len(partes) != 2:
            continue
        probs = it["probabilidades_usadas"]
        favorito = max(SIGNOS, key=lambda s: float(probs.get(s) or 0))
        signo_real = str(it["signo_real"]).upper()
        for nombre, signo_equipo in ((partes[0].strip(), "1"), (partes[1].strip(), "2")):
            clave = clave_equipo(nombre)
            if not clave:
                continue
            sorpresa = signo_real == signo_equipo and favorito != signo_equipo
            por_equipo.setdefault(clave, []).append(sorpresa)
    return por_equipo


def jornadas_con_porcentajes(etiqueta, hasta=60):
    """Jornadas de la temporada etiquetada con % LAE versionados: el conjunto
    de 'jornadas de esta temporada' sin depender de la numeracion (que se
    reinicia cada temporada)."""
    return {j for j in range(1, hasta + 1) if ruta_porcentajes(j, etiqueta).exists()}


# ---------------------------------------------------------------------------
# Seleccion de la valiente (nucleo puro, testeable)
# ---------------------------------------------------------------------------

def cargar_fuentes():
    return {
        "ceses": (cargar_json(CESES, {}) or {}).get("ceses") or [],
        "estudio_x": cargar_json(ESTUDIO_X, {}),
        "h2h": cargar_json(HISTORIAL_H2H, {}),
        "sorpresas_equipo": {},
        "contador": None,
    }


def vetos_partido(partido, estudio=None):
    """Vetos del prerregistro v2: si alguno aplica, el partido entero queda
    fuera de la seleccion (ninguna valiente, ni X ni contraria)."""
    probs = partido.get("probabilidades") or {}
    if not probs:
        return []
    favorito = max(SIGNOS, key=lambda s: float(probs.get(s) or 0))
    prob_fav = float(probs.get(favorito) or 0)
    vetos = []
    if prob_fav >= VETO_FAVORITO_CLARO_PROB:
        vetos.append({
            "tipo": "favorito_claro",
            "texto": (
                f"Favorito del motor al {prob_fav:.1f}% (>= {VETO_FAVORITO_CLARO_PROB:.0f}%): "
                "la valentia es para partidos parejos, no para desafiar favoritos solidos."
            ),
        })
    if estudio is None:
        estudio = cargar_json(ESTUDIO_X, {})
    empatadores = {f.get("equipo"): f for f in estudio.get("equipos_empatadores") or []}
    for nombre, signo_equipo in ((partido.get("local"), "1"), (partido.get("visitante"), "2")):
        if favorito != signo_equipo:
            continue
        f = empatadores.get(clave_equipo(nombre))
        if f and f.get("x_pct") is not None and float(f["x_pct"]) < VETO_GRANDES_X_PCT:
            vetos.append({
                "tipo": "grande_favorito",
                "texto": (
                    f"{nombre} es favorito y casi nunca empata ({f['x_pct']}% de X historico, "
                    f"< {VETO_GRANDES_X_PCT:.0f}%): contra un grande asi no hay valiente que valga."
                ),
            })
    return vetos


def evaluar_candidato(partido, signo, masa_partido, fuentes):
    """Devuelve el candidato (con señales y filtro de pago) o None."""
    probs = partido.get("probabilidades") or {}
    prob = float(probs.get(signo) or 0)
    if not (PROB_MIN <= prob <= PROB_MAX):
        return None
    masa = masa_partido.get(signo)
    if masa is None:
        return None
    masa = float(masa)
    if masa > prob - FILTRO_PAGO_PUNTOS:
        return None  # filtro de pago: si la masa ya lo juega, no paga
    # Señales suspendidas por el freno del marcador (15/10/2026): dejan de
    # contar como señal dura hasta que Marc decida reactivarlas.
    suspendidas = set(fuentes.get("senales_suspendidas") or ())
    senales = []
    for senal in (
        senal_revulsivo(partido, signo, fuentes.get("ceses"), fuentes.get("contador")),
        senal_empatador(partido, signo, fuentes.get("estudio_x")),
        senal_h2h(partido, fuentes.get("h2h")),
        senal_sobrecompra(partido, signo, masa_partido, fuentes.get("sorpresas_equipo")),
        senal_favorito_mercado(partido, signo),
    ):
        if senal and senal.get("tipo") not in suspendidas:
            senales.append(senal)
    if not senales:
        return None
    return {
        "num": partido.get("num"),
        "local": partido.get("local"),
        "visitante": partido.get("visitante"),
        "signo": signo,
        "prob_motor": round(prob, 1),
        "masa_pct": round(masa, 1),
        "ventaja_sobre_masa": round(prob - masa, 1),
        "senales": senales,
    }


def elegir_valiente(partidos, masa, fuentes, aplicar_vetos=None, tipos_vetos=None):
    """Como maximo UNA valiente: la de mayor ventaja sobre la masa entre las
    candidatas con señal dura + filtro de pago; desempate por numero de
    señales y despues por numero de partido (prerregistrado). Los vetos v2
    solo se aplican si aplicar_vetos es True (o VETOS_V2_ACTIVOS: hoy False,
    su prerregistro fallo). tipos_vetos (solo para la auditoria automatica,
    15/10/2026) limita que vetos se aplican -p.ej. {"grande_favorito"} para
    re-probar el veto grandes POR SEPARADO, como pide DECISION_LOG 14/10;
    no cambia nada cuando es None. Devuelve (eleccion, evaluados,
    partidos_vetados, candidatos_ordenados) -los candidatos ordenados son los
    PALPITOS del prerregistro v3 (mismo ranking de siempre; el nº1 es la
    valiente)."""
    if aplicar_vetos is None:
        aplicar_vetos = VETOS_V2_ACTIVOS
    candidatos = []
    evaluados = 0
    vetados = []
    for partido in partidos:
        probs = partido.get("probabilidades") or {}
        num = partido.get("num")
        masa_partido = (masa or {}).get(num) or {}
        if not probs or not masa_partido:
            continue
        vetos = vetos_partido(partido, fuentes.get("estudio_x")) if aplicar_vetos else []
        if tipos_vetos is not None:
            vetos = [v for v in vetos if v["tipo"] in tipos_vetos]
        if vetos:
            vetados.append({
                "num": num,
                "local": partido.get("local"),
                "visitante": partido.get("visitante"),
                "vetos": [v["tipo"] for v in vetos],
            })
            continue
        favorito = max(SIGNOS, key=lambda s: float(probs.get(s) or 0))
        for signo in SIGNOS:
            if signo == favorito:
                continue
            evaluados += 1
            candidato = evaluar_candidato(partido, signo, masa_partido, fuentes)
            if candidato:
                candidatos.append(candidato)
    if not candidatos:
        return None, evaluados, vetados, []
    candidatos.sort(key=lambda c: (-c["ventaja_sobre_masa"], -len(c["senales"]), c["num"] or 99))
    return candidatos[0], evaluados, vetados, candidatos


def advertencia_backtest():
    """Resumen honesto del backtest retrospectivo prerregistrado, incrustado
    en el propio bloque para que la web nunca lo venda sin contexto (mismo
    patron que el boleto EV)."""
    datos = cargar_json(BACKTEST, {})
    resumen = datos.get("resumen") or {}
    n = resumen.get("valientes")
    aciertos = resumen.get("aciertos")
    esperados = resumen.get("esperados")
    if not n or aciertos is None or esperados is None:
        return None
    veredicto = resumen.get("veredicto") or ""
    return (
        f"Backtest retrospectivo J1-J13 26/27 (criterio identico, sin fuga de futuro): "
        f"{aciertos} acierto(s) en {n} valientes cuando se esperaban {esperados:.1f}. "
        f"{veredicto} Muestra pequeña: por eso esta en modo sombra y no toca ningun boleto."
    )


def construir_bloque_no_disponible(motivo):
    return {
        "estado": "no_disponible",
        "modo": "sombra",
        "motivo": motivo,
        "generado_en": datetime.now(timezone.utc).isoformat(),
    }


def construir_bloque_valiente(prediccion, fuente_losilla, fuentes=None):
    """Nucleo del bloque `valiente` de ultima_prediccion.json (testeable)."""
    jornada = prediccion.get("jornada")
    partidos = sorted(
        [p for p in prediccion.get("partidos") or []
         if isinstance(p.get("num"), int) and 1 <= p["num"] <= 14],
        key=lambda p: p["num"],
    )
    if len(partidos) != 14 or any(not p.get("probabilidades") for p in partidos):
        return construir_bloque_no_disponible(
            "La prediccion no tiene los 14 partidos con probabilidades del motor."
        )
    masa, fuente_masa = porcentajes_masa(jornada, fuente_losilla)
    if not masa:
        return construir_bloque_no_disponible(
            "Sin % de apostantes LAE para esta jornada: sin masa no hay filtro de pago."
        )
    if fuentes is None:
        fuentes = cargar_fuentes()
        etiqueta = temporada_etiqueta(datetime.now())
        validas = jornadas_con_porcentajes(etiqueta)
        detalle = (cargar_json(APRENDIZAJE, {}) or {}).get("detalle") or []
        fuentes["sorpresas_equipo"] = sorpresas_por_equipo(
            detalle, validas, jornada if isinstance(jornada, int) else 0
        )
        # Freno del meta-aprendizaje (15/10/2026): las señales suspendidas por
        # el marcador real dejan de contar como señal dura en el bloque VIVO
        # (el backtest prerregistrado sigue evaluando el criterio v1 integro).
        fuentes.setdefault(
            "senales_suspendidas",
            senales_suspendidas_actuales() | set(SENALES_RETIRADAS),
        )
    eleccion, evaluados, vetados, candidatos = elegir_valiente(partidos, masa, fuentes)
    suspendidas = sorted(fuentes.get("senales_suspendidas") or [])
    base = {
        "modo": "sombra",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "jornada": jornada,
        "fuente_masa": fuente_masa,
        "candidatos_evaluados": evaluados,
        "partidos_vetados": vetados,
        "criterio": (
            "Signo no-favorito con prob motor 18-45%, al menos una señal contextual dura "
            "(revulsivo fuera, empatador/nemesis en X, sobrecompra del publico, favorito distinto "
            "en el mercado -v3) y % de masa LAE al menos 8 puntos por debajo de la prob del motor. "
            "Hasta 3 palpitos ordenados; el nº1 es la valiente y el unico que mide el marcador. "
            "(Vetos v2 no desplegados y señal h2h_caotico jubilada por backtest: DECISION_LOG "
            "14/10 y 17/10/2026.)"
        ),
        "aviso": AVISO_SOMBRA,
        "advertencia_backtest": advertencia_backtest(),
        "senales_suspendidas": suspendidas,
    }
    if eleccion is None:
        return {
            **base,
            "estado": "sin_valiente",
            "motivo": (
                "Ninguna candidata cumple señal dura + filtro de pago esta jornada. "
                "No se fuerza: declarar 'no hay valiente' es parte del diseño."
            ),
        }
    # Palpitos (prerregistro v3): hasta 3 candidatos con el MISMO ranking de
    # siempre. El nº1 es la valiente (unico que mide el marcador/graduacion);
    # los demas son informativos, cada uno con su intensidad legible.
    palpitos = []
    for i, c in enumerate(candidatos[:PALPITOS_MAX], start=1):
        palpitos.append({
            "orden": i,
            "es_la_valiente": i == 1,
            "intensidad": min(3, len(c["senales"])) + (1 if c["ventaja_sobre_masa"] >= 15 else 0),
            **c,
        })
    return {**base, "estado": "ok", "palpitos": palpitos, **eleccion}


# ---------------------------------------------------------------------------
# Marcador de sombra (se engancha al ciclo de aprendizaje)
# ---------------------------------------------------------------------------

def _signo_real_verificado(bloque, dir_jornadas):
    """Signo oficial del partido de la valiente, verificando ademas que los
    nombres del fixture coinciden (la numeracion de jornadas se reinicia cada
    temporada: sin esta verificacion, una J14 vieja podria puntuar una J14
    nueva). Basta con que UNO de los dos nombres case -el num ya ancla el
    partido y el propio motor usa alias legitimos ("Celta B"/"Celta Fortuna").
    None si la jornada aun no esta cerrada o ningun nombre casa."""
    datos = cargar_json(Path(dir_jornadas) / f"jornada_{bloque.get('jornada')}.json", {})
    for p in datos.get("partidos") or []:
        if p.get("num") != bloque.get("num"):
            continue
        if (clave_equipo(p.get("local")) != clave_equipo(bloque.get("local"))
                and clave_equipo(p.get("visitante")) != clave_equipo(bloque.get("visitante"))):
            return None
        signo = str(p.get("signo_oficial") or "").upper()
        return signo if signo in SIGNOS else None
    return None


def _atribucion_por_senal(evaluadas):
    """Atribucion POR SEÑAL del marcador (15/10/2026): una valiente con dos
    señales suma en ambas (la señal estuvo detras del pick). Con el freno
    prerregistrado de suspension: >=8 valientes propias y aciertos < 50% de
    esperados -> la señal se suspende sola."""
    por_senal = {}
    for v in evaluadas:
        prob = float(v.get("prob_declarada") or 0) / 100.0
        for tipo in v.get("senales") or []:
            reg = por_senal.setdefault(tipo, {"valientes": 0, "aciertos": 0, "esperados": 0.0})
            reg["valientes"] += 1
            reg["aciertos"] += 1 if v.get("acierto") else 0
            reg["esperados"] += prob
    for tipo, reg in por_senal.items():
        reg["esperados"] = round(reg["esperados"], 2)
        reg["suspendida"] = bool(
            reg["valientes"] >= SENAL_SUSPENSION_MIN_VALIENTES
            and reg["aciertos"] < SENAL_SUSPENSION_FRACCION * reg["esperados"]
        )
    return por_senal


def _resumen_marcador(valientes):
    evaluadas = [v for v in valientes if v.get("acierto") in (True, False)]
    aciertos = sum(1 for v in evaluadas if v["acierto"])
    esperados = round(sum(float(v.get("prob_declarada") or 0) for v in evaluadas) / 100.0, 2)
    cobrado = round(sum(float(v.get("pago_hipotetico_eur") or 0) for v in evaluadas), 2)
    estado = "en_sombra"
    if len(evaluadas) >= GRADUACION_MIN_VALIENTES:
        if aciertos >= esperados and aciertos >= GRADUACION_MIN_ACIERTOS:
            estado = "candidata_a_dinero"
        elif aciertos < SUSPENSION_FRACCION * esperados:
            estado = "suspendida"
    por_senal = _atribucion_por_senal(evaluadas)
    suspendidas = sorted(t for t, reg in por_senal.items() if reg["suspendida"])
    return {
        "evaluadas": len(evaluadas),
        "aciertos": aciertos,
        "esperados": esperados,
        "apostado_hipotetico_eur": round(len(evaluadas) * APUESTA_HIPOTETICA_EUR, 2),
        "cobrado_hipotetico_eur": cobrado,
        "estado": estado,
        "avisar_a_marc": estado == "candidata_a_dinero",
        "por_senal": por_senal,
        "senales_suspendidas": suspendidas,
        "criterio_suspension_senal": (
            f"Prerregistrado (15/10/2026): una señal con >={SENAL_SUSPENSION_MIN_VALIENTES} "
            f"valientes propias y aciertos < {int(SENAL_SUSPENSION_FRACCION * 100)}% de los "
            "esperados se suspende sola (deja de contar como señal dura) y se anuncia. "
            "Reactivarla la decide Marc."
        ),
    }


def senales_suspendidas_actuales(ruta_marcador=None):
    """Señales suspendidas por el freno prerregistrado, leidas del marcador
    de sombra REAL (no del backtest, que es una foto fija ya auditada)."""
    marcador = cargar_json(Path(ruta_marcador or MARCADOR), {})
    return set((marcador.get("resumen") or {}).get("senales_suspendidas") or [])


def actualizar_marcador_valiente(dir_predicciones=None, dir_jornadas=None,
                                 ruta_marcador=None, etiqueta=None, ahora=None):
    """Al cerrar cada jornada, registra si la valiente publicada acerto y
    actualiza el acumulado con el criterio de graduacion prerregistrado.
    Idempotente: cada (temporada, jornada) se registra una sola vez."""
    dir_predicciones = Path(dir_predicciones or PREDICCIONES_DIR)
    dir_jornadas = Path(dir_jornadas or JORNADAS_DIR)
    ruta_marcador = Path(ruta_marcador or MARCADOR)
    ahora = ahora or datetime.now(timezone.utc)
    etiqueta = etiqueta or temporada_etiqueta(datetime.now())

    marcador = cargar_json(ruta_marcador, {})
    valientes = marcador.get("valientes") or []
    registradas = {(v.get("temporada"), v.get("jornada")) for v in valientes}
    nuevas = 0
    for path in sorted(dir_predicciones.glob("jornada_*.json")):
        bloque = (cargar_json(path, {}) or {}).get("valiente") or {}
        if bloque.get("estado") != "ok":
            continue
        jornada = bloque.get("jornada")
        if (etiqueta, jornada) in registradas:
            continue
        signo_real = _signo_real_verificado(bloque, dir_jornadas)
        if signo_real is None:
            continue  # jornada aun abierta o fixture de otra temporada
        acierto = signo_real == str(bloque.get("signo") or "").upper()
        masa = float(bloque.get("masa_pct") or 0)
        pago = round(100.0 / masa * APUESTA_HIPOTETICA_EUR, 2) if acierto and masa > 0 else 0.0
        valientes.append({
            "temporada": etiqueta,
            "jornada": jornada,
            "num": bloque.get("num"),
            "partido": f"{bloque.get('local')} - {bloque.get('visitante')}",
            "signo": bloque.get("signo"),
            "prob_declarada": bloque.get("prob_motor"),
            "masa_pct": bloque.get("masa_pct"),
            "senales": [s.get("tipo") for s in bloque.get("senales") or []],
            "signo_real": signo_real,
            "acierto": acierto,
            "pago_hipotetico_eur": pago,
            "modo": "sombra",
            "registrado_en": ahora.isoformat(),
        })
        registradas.add((etiqueta, jornada))
        nuevas += 1

    resumen = _resumen_marcador(valientes)
    marcador = {
        "version": 1,
        "descripcion": (
            "Marcador de sombra de La Valiente: una sorpresa formal por jornada, publicada y "
            "medida sin dinero. El pago hipotetico es ilustrativo (1 EUR por valiente a cuota "
            "justa pari-mutuel 100/% masa)."
        ),
        "criterio_graduacion": CRITERIO_GRADUACION,
        "actualizado_en": ahora.isoformat(),
        "valientes": valientes,
        "resumen": resumen,
    }
    guardar_json(ruta_marcador, marcador)
    if resumen.get("senales_suspendidas"):
        print(
            "LA_VALIENTE_SENAL_SUSPENDIDA: "
            + ", ".join(resumen["senales_suspendidas"])
            + " suspendida(s) por el freno prerregistrado (>="
            + f"{SENAL_SUSPENSION_MIN_VALIENTES} valientes propias y aciertos < "
            + f"{int(SENAL_SUSPENSION_FRACCION * 100)}% de esperados). Dejan de contar "
            + "como señal dura; reactivarlas lo decide Marc."
        )
    if resumen["avisar_a_marc"]:
        print(
            "LA_VALIENTE_CANDIDATA_A_DINERO: el marcador de sombra cumple el criterio "
            f"prerregistrado ({resumen['aciertos']} aciertos vs {resumen['esperados']} esperados "
            f"en {resumen['evaluadas']} valientes). Avisar a Marc antes de tocar dinero."
        )
    return {"nuevas": nuevas, "resumen": resumen}


# ---------------------------------------------------------------------------
# Script de pipeline (patron optimizador_ev_premio)
# ---------------------------------------------------------------------------

def main():
    prediccion = cargar_json(PREDICCION, {})
    if not prediccion:
        print("Sin ultima_prediccion.json; nada que señalar.")
        return
    if not prediccion.get("prediccion_disponible") or not prediccion.get("prediccion_permitida"):
        if prediccion.pop("valiente", None) is not None:
            guardar_json(PREDICCION, prediccion)
        print("Prediccion bloqueada o no disponible; bloque valiente retirado.")
        return

    fuente_losilla = cargar_json(FUENTE_LOSILLA, {})
    bloque = construir_bloque_valiente(prediccion, fuente_losilla)
    prediccion["valiente"] = bloque
    guardar_json(PREDICCION, prediccion)

    # mantener coherente el espejo por jornada que escribe el motor
    jornada = prediccion.get("jornada")
    espejo = PREDICCIONES_DIR / f"jornada_{jornada}.json"
    if isinstance(jornada, int) and espejo.exists():
        datos_espejo = cargar_json(espejo, {})
        if datos_espejo.get("jornada") == jornada:
            datos_espejo["valiente"] = bloque
            guardar_json(espejo, datos_espejo)

    if bloque.get("estado") == "ok":
        senales = ", ".join(s["tipo"] for s in bloque.get("senales") or [])
        print(
            f"La Valiente (sombra) J{jornada}: {bloque['local']} - {bloque['visitante']} -> "
            f"{bloque['signo']} ({bloque['prob_motor']}% motor vs {bloque['masa_pct']}% masa; "
            f"señales: {senales})."
        )
    else:
        print(f"La Valiente (sombra) J{jornada}: {bloque.get('estado')} - {bloque.get('motivo')}")


if __name__ == "__main__":
    main()
