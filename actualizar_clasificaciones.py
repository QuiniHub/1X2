import csv
import json
from pathlib import Path
from urllib.request import urlopen

LIGAS = {
    "primera": "https://www.football-data.co.uk/mmz4281/2526/SP1.csv",
    "segunda": "https://www.football-data.co.uk/mmz4281/2526/SP2.csv",
}

def nueva_tabla():
    return {}

def equipo(tabla, nombre):
    if nombre not in tabla:
        tabla[nombre] = {
            "equipo": nombre,
            "pj": 0,
            "g": 0,
            "e": 0,
            "p": 0,
            "gf": 0,
            "gc": 0,
            "dg": 0,
            "pts": 0
        }
    return tabla[nombre]

def procesar_liga(url):
    data = urlopen(url, timeout=30).read().decode("utf-8", errors="ignore").splitlines()
    reader = csv.DictReader(data)
    tabla = nueva_tabla()

    for row in reader:
        local = row.get("HomeTeam")
        visitante = row.get("AwayTeam")
        gl = row.get("FTHG")
        gv = row.get("FTAG")

        if not local or not visitante or gl in ("", None) or gv in ("", None):
            continue

        gl = int(gl)
        gv = int(gv)

        l = equipo(tabla, local)
        v = equipo(tabla, visitante)

        l["pj"] += 1
        v["pj"] += 1

        l["gf"] += gl
        l["gc"] += gv
        v["gf"] += gv
        v["gc"] += gl

        if gl > gv:
            l["g"] += 1
            v["p"] += 1
            l["pts"] += 3
        elif gl < gv:
            v["g"] += 1
            l["p"] += 1
            v["pts"] += 3
        else:
            l["e"] += 1
            v["e"] += 1
            l["pts"] += 1
            v["pts"] += 1

    for e in tabla.values():
        e["dg"] = e["gf"] - e["gc"]

    return sorted(
        tabla.values(),
        key=lambda x: (x["pts"], x["dg"], x["gf"]),
        reverse=True
    )

salida = {
    "primera": procesar_liga(LIGAS["primera"]),
    "segunda": procesar_liga(LIGAS["segunda"])
}

Path("clasificaciones.json").write_text(
    json.dumps(salida, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("Clasificaciones actualizadas correctamente")
