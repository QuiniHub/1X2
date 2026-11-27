"""Utilidades comunes de los tests del paquete P4 (auditoria 26/11/2026).

No contiene tests: monta en un directorio temporal una jornada cerrada
(data/jornadas) y su snapshot pre-cierre (data/backtesting/pre_cierre), que es
de donde leen ahora los marcadores de sombra.
"""
import json
from pathlib import Path

EQUIPOS = [
    ("Alaves", "Getafe"), ("Betis", "Osasuna"), ("Celta", "Girona"), ("Sevilla", "Mallorca"),
    ("Cadiz", "Levante"), ("Valencia", "Villarreal"), ("Espanyol", "Elche"), ("Oviedo", "Leganes"),
    ("Granada", "Almeria"), ("Zaragoza", "Huesca"), ("Burgos", "Mirandes"), ("Albacete", "Castellon"),
    ("Eibar", "Racing"), ("Tenerife", "Cordoba"),
]
OTROS_EQUIPOS = [
    ("Arsenal", "Chelsea"), ("Liverpool", "Everton"), ("Juventus", "Torino"), ("Milan", "Inter"),
    ("Bayern", "Leipzig"), ("Ajax", "Feyenoord"), ("Porto", "Benfica"), ("Lyon", "Marsella"),
    ("Celtic", "Rangers"), ("Brujas", "Anderlecht"), ("Basilea", "Zurich"), ("Salzburgo", "Rapid"),
    ("Galatasaray", "Besiktas"), ("Olympiacos", "Panathinaikos"),
]


def partidos_jornada(nombres, fecha, signos=None):
    signos = signos or {}
    return [{"num": n, "local": local, "visitante": visitante, "fecha": fecha, "hora": "16:00",
             "signo_oficial": signos.get(n, "1")}
            for n, (local, visitante) in enumerate(nombres, start=1)]


def partidos_prediccion(nombres):
    return [{"num": n, "local": local, "visitante": visitante,
             "probabilidades": {"1": 50.0, "X": 28.0, "2": 22.0}, "signo_final": "1"}
            for n, (local, visitante) in enumerate(nombres, start=1)]


def escribir_jornada(dir_jornadas, jornada, fecha="2026-11-21", signos=None, nombres=None):
    dir_jornadas = Path(dir_jornadas)
    dir_jornadas.mkdir(parents=True, exist_ok=True)
    datos = {"jornada": jornada, "fecha": fecha,
             "partidos": partidos_jornada(nombres or EQUIPOS, fecha, signos)}
    (dir_jornadas / f"jornada_{jornada}.json").write_text(json.dumps(datos), encoding="utf-8")
    return datos


def escribir_snapshot(dir_snapshots, jornada, bloques=None, fecha="2026-11-21", nombres=None,
                      partidos=None, extra=None):
    dir_snapshots = Path(dir_snapshots)
    dir_snapshots.mkdir(parents=True, exist_ok=True)
    prediccion = {"jornada": jornada, "prediccion_disponible": True, "prediccion_permitida": True,
                  "partidos": partidos if partidos is not None else partidos_prediccion(nombres or EQUIPOS)}
    prediccion.update(bloques or {})
    snapshot = {"version": "1.2", "tipo": "prediccion_pre_cierre", "inmutable": True, "jornada": jornada,
                "creado_en": f"{fecha}T08:00:00+00:00", "refrescado_en": f"{fecha}T10:00:00+00:00",
                "primer_partido_utc": f"{fecha}T15:00:00+00:00", "prediccion": prediccion}
    snapshot.update(extra or {})
    (dir_snapshots / f"jornada_{jornada}.json").write_text(json.dumps(snapshot), encoding="utf-8")
    return snapshot


def montar_cierre(base, jornada, bloques, signos=None, fecha="2026-11-21", nombres=None,
                  nombres_fixture=None, fecha_snapshot=None):
    """Jornada (cerrada salvo que `signos` diga otra cosa) + snapshot pre-cierre
    con los `bloques` dados. Devuelve (dir_jornadas, dir_snapshots)."""
    base = Path(base)
    dir_jornadas, dir_snapshots = base / "jornadas", base / "snapshots"
    escribir_jornada(dir_jornadas, jornada, fecha, signos, nombres_fixture or nombres)
    escribir_snapshot(dir_snapshots, jornada, bloques, fecha_snapshot or fecha, nombres)
    return dir_jornadas, dir_snapshots
