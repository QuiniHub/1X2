import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

FUENTES = {
    "primera": "https://fixturedownload.com/results/la-liga-2025",
    "segunda": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/es.2.json"
}

OUT = Path("data")
OUT.mkdir(exist_ok=True)

def descargar(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")

def clean(x):
    return re.sub(r"\s+", " ", str(x)).strip()

def escribir(nombre, fuente, jornadas):
    salida = {
        "competicion": nombre,
        "fuente": fuente,
        "jornadas": [
            {
                "jornada": j,
                "partidos": jornadas[j]
            }
            for j in sorted(jornadas)
        ]
    }

    Path(f"data/calendario_{nombre}.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Calendario {nombre}: {len(jornadas)} jornadas generadas")

def extraer_primera():
    html = descargar(FUENTES["primera"])
    soup = BeautifulSoup(html, "html.parser")
    texto = clean(soup.get_text(" "))

    equipos = [
        "Athletic Club", "Atlético de Madrid", "CA Osasuna", "Celta",
        "Deportivo Alavés", "Elche CF", "FC Barcelona", "Getafe CF",
        "Girona FC", "Levante UD", "Rayo Vallecano",
        "RCD Espanyol de Barcelona", "RCD Mallorca", "Real Betis",
        "Real Madrid", "Real Oviedo", "Real Sociedad", "Sevilla FC",
        "Valencia CF", "Villarreal CF"
    ]

    equipos_re = "|".join(sorted(map(re.escape, equipos), key=len, reverse=True))

    patron = re.compile(
        rf"(\d{{1,2}})\s+(\d{{2}}/\d{{2}}/\d{{4}})\s+(\d{{2}}:\d{{2}})\s+(.+?)\s+({equipos_re})\s+({equipos_re})\s+(\d+\s-\s\d+)?",
        re.I
    )

    jornadas = {}

    for m in patron.finditer(texto):
        jornada, fecha, hora, estadio, local, visitante, resultado = m.groups()
        jornada = int(jornada)

        partido = {
            "fecha": fecha,
            "hora": hora,
            "local": clean(local),
            "visitante": clean(visitante),
            "estado": "Programado" if not resultado else "Jugado",
            "resultado": clean(resultado or "")
        }

        jornadas.setdefault(jornada, []).append(partido)

    escribir("primera", FUENTES["primera"], jornadas)

def extraer_segunda():
    texto = descargar(FUENTES["segunda"])
    data = json.loads(texto)

    jornadas = {}

    for ronda in data.get("rounds", []):
        nombre_ronda = ronda.get("name", "")
        numero = re.search(r"(\d+)", nombre_ronda)

        if not numero:
            continue

        jornada = int(numero.group(1))

        partidos = []

        for match in ronda.get("matches", []):
            partido = {
                "fecha": match.get("date", ""),
                "hora": "",
                "local": clean(match.get("team1", {}).get("name", "")),
                "visitante": clean(match.get("team2", {}).get("name", "")),
                "estado": "Programado",
                "resultado": ""
            }

            score1 = match.get("score1")
            score2 = match.get("score2")

            if score1 is not None and score2 is not None:
                partido["estado"] = "Jugado"
                partido["resultado"] = f"{score1}-{score2}"

            partidos.append(partido)

        jornadas[jornada] = partidos

    escribir("segunda", FUENTES["segunda"], jornadas)

extraer_primera()
extraer_segunda()

print("Calendarios generados correctamente")
