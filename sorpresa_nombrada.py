"""Sorpresa Nombrada (modo sombra): UNA sorpresa por jornada, dicha ANTES del
cierre y en la franja donde de verdad viven las sorpresas, publicada y medida.

Origen (Marc, 21-22/11/2026, tras Athletic 0-1 Espanyol y Rayo 0-1 Valencia):
"te recuerdo tus respuestas cuando se da el resultado contra todo pronostico:
'ningun dato daba ese resultado', 'era el % con menos peso'... eso se ha de
saber ver ya". En J23 la sorpresa que nombramos a mano fue Madrid-Celta X (8%,
la de postal) y la real fue Rayo 0-1 Valencia (23%) con señales baratas a la
vista: el Valencia solo habia ganado fuera, banquillo nuevo esta temporada, y
el partido se jugaba el sabado (un fallo temprano deja el techo en 13 con
ocho partidos por jugar).

CRITERIO PRERREGISTRADO (22/11/2026; no se cambia despues de ver los datos):

Candidata = signo NO favorito del motor con probabilidad en [20, 33] (la
franja 20-30 con margen; nunca los 8% de los grandes). Cada candidata suma
SEÑALES (1 punto cada una), todas calculables con datos que ya estan en el
repo y SIN mirar el futuro (solo partidos jugados antes de la fecha del
partido):

  - especialista_de_rol: el equipo del signo solo gana en el rol que le toca
    hoy. Signo 2: visitante con >=2 victorias esta temporada, todas fuera y
    0 en casa (>=3 pj en casa). Signo 1: local con >=2 victorias, todas en
    casa y 0 fuera (>=3 pj fuera). (Valencia en Vallecas; Getafe en el
    Coliseum.)
  - banquillo_nuevo: el equipo del signo (1 o 2) cambio de entrenador esta
    temporada (ceses_actuales.json) y el nuevo ya lleva >=2 partidos (el
    debut/2o partido fuera ya lo cubre La Valiente como revulsivo). Un
    tecnico nuevo con el puesto en juego cada semana (Aguirre).
  - h2h_adverso_reciente: el ultimo cruce en ESTE campo (temporada actual o
    anterior) acabo con el signo de la candidata. (Celta gano 2-0 en el
    Bernabeu en 2025; Eibar gano en Montilivi en 25/26.)
  - empatador: solo signo X; reutiliza la señal empatador/nemesis de La
    Valiente (equipos_x_fiabilidad.json).
  - mercado_mas_alto: el mercado Losilla pre-cierre da al signo >=4 puntos
    mas que el motor (las cuotas son el benchmark; cuando ven mas sorpresa
    que nosotros, suele ser por algo).

Se nombra UNA: la de mas señales; desempate por hora del partido (ANTES el
que juega antes: el fallo temprano es el que mata el 14), despues por mayor
probabilidad y despues por numero. Hasta 3 "avisos" adicionales ordenados
igual (informativos, no miden). Sin candidatas con señal -> "sin sorpresa
nombrada": decirlo es parte del diseño. Se anota si el boleto conservador ya
cubre el signo (cubierta_por_boleto) -lo que mide el marcador es si SALIO,
no si se pago.

MARCADOR (data/memoria_ia/marcador_sorpresa_nombrada.json), prerregistrado:
acierto = el signo oficial del partido es el nombrado. Esperados = suma de
probabilidades declaradas. Con >=10 jornadas evaluadas: si aciertos >= 1,2 x
esperados y aciertos >= 4 -> "candidata" (avisar a Marc: podria pesar en la
prioridad de cobertura); si aciertos < 0,6 x esperados -> "despido"; en otro
caso "en_prueba". Freno POR SEÑAL (mismo que La Valiente): >=8 nombradas
propias y aciertos < 50% de esperados -> la señal se suspende sola y se
anuncia; reactivarla la decide Marc.

Exporta el bloque "sorpresa_nombrada" en ultima_prediccion.json SIN tocar la
recomendacion conservadora ni ningun boleto. Jugar dinero lo decide Marc.
"""
import json
import re
from datetime import datetime, timezone, date
from pathlib import Path

