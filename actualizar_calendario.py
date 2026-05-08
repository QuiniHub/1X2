import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

FUENTES = {
    "primera": "https://fixturedownload.com/results/la-liga-2025",
    "segunda": "https://raw.githubusercontent.com/openfootball/spain/master/2025-26/segunda-division.csv"
}

OUT = Path("data")
OUT.mkdir(exist_ok=True)

def descargar(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")

def clean(x):
    return re.sub(r"\s+", " ", x).strip()

def extraer_primera():
    html = descargar(FUENTES["primera"])
    soup = BeautifulSoup(html, "html.parser")
    texto = clean(soup.get_text(" "))

    patron = re.compile(
        r"(\d{1,2})\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\s+(.+?)\s+(.+?)\s+(.+?)\s+(\d+\s-\s\d+|)$"
    )

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

    if len(jornadas) < 38:
        print(f"WARNING primera parcial: {len(jornadas)} jornadas")

    escribir("primera", FUENTES["primera"], jornadas)

def extraer_segunda():
    html = descargar(FUENTES["segunda"])
    print("Descargando Segunda División...")
    soup = BeautifulSoup(html, "html.parser")
    texto = clean(soup.get_text(" "))

    equipos = [
        "AD Ceuta FC", "Albacete", "Almería", "Burgos", "Cádiz", "Castellón",
        "Córdoba", "Cultural Leonesa", "Deportivo La Coruña", "Eibar",
        "FC Andorra", "Granada CF", "Huesca", "Las Palmas", "Leganés",
        "Málaga", "Mirandés", "Racing Santander", "Real Sociedad II",
        "Sporting Gijón", "Valladolid", "Zaragoza"
    ]

    equipos_re = "|".join(sorted(map(re.escape, equipos), key=len, reverse=True))

    patron = re.compile(
        rf"(\d{{1,2}}:\d{{2}})\s+(\d{{1,2}})\s+({equipos_re})\s+({equipos_re})\s+(.+?)\s+(Jugado|Programado|Aplazado|Suspendido)\s*(\d+\s*[–-]\s*\d+)?",
        re.I
    )

    jornadas = {}

    for m in patron.finditer(texto):
        hora, jornada, local, visitante, estadio, estado, resultado = m.groups()
        jornada = int(jornada)

        partido = {
            "fecha": "",
            "hora": hora,
            "local": clean(local),
            "visitante": clean(visitante),
            "estado": clean(estado),
            "resultado": clean(resultado or "").replace("–", "-")
        }

        jornadas.setdefault(jornada, []).append(partido)

    if len(jornadas) < 30:
        print(f"WARNING segunda parcial: {len(jornadas)} jornadas")

    escribir("segunda", FUENTES["segunda"], jornadas)

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

extraer_primera()
extraer_segunda()

print("Calendarios generados correctamente")
