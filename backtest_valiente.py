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


def ejecutar_backtest():
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
        eleccion, evaluados = elegir_valiente(partidos, masa, fuentes)
        if eleccion is None:
            filas.append({
                "jornada": jornada,
                "estado": "sin_valiente",
                "candidatos_evaluados": evaluados,
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
    resultado = {
        "version": 1,
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
        "resumen": {
            "jornadas_evaluadas": len([f for f in filas if f.get("estado") != "fixture_incompleto"]),
            "valientes": len(valientes),
            "aciertos": aciertos,
            "esperados": esperados,
            "apostado_hipotetico_eur": round(len(valientes) * APUESTA_HIPOTETICA_EUR, 2),
            "cobrado_hipotetico_eur": cobrado,
            "veredicto": veredicto,
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