from actualizar_porcentajes_lae import temporada_etiqueta
from modelo_dixon_coles import clave_equipo
from optimizador_ev_premio import cargar_json, guardar_json
from senal_valiente import senal_empatador

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCION = DATA / "predicciones" / "ultima_prediccion.json"
PREDICCIONES_DIR = DATA / "predicciones"
JORNADAS_DIR = DATA / "jornadas"
CESES = DATA / "memoria_ia" / "ceses_actuales.json"
ESTUDIO_X = DATA / "memoria_ia" / "equipos_x_fiabilidad.json"
MARCADOR = DATA / "memoria_ia" / "marcador_sorpresa_nombrada.json"
BACKTEST = DATA / "memoria_ia" / "backtest_sorpresa_nombrada.json"
CALENDARIOS = (
    DATA / "calendario_primera.json",
    DATA / "calendario_segunda.json",
    DATA / "historico" / "calendario_primera_2025_2026.json",
    DATA / "historico" / "calendario_segunda_2025_2026.json",
)

SIGNOS = ("1", "X", "2")

# --- Umbrales prerregistrados (22/11/2026; no tocar sin nuevo backtest) ---
PROB_MIN = 20.0
PROB_MAX = 33.0
ROL_VICTORIAS_MIN = 2
ROL_PJ_CONTRARIO_MIN = 3
BANQUILLO_PARTIDOS_MIN = 2
MERCADO_PUNTOS = 4.0
AVISOS_MAX = 3
GRADUACION_MIN_JORNADAS = 10
GRADUACION_FACTOR = 1.2
GRADUACION_MIN_ACIERTOS = 4
DESPIDO_FRACCION = 0.6
SENAL_SUSPENSION_MIN = 8
SENAL_SUSPENSION_FRACCION = 0.5

AVISO_SOMBRA = (
    "Experimental, MODO SOMBRA: la sorpresa se nombra antes del cierre y se mide despues; "
    "no cambia ningun boleto hasta graduarse con el criterio prerregistrado del marcador."
)
CRITERIO = (
    "Signo no-favorito del motor con prob 20-33% y al menos una señal: especialista de rol, "
    "banquillo nuevo esta temporada, H2H adverso reciente en este campo, empatador (solo X) o "
    "mercado Losilla >=4 pts por encima del motor. Se nombra la de mas señales; desempate por "
    "hora (antes el que juega antes), probabilidad y numero."
)
CRITERIO_GRADUACION = (
    f"Prerregistrado 22/11/2026: con >={GRADUACION_MIN_JORNADAS} jornadas evaluadas, aciertos >= "
    f"{GRADUACION_FACTOR}x esperados y >={GRADUACION_MIN_ACIERTOS} aciertos -> candidata; aciertos < "
    f"{int(DESPIDO_FRACCION * 100)}% de esperados -> despido; si no, en prueba. Una señal con >="
    f"{SENAL_SUSPENSION_MIN} nombradas y aciertos < {int(SENAL_SUSPENSION_FRACCION * 100)}% de "
    "esperados se suspende sola."
)

_CAL_CACHE = None


# ---------------------------------------------------------------------------
# Datos: calendarios (sin fuga de futuro: siempre filtrados por fecha)
# ---------------------------------------------------------------------------

