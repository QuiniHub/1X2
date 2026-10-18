"""Backtest retrospectivo de La Valiente ANTES de desplegar (prerregistrado).

Reconstruye que valiente habria elegido el criterio de senal_valiente.py en
las jornadas 1-13 de 2026/27 con datos estrictamente pre-cierre:

- probabilidades del motor: snapshots INMUTABLES de data/backtesting/pre_cierre
  (los mismos del TEST B del boleto EV; congelados antes de cada cierre),
- % de apostantes LAE: data/memoria_ia/porcentajes_lae/2026_2027/ (reconstruidos
  de commits pre-cierre, ya auditados para el backtest del EV),
- señal sobrecompra: aprendizaje_ia.json SOLO de jornadas anteriores a la
  evaluada (sin fuga de futuro),
- señales revulsivo / empatador / H2H: ceses_actuales.json (los eventos llevan
  fecha y el efecto se reconstruye con los calendarios, como hace el motor),
  equipos_x_fiabilidad.json e historial_enfrentamientos.json. CAVEAT honesto:
  estos tres archivos son la foto de HOY -los umbrales son historicos
  (23/24-25/26) y apenas se mueven, pero la parte 26/27 del estudio de
  empatadores y la fiabilidad-nemesis incorporan jornadas ya jugadas, asi que
  esas dos señales tienen una fuga leve inevitable. Queda documentado en
  DECISION_LOG.md.

PRERREGISTRO v2 (14/10/2026, antes de re-ejecutar): se añaden los dos VETOS
aprobados por Marc (ver senal_valiente.py: nada contra grandes que casi nunca
empatan siendo favoritos, ni contra favoritos >=55%). REGLA DE DESPLIEGUE
prerregistrada: los vetos se despliegan solo si el backtest v2 mantiene el
veredicto VERDE y el ratio aciertos/esperados no baja del 1,30 de v1
(v1: 10 valientes, 4 aciertos, 3,08 esperados, 36,16 EUR / 10 EUR). Si
empeora, los vetos NO se despliegan y se reporta tal cual.
RESULTADO: v2 dio 9 valientes, 3 aciertos vs 2,87 esperados (ratio 1,05) y
17,10 EUR/9 EUR -> vetos NO desplegados; el JSON canonico es el criterio
vivo (sin vetos) y el experimento queda en "experimento_vetos_v2".

CRITERIOS PRERREGISTRADOS (escritos antes de la primera ejecucion):
- VERDE: aciertos reales >= esperados (suma de probabilidades declaradas) y
  al menos 2 aciertos.
- ROJO: aciertos < 60% de lo esperado -> se despliega IGUALMENTE en sombra,
  pero con la advertencia escrita en el bloque de la web y en DECISION_LOG.md
  (la muestra de 13 jornadas es pequeña y el criterio es distinto del selector
  ingenuo ya refutado el 14/10/2026: 1/13 real vs 28% declarado).
- Entre medias: NEUTRO (sombra sin advertencia roja, muestra insuficiente).

Salida: data/memoria_ia/backtest_valiente.json + resumen por pantalla.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from modelo_dixon_coles import clave_equipo
from optimizador_ev_premio import cargar_json, guardar_json
from senal_valiente import (
    SIGNOS,
    cargar_fuentes,
    elegir_valiente,
    jornadas_con_porcentajes,
    sorpresas_por_equipo,
    APUESTA_HIPOTETICA_EUR,
)
from actualizar_porcentajes_lae import ruta_porcentajes

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SALIDA = DATA / "memoria_ia" / "backtest_valiente.json"
PRE_CIERRE = DATA / "backtesting" / "pre_cierre"
APRENDIZAJE = DATA / "aprendizaje_ia.json"
ETIQUETA = "2026_2027"

UMBRAL_VERDE_ACIERTOS_MIN = 2
UMBRAL_ROJO_FRACCION = 0.6


def fixture_jornada(jornada):
    """num -> {local, visitante, fecha, signo_oficial} del fixture oficial."""
    datos = cargar_json(DATA / "jornadas" / f"jornada_{jornada}.json", {})
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


def partidos_snapshot(jornada, fixture):
    """Partidos del snapshot pre-cierre con la fecha inyectada del fixture
    (el snapshot no la guarda; la fecha del calendario es pre-cierre). Si los
    nombres no casan con el fixture, la fecha queda fuera -la señal revulsivo
    simplemente no se reconstruye para ese partido."""
    snapshot = cargar_json(PRE_CIERRE / f"jornada_{jornada}.json", {})
    partidos = []
    for p in (snapshot.get("prediccion") or {}).get("partidos") or []:
        num = p.get("num")
        if not (isinstance(num, int) and 1 <= num <= 14 and p.get("probabilidades")):
            continue
        fila = {
            "num": num,
            "local": p.get("local"),
            "visitante": p.get("visitante"),
            "probabilidades": p.get("probabilidades"),
            # para la señal favorito_distinto_mercado (prerregistro v3): el
            # mercado Losilla congelado en el propio snapshot pre-cierre
            "mercado_losilla": p.get("mercado_losilla"),
        }
        fx = fixture.get(num) or {}
        # Al menos UNO de los dos nombres debe casar (el num ya ancla el
        # partido): exigir los dos rompia con alias legitimos del propio
        # motor ("Celta B" en el snapshot vs "Celta Fortuna" en el fixture).
        fila["_fixture_ok"] = (
            clave_equipo(fx.get("local")) == clave_equipo(p.get("local"))
            or clave_equipo(fx.get("visitante")) == clave_equipo(p.get("visitante"))
        )
        if fila["_fixture_ok"]:
            fila["fecha"] = fx.get("fecha")
        partidos.append(fila)
    return partidos


def masa_jornada(jornada):
    registro = cargar_json(ruta_porcentajes(jornada, ETIQUETA), {})
    masa = {
        p["numero"]: p["porcentajes"]
        for p in registro.get("partidos") or []
        if isinstance(p.get("numero"), int) and p.get("porcentajes")
    }
    return masa if len(masa) >= 14 else None


def evaluar_criterio(aplicar_vetos=False, tipos_vetos=None, senales_suspendidas=None):
    """Corre el criterio sobre las jornadas con % LAE versionados y devuelve
    (filas, resumen). tipos_vetos (auditoria automatica, 15/10/2026) permite
    re-probar cada veto v2 POR SEPARADO como pide DECISION_LOG 14/10; con
    None el comportamiento es identico al original. senales_suspendidas
    (prerregistro v3, 17/10/2026) permite evaluar variantes del juego de
    señales -p.ej. {"favorito_distinto_mercado"} reproduce el criterio v1
    sin la señal nueva, {"h2h_caotico"} prueba su jubilacion."""
    detalle = (cargar_json(APRENDIZAJE, {}) or {}).get("detalle") or []
    jornadas = sorted(jornadas_con_porcentajes(ETIQUETA))
    fuentes_base = cargar_fuentes()
    filas = []
    for jornada in jornadas:
        fixture = fixture_jornada(jornada)
        if len(fixture) != 14:
            filas.append({"jornada": jornada, "estado": "fixture_incompleto"})
            continue
        partidos = partidos_snapshot(jornada, fixture)
        masa = masa_jornada(jornada)
        if len(partidos) != 14 or not masa:
            filas.append({"jornada": jornada, "estado": "sin_snapshot_o_masa"})
            continue
        fuentes = dict(fuentes_base)
        fuentes["sorpresas_equipo"] = sorpresas_por_equipo(detalle, set(jornadas), jornada)
        if senales_suspendidas is not None:
            fuentes["senales_suspendidas"] = set(senales_suspendidas)
        eleccion, evaluados, vetados, _candidatos = elegir_valiente(
            partidos, masa, fuentes, aplicar_vetos=aplicar_vetos,
            tipos_vetos=tipos_vetos)
        if eleccion is None:
            filas.append({
                "jornada": jornada,
                "estado": "sin_valiente",
                "candidatos_evaluados": evaluados,
                "partidos_vetados": vetados,
            })
            continue
        elegido = next(p for p in partidos if p["num"] == eleccion["num"])
        if not elegido["_fixture_ok"]:
            # el snapshot y el fixture no hablan del mismo partido: no se
            # puntua a ciegas (la numeracion/el emparejamiento no casan)
            filas.append({
                "jornada": jornada,
                "estado": "nombres_no_casan_con_fixture",
                "num": eleccion["num"],
                "partido": f"{eleccion['local']} - {eleccion['visitante']}",
            })
            continue
        signo_real = fixture[eleccion["num"]]["signo_oficial"]
        if signo_real not in SIGNOS:
            # se elige con datos pre-cierre pero SU partido aun no tiene signo
            # oficial (aplazado o jornada en juego): queda pendiente, no cuenta
            filas.append({
                "jornada": jornada,
                "estado": "valiente_pendiente",
                "num": eleccion["num"],
                "partido": f"{eleccion['local']} - {eleccion['visitante']}",
                "signo": eleccion["signo"],
                "prob_declarada": eleccion["prob_motor"],
                "masa_pct": eleccion["masa_pct"],
                "senales": [s["tipo"] for s in eleccion["senales"]],
            })
            continue
        acierto = signo_real == eleccion["signo"]
        masa_pct = float(eleccion["masa_pct"] or 0)
        filas.append({
            "jornada": jornada,
            "estado": "valiente",
            "candidatos_evaluados": evaluados,
            "partidos_vetados": vetados,
            "num": eleccion["num"],
            "partido": f"{eleccion['local']} - {eleccion['visitante']}",
            "signo": eleccion["signo"],
            "prob_declarada": eleccion["prob_motor"],
            "masa_pct": eleccion["masa_pct"],
            "senales": [s["tipo"] for s in eleccion["senales"]],
            "senales_textos": [s["texto"] for s in eleccion["senales"]],
            "signo_real": signo_real,
            "acierto": acierto,
            "pago_hipotetico_eur": round(100.0 / masa_pct * APUESTA_HIPOTETICA_EUR, 2)
            if acierto and masa_pct > 0 else 0.0,
        })

    valientes = [f for f in filas if f.get("estado") == "valiente"]
    aciertos = sum(1 for f in valientes if f["acierto"])
    esperados = round(sum(float(f["prob_declarada"]) for f in valientes) / 100.0, 2)
    cobrado = round(sum(f["pago_hipotetico_eur"] for f in valientes), 2)
    if valientes and aciertos >= esperados and aciertos >= UMBRAL_VERDE_ACIERTOS_MIN:
        veredicto = (
            "VERDE segun el prerregistro (aciertos >= esperados con >=2 aciertos): la señal "
            "merece la sombra, sigue sin merecer dinero."
        )
    elif not valientes or aciertos < UMBRAL_ROJO_FRACCION * esperados:
        veredicto = (
            "ROJO segun el prerregistro (aciertos < 60% de lo esperado): se despliega en sombra "
            "igualmente, con esta advertencia visible."
        )
    else:
        veredicto = (
            "NEUTRO segun el prerregistro (entre el 60% y el 100% de lo esperado): sombra sin "
            "advertencia roja, muestra insuficiente para concluir."
        )
    resumen = {
        "jornadas_evaluadas": len([f for f in filas if f.get("estado") != "fixture_incompleto"]),
        "valientes": len(valientes),
        "aciertos": aciertos,
        "esperados": esperados,
        "apostado_hipotetico_eur": round(len(valientes) * APUESTA_HIPOTETICA_EUR, 2),
        "cobrado_hipotetico_eur": cobrado,
        "veredicto": veredicto,
    }
    return filas, resumen


def _resumen_variante(nombre, susp):
    filas, res = evaluar_criterio(senales_suspendidas=susp)
    res = dict(res)
    res["variante"] = nombre
    res["ratio"] = round(res["aciertos"] / res["esperados"], 2) if res["esperados"] else None
    return filas, res


def ejecutar_backtest():
    """JSON canonico: el criterio VIVO (v3: sin vetos, sin h2h_caotico, con la
    señal favorito_distinto_mercado) + los experimentos documentados dentro
    (vetos v2 y variantes v3), cada uno con su regla y decision."""
    from senal_valiente import SENALES_RETIRADAS
    filas, resumen = evaluar_criterio(senales_suspendidas=set(SENALES_RETIRADAS))
    filas_v2, resumen_v2 = evaluar_criterio(aplicar_vetos=True,
                                            senales_suspendidas=set(SENALES_RETIRADAS))
    # Variantes del prerregistro v3 (17/10/2026), evaluadas POR SEPARADO:
    _, res_v1 = _resumen_variante("v1 (criterio 14/10)", {"favorito_distinto_mercado"})
    _, res_v1A = _resumen_variante("v1+A (señal mercado)", set())
    _, res_v1B = _resumen_variante("v1-B (sin h2h)", {"favorito_distinto_mercado", "h2h_caotico"})
    _, res_v1AB = _resumen_variante("v1+A-B (criterio vivo v3)", {"h2h_caotico"})
    ratio_v1 = round(resumen["aciertos"] / resumen["esperados"], 2) if resumen["esperados"] else None
    ratio_v2 = round(resumen_v2["aciertos"] / resumen_v2["esperados"], 2) if resumen_v2["esperados"] else None
    resultado = {
        "version": 2,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": (
            "Backtest retrospectivo prerregistrado de La Valiente en J1-J13 2026/27, con "
            "snapshots pre-cierre inmutables y % LAE versionados (sin fuga de futuro; caveat "
            "leve en empatadores/nemesis, documentado en DECISION_LOG.md)."
        ),
        "criterios_prerregistrados": {
            "verde": "aciertos >= esperados y aciertos >= 2",
            "rojo": "aciertos < 60% de esperados (se despliega en sombra con advertencia)",
            "neutro": "entre medias",
        },
        "jornadas": filas,
        "resumen": resumen,
        "experimento_palpitos_v3": {
            "descripcion": (
                "Prerregistro v3 (17/10/2026, DECISION_LOG): CAMBIO A = señal nueva "
                "favorito_distinto_mercado (estudio_ver_sorpresas: favorito motor != mercado "
                "-> el del motor cae 64,3%, n=56, z=3,0); CAMBIO B = jubilar h2h_caotico "
                "(sin soporte en nuestros datos). Reglas escritas ANTES de ejecutar: A se "
                "despliega si v1+A mantiene VERDE con ratio >=1,15 y aciertos >= v1; B se "
                "jubila si v1-B no reduce aciertos ni ratio."
            ),
            "variantes": [res_v1, res_v1A, res_v1B, res_v1AB],
            "decision": (
                "A DESPLEGADA (v1+A: VERDE, ratio {ra}, aciertos {aa} >= {a1}; en J1-J13 no "
                "cambio ningun pick, se estrena en vivo) y B JUBILADA (v1-B: mismos {ab} "
                "aciertos con ratio {rb} >= {r1}). Criterio vivo = v1+A-B."
            ).format(ra=res_v1A["ratio"], aa=res_v1A["aciertos"], a1=res_v1["aciertos"],
                     ab=res_v1B["aciertos"], rb=res_v1B["ratio"], r1=res_v1["ratio"]),
        },
        "experimento_vetos_v2": {
            "descripcion": (
                "Vetos aprobados por Marc (14/10/2026): nada contra grandes que casi nunca "
                "empatan siendo favoritos (<18% de X historico) ni contra favoritos >=55%. "
                "Regla de despliegue prerregistrada ANTES de ejecutar: solo si v2 mantiene "
                "VERDE y el ratio aciertos/esperados no baja del de v1."
            ),
            "ratio_v1": ratio_v1,
            "ratio_v2": ratio_v2,
            "resumen": resumen_v2,
            "jornadas": filas_v2,
            "decision": (
                (
                    "Cumpliria la regla de despliegue (ratio {v2} >= {v1} manteniendo VERDE), "
                    "pero activarlos de verdad exige decision explicita de Marc y nuevo "
                    "prerregistro (VETOS_V2_ACTIVOS sigue en False)."
                ) if (ratio_v1 is not None and ratio_v2 is not None and ratio_v2 >= ratio_v1
                      and resumen_v2["veredicto"].startswith("VERDE")) else (
                    "NO DESPLEGADOS: el ratio paso de {v1} a {v2} y el pago hipotetico de "
                    "{c1} a {c2} EUR. En la ejecucion original (14/10/2026) los vetos quitaron "
                    "2 de los 4 aciertos (favoritos de 55,3% y 55,8%) y los picks sustitutos "
                    "fallaron. El criterio vivo sigue siendo v1; reactivar los vetos exige "
                    "nuevo prerregistro con mas jornadas."
                )
            ).format(v1=ratio_v1, v2=ratio_v2,
                     c1=resumen["cobrado_hipotetico_eur"],
                     c2=resumen_v2["cobrado_hipotetico_eur"]),
        },
    }
    guardar_json(SALIDA, resultado)
    return resultado


def main():
    resultado = ejecutar_backtest()
    resumen = resultado["resumen"]
    print(
        f"Backtest La Valiente: {resumen['valientes']} valientes en "
        f"{resumen['jornadas_evaluadas']} jornadas; {resumen['aciertos']} aciertos vs "
        f"{resumen['esperados']} esperados; pago hipotetico {resumen['cobrado_hipotetico_eur']} EUR "
        f"sobre {resumen['apostado_hipotetico_eur']} EUR apostados."
    )
    print(resumen["veredicto"])
    for fila in resultado["jornadas"]:
        if fila.get("estado") == "valiente":
            print(
                f"  J{fila['jornada']}: {fila['partido']} -> {fila['signo']} "
                f"({fila['prob_declarada']}% vs masa {fila['masa_pct']}%) "
                f"[{', '.join(fila['senales'])}] real={fila['signo_real']} "
                f"{'ACIERTO' if fila['acierto'] else 'fallo'}"
            )
        else:
            print(f"  J{fila['jornada']}: {fila.get('estado')}")


if __name__ == "__main__":
    main()