def _fecha(valor):
    try:
        return datetime.strptime(str(valor or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _resultado(p):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(p.get("resultado") or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _signo(gl, gv):
    return "1" if gl > gv else ("2" if gv > gl else "X")


def cargar_calendarios(rutas=None):
    """Lista plana de partidos jugados {local, visitante, fecha, gl, gv, signo}
    de 1a y 2a (temporada actual + anterior), cacheada por proceso."""
    global _CAL_CACHE
    if rutas is None and _CAL_CACHE is not None:
        return _CAL_CACHE
    partidos = []
    for ruta in rutas or CALENDARIOS:
        datos = cargar_json(ruta, {}) or {}
        for jornada in datos.get("jornadas") or []:
            for p in jornada.get("partidos") or []:
                res = _resultado(p)
                fecha = _fecha(p.get("fecha"))
                if not res or not fecha or not p.get("local") or not p.get("visitante"):
                    continue
                partidos.append({
                    "local": p["local"], "visitante": p["visitante"], "fecha": fecha,
                    "kl": clave_equipo(p["local"]), "kv": clave_equipo(p["visitante"]),
                    "gl": res[0], "gv": res[1], "signo": _signo(*res),
                })
    partidos.sort(key=lambda x: x["fecha"])
    if rutas is None:
        _CAL_CACHE = partidos
    return partidos


def _inicio_temporada(fecha):
    return date(fecha.year if fecha.month >= 7 else fecha.year - 1, 7, 1)


def balance_rol(equipo, hasta, partidos=None):
    """{'casa': {'pj','g'}, 'fuera': {'pj','g'}} de la temporada de `hasta`,
    solo con partidos jugados ANTES de esa fecha."""
    partidos = partidos if partidos is not None else cargar_calendarios()
    clave = clave_equipo(equipo)
    desde = _inicio_temporada(hasta)
    out = {"casa": {"pj": 0, "g": 0}, "fuera": {"pj": 0, "g": 0}}
    for p in partidos:
        if not (desde <= p["fecha"] < hasta):
            continue
        if p["kl"] == clave:
            out["casa"]["pj"] += 1
            out["casa"]["g"] += 1 if p["signo"] == "1" else 0
        elif p["kv"] == clave:
            out["fuera"]["pj"] += 1
            out["fuera"]["g"] += 1 if p["signo"] == "2" else 0
    return out


def ultimo_cruce_mismo_campo(local, visitante, hasta, partidos=None):
    """Ultimo partido local-visitante en ese mismo campo ANTES de `hasta`."""
    partidos = partidos if partidos is not None else cargar_calendarios()
    kl, kv = clave_equipo(local), clave_equipo(visitante)
    ultimo = None
    for p in partidos:
        if p["fecha"] >= hasta:
            break
        if p["kl"] == kl and p["kv"] == kv:
            ultimo = p
    return ultimo


def partidos_con_tecnico_nuevo(equipo, hasta, ceses, partidos=None):
    """None si el equipo no cambio de banquillo esta temporada (segun
    ceses_actuales); si cambio, cuantos partidos de liga ha dirigido ya el
    nuevo antes de `hasta` (desde fecha_nuevo, o fecha_cese si no hay)."""
    clave = clave_equipo(equipo)
    partidos = partidos if partidos is not None else cargar_calendarios()
    for c in ceses or []:
        if clave_equipo(c.get("equipo")) != clave:
            continue
        desde = _fecha(c.get("fecha_nuevo")) or _fecha(c.get("fecha_cese"))
        if not desde or desde >= hasta or _inicio_temporada(desde) != _inicio_temporada(hasta):
            continue
        return sum(1 for p in partidos if desde <= p["fecha"] < hasta and clave in (p["kl"], p["kv"]))
    return None


# ---------------------------------------------------------------------------
# Señales
# ---------------------------------------------------------------------------

def senal_especialista_de_rol(partido, signo, fecha, partidos=None):
    if signo not in ("1", "2") or not fecha:
        return None
    equipo = partido.get("local") if signo == "1" else partido.get("visitante")
    rol, contrario = ("casa", "fuera") if signo == "1" else ("fuera", "casa")
    b = balance_rol(equipo, fecha, partidos)
    if (b[rol]["g"] >= ROL_VICTORIAS_MIN and b[contrario]["g"] == 0
            and b[contrario]["pj"] >= ROL_PJ_CONTRARIO_MIN):
        donde = "en casa" if rol == "casa" else "fuera"
        return {"tipo": "especialista_de_rol",
                "texto": (f"{equipo} solo gana {donde}: {b[rol]['g']} victorias {donde} y 0 en "
                          f"{b[contrario]['pj']} partidos {'fuera' if contrario == 'fuera' else 'en casa'} esta temporada.")}
    return None


def senal_banquillo_nuevo(partido, signo, fecha, ceses, partidos=None):
    if signo not in ("1", "2") or not fecha:
        return None
    equipo = partido.get("local") if signo == "1" else partido.get("visitante")
    n = partidos_con_tecnico_nuevo(equipo, fecha, ceses, partidos)
    if n is not None and n >= BANQUILLO_PARTIDOS_MIN:
        return {"tipo": "banquillo_nuevo",
                "texto": f"{equipo} cambio de entrenador esta temporada: el nuevo ya lleva {n} partidos de liga."}
    return None


def senal_h2h_adverso_reciente(partido, signo, fecha, partidos=None):
    if not fecha:
        return None
    u = ultimo_cruce_mismo_campo(partido.get("local"), partido.get("visitante"), fecha, partidos)
    if u and u["signo"] == signo:
        return {"tipo": "h2h_adverso_reciente",
                "texto": (f"Ultimo cruce en este campo ({u['fecha'].isoformat()}): {u['local']} {u['gl']}-{u['gv']} "
                          f"{u['visitante']}, salio el {signo}.")}
    return None


def senal_mercado_mas_alto(partido, signo):
    mercado = partido.get("mercado_losilla") or {}
    probs = partido.get("probabilidades") or {}
    try:
        m = float(mercado.get(signo) or 0)
        p = float(probs.get(signo) or 0)
    except (TypeError, ValueError):
        return None
    if m > 0 and m >= p + MERCADO_PUNTOS:
        return {"tipo": "mercado_mas_alto",
                "texto": f"El mercado da al {signo} un {m:.0f}% frente al {p:.0f}% del motor (+{m - p:.0f} pts)."}
    return None


def senales_candidata(partido, signo, fecha, fuentes):
    partidos = fuentes.get("calendario")
    suspendidas = set(fuentes.get("senales_suspendidas") or ())
    senales = []
    for s in (
        senal_especialista_de_rol(partido, signo, fecha, partidos),
        senal_banquillo_nuevo(partido, signo, fecha, fuentes.get("ceses"), partidos),
        senal_h2h_adverso_reciente(partido, signo, fecha, partidos),
        senal_empatador(partido, signo, fuentes.get("estudio_x")),
        senal_mercado_mas_alto(partido, signo),
    ):
        if s and s.get("tipo") not in suspendidas:
            senales.append(s)
    return senales


# ---------------------------------------------------------------------------
# Eleccion
# ---------------------------------------------------------------------------

def _hora_orden(fechas, num):
    f = fechas.get(num) or {}
    return (str(f.get("fecha") or "9999-99-99"), str(f.get("hora") or "99:99"))


def elegir_sorpresa(partidos, fechas, fuentes):
    """(nombrada, candidatas_ordenadas, evaluadas). `fechas` = {num: {fecha, hora}}."""
    candidatas = []
    evaluadas = 0
    for partido in partidos:
        probs = partido.get("probabilidades") or {}
        num = partido.get("num")
        if not probs or not isinstance(num, int):
            continue
        favorito = max(SIGNOS, key=lambda s: float(probs.get(s) or 0))
        fecha = _fecha((fechas.get(num) or {}).get("fecha"))
        for signo in SIGNOS:
            if signo == favorito:
                continue
            prob = float(probs.get(signo) or 0)
            if not (PROB_MIN <= prob <= PROB_MAX):
                continue
            evaluadas += 1
            senales = senales_candidata(partido, signo, fecha, fuentes)
            if not senales:
                continue
            signo_final = str(partido.get("signo_final") or "")
            candidatas.append({
                "num": num, "local": partido.get("local"), "visitante": partido.get("visitante"),
                "signo": signo, "prob_motor": round(prob, 1), "senales": senales,
                "fecha": (fechas.get(num) or {}).get("fecha"), "hora": (fechas.get(num) or {}).get("hora"),
                "cubierta_por_boleto": signo in signo_final,
            })
    candidatas.sort(key=lambda c: (-len(c["senales"]), _hora_orden(fechas, c["num"]), -c["prob_motor"], c["num"]))
    return (candidatas[0] if candidatas else None), candidatas, evaluadas


def fechas_de_jornada(jornada, dir_jornadas=None):
    datos = cargar_json(Path(dir_jornadas or JORNADAS_DIR) / f"jornada_{jornada}.json", {}) or {}
    return {p.get("num"): {"fecha": p.get("fecha"), "hora": p.get("hora")}
            for p in datos.get("partidos") or [] if isinstance(p.get("num"), int)}


def cargar_fuentes(ruta_marcador=None):
    return {
        "ceses": (cargar_json(CESES, {}) or {}).get("ceses") or [],
        "estudio_x": cargar_json(ESTUDIO_X, {}),
        "calendario": cargar_calendarios(),
        "senales_suspendidas": senales_suspendidas_actuales(ruta_marcador),
    }


def advertencia_backtest():
    """Resumen honesto del backtest prerregistrado, incrustado en el bloque
    para que la web nunca lo venda sin contexto (patron La Valiente)."""
    r = (cargar_json(BACKTEST, {}) or {}).get("resumen") or {}
    if not r.get("nombradas"):
        return None
    cs, ss = r.get("candidatas_con_senal") or {}, r.get("candidatas_sin_senal") or {}
    return (
        f"Backtest retrospectivo J1-J22 26/27: {r['aciertos']} aciertos en {r['nombradas']} nombradas cuando se esperaban "
        f"{r['esperados']:.1f} ({r.get('vistas_y_no_pagadas', 0)} vistas y no pagadas). A nivel de candidata las señales "
        f"apenas separan ({cs.get('salieron')}/{cs.get('total')} con señal vs {ss.get('salieron')}/{ss.get('total')} sin). "
        "Por eso esta en sombra: vale la disciplina de nombrar; el marcador real decide."
    )


def construir_bloque_sorpresa(prediccion, fechas=None, fuentes=None):
    """Nucleo del bloque `sorpresa_nombrada` (testeable, sin tocar disco si se
    pasan fechas y fuentes)."""
    jornada = prediccion.get("jornada")
    base = {"modo": "sombra", "generado_en": datetime.now(timezone.utc).isoformat(),
            "jornada": jornada, "criterio": CRITERIO, "aviso": AVISO_SOMBRA}
    partidos = sorted([p for p in prediccion.get("partidos") or []
                       if isinstance(p.get("num"), int) and 1 <= p["num"] <= 14], key=lambda p: p["num"])
    if len(partidos) != 14 or any(not p.get("probabilidades") for p in partidos):
        return {**base, "estado": "no_disponible", "motivo": "La prediccion no tiene los 14 partidos con probabilidades."}
    if fechas is None:
        fechas = fechas_de_jornada(jornada) if isinstance(jornada, int) else {}
    if fuentes is None:
        fuentes = cargar_fuentes()
    nombrada, candidatas, evaluadas = elegir_sorpresa(partidos, fechas, fuentes)
    base["candidatas_evaluadas"] = evaluadas
    base["advertencia_backtest"] = advertencia_backtest()
    base["senales_suspendidas"] = sorted(fuentes.get("senales_suspendidas") or [])
    if not nombrada:
        return {**base, "estado": "sin_sorpresa_nombrada",
                "motivo": "Ninguna candidata de la franja 20-33% tiene señal esta jornada. No se fuerza: decirlo es parte del diseño."}
    avisos = [{"orden": i, **c} for i, c in enumerate(candidatas[1:AVISOS_MAX + 1], start=2)]
    return {**base, "estado": "ok", **nombrada, "avisos": avisos}


# ---------------------------------------------------------------------------
# Marcador de sombra
# ---------------------------------------------------------------------------

def _signo_real(bloque, dir_jornadas):
    datos = cargar_json(Path(dir_jornadas) / f"jornada_{bloque.get('jornada')}.json", {}) or {}
    for p in datos.get("partidos") or []:
        if p.get("num") != bloque.get("num"):
            continue
        if (clave_equipo(p.get("local")) != clave_equipo(bloque.get("local"))
                and clave_equipo(p.get("visitante")) != clave_equipo(bloque.get("visitante"))):
            return None
        signo = str(p.get("signo_oficial") or "").upper()
        return signo if signo in SIGNOS else None
    return None


def _por_senal(evaluadas):
    out = {}
    for v in evaluadas:
        prob = float(v.get("prob_declarada") or 0) / 100.0
        for tipo in v.get("senales") or []:
            r = out.setdefault(tipo, {"nombradas": 0, "aciertos": 0, "esperados": 0.0})
            r["nombradas"] += 1
            r["aciertos"] += 1 if v.get("acierto") else 0
            r["esperados"] += prob
    for r in out.values():
        r["esperados"] = round(r["esperados"], 2)
        r["suspendida"] = bool(r["nombradas"] >= SENAL_SUSPENSION_MIN
                               and r["aciertos"] < SENAL_SUSPENSION_FRACCION * r["esperados"])
    return out


def resumen_marcador(registros):
    evaluadas = [r for r in registros if r.get("estado") == "nombrada" and r.get("acierto") in (True, False)]
    aciertos = sum(1 for r in evaluadas if r["acierto"])
    esperados = round(sum(float(r.get("prob_declarada") or 0) for r in evaluadas) / 100.0, 2)
    cubiertas = sum(1 for r in evaluadas if r.get("cubierta_por_boleto"))
    vistas_no_pagadas = sum(1 for r in evaluadas if r["acierto"] and not r.get("cubierta_por_boleto"))
    veredicto = "en_prueba"
    if len(evaluadas) >= GRADUACION_MIN_JORNADAS:
        if aciertos >= GRADUACION_FACTOR * esperados and aciertos >= GRADUACION_MIN_ACIERTOS:
            veredicto = "candidata"
        elif aciertos < DESPIDO_FRACCION * esperados:
            veredicto = "despido"
    por_senal = _por_senal(evaluadas)
    return {
        "jornadas_evaluadas": len(evaluadas),
        "jornadas_sin_sorpresa": sum(1 for r in registros if r.get("estado") == "sin_sorpresa_nombrada"),
        "aciertos": aciertos, "esperados": esperados,
        "cubiertas_por_boleto": cubiertas, "vistas_y_no_pagadas": vistas_no_pagadas,
        "veredicto": veredicto, "avisar_a_marc": veredicto == "candidata",
        "por_senal": por_senal,
        "senales_suspendidas": sorted(t for t, r in por_senal.items() if r["suspendida"]),
        "criterio_graduacion": CRITERIO_GRADUACION,
    }


def senales_suspendidas_actuales(ruta_marcador=None):
    marcador = cargar_json(Path(ruta_marcador or MARCADOR), {}) or {}
    return set((marcador.get("resumen") or {}).get("senales_suspendidas") or [])


def registro_desde_bloque(bloque, signo_real, etiqueta, ahora):
    if bloque.get("estado") != "ok":
        return {"temporada": etiqueta, "jornada": bloque.get("jornada"), "estado": "sin_sorpresa_nombrada",
                "registrado_en": ahora.isoformat()}
    return {
        "temporada": etiqueta, "jornada": bloque.get("jornada"), "estado": "nombrada",
        "num": bloque.get("num"), "partido": f"{bloque.get('local')} - {bloque.get('visitante')}",
        "signo": bloque.get("signo"), "prob_declarada": bloque.get("prob_motor"),
        "senales": [s.get("tipo") for s in bloque.get("senales") or []],
        "cubierta_por_boleto": bool(bloque.get("cubierta_por_boleto")),
        "fecha": bloque.get("fecha"), "hora": bloque.get("hora"),
        "signo_real": signo_real, "acierto": signo_real == bloque.get("signo"),
        "registrado_en": ahora.isoformat(),
    }


def actualizar_marcador(dir_predicciones=None, dir_jornadas=None, ruta_marcador=None, etiqueta=None, ahora=None):
    """Al cerrar cada jornada con bloque publicado, anota si la sorpresa
    nombrada SALIO. Idempotente por (temporada, jornada)."""
    dir_predicciones = Path(dir_predicciones or PREDICCIONES_DIR)
    dir_jornadas = Path(dir_jornadas or JORNADAS_DIR)
    ruta_marcador = Path(ruta_marcador or MARCADOR)
    ahora = ahora or datetime.now(timezone.utc)
    etiqueta = etiqueta or temporada_etiqueta(datetime.now())
    marcador = cargar_json(ruta_marcador, {}) or {}
    registros = marcador.get("jornadas") or []
    vistas = {(r.get("temporada"), r.get("jornada")) for r in registros}
    nuevas = 0
    for path in sorted(dir_predicciones.glob("jornada_*.json")):
        snapshot = cargar_json(path, {}) or {}
        bloque = snapshot.get("sorpresa_nombrada") or {}
        if bloque.get("estado") not in ("ok", "sin_sorpresa_nombrada"):
            continue
        jornada = bloque.get("jornada")
        if not isinstance(jornada, int) or (etiqueta, jornada) in vistas:
            continue
        datos = cargar_json(dir_jornadas / f"jornada_{jornada}.json", {}) or {}
        partidos = datos.get("partidos") or []
        if not partidos or any(str(p.get("signo_oficial") or "").upper() not in SIGNOS for p in partidos):
            continue  # jornada abierta
        signo_real = _signo_real(bloque, dir_jornadas) if bloque.get("estado") == "ok" else None
        if bloque.get("estado") == "ok" and signo_real is None:
            continue  # nombres no casan (jornada de otra temporada)
        registros.append(registro_desde_bloque(bloque, signo_real, etiqueta, ahora))
        vistas.add((etiqueta, jornada))
        nuevas += 1
    if not nuevas and marcador:
        return {"nuevas": 0, "resumen": marcador.get("resumen") or {}}
    resumen = resumen_marcador(registros)
    guardar_json(ruta_marcador, {"version": 1, "actualizado_en": ahora.isoformat(), "modo": "sombra",
                                 "resumen": resumen, "jornadas": registros})
    return {"nuevas": nuevas, "resumen": resumen}


# ---------------------------------------------------------------------------
# Script de pipeline (patron radar_tormenta)
# ---------------------------------------------------------------------------

def main():
    prediccion = cargar_json(PREDICCION, {})
    if not prediccion:
        print("Sin ultima_prediccion.json; nada que nombrar.")
        return
    if not prediccion.get("prediccion_disponible") or not prediccion.get("prediccion_permitida"):
        if prediccion.pop("sorpresa_nombrada", None) is not None:
            guardar_json(PREDICCION, prediccion)
        print("Prediccion bloqueada o no disponible; bloque sorpresa_nombrada retirado.")
        return
    bloque = construir_bloque_sorpresa(prediccion)
    prediccion["sorpresa_nombrada"] = bloque
    guardar_json(PREDICCION, prediccion)
    jornada = prediccion.get("jornada")
    espejo = PREDICCIONES_DIR / f"jornada_{jornada}.json"
    if isinstance(jornada, int) and espejo.exists():
        datos = cargar_json(espejo, {})
        if datos.get("jornada") == jornada:
            datos["sorpresa_nombrada"] = bloque
            guardar_json(espejo, datos)
    if bloque.get("estado") == "ok":
        print(f"Sorpresa nombrada (sombra) J{jornada}: P{bloque['num']} {bloque['local']} - {bloque['visitante']} "
              f"signo {bloque['signo']} ({bloque['prob_motor']}%), señales: "
              f"{', '.join(s['tipo'] for s in bloque['senales'])}; cubierta por boleto: {bloque['cubierta_por_boleto']}")
    else:
        print(f"Sorpresa nombrada (sombra) J{jornada}: {bloque.get('estado')} - {bloque.get('motivo')}")


if __name__ == "__main__":
    main()
