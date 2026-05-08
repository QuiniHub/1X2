import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

FUENTES = {
    "primera": "https://www.matchesio.com/es/competition/la-liga-es/",
    "segunda": "https://www.matchesio.com/es/competition/segunda-division-es/"
}

OUT = Path("data")
OUT.mkdir(exist_ok=True)

def get_html(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")

def clean(x):
    return re.sub(r"\s+", " ", x).strip()

def extraer_calendario(nombre, url):
    html = get_html(url)
    soup = BeautifulSoup(html, "html.parser")
    texto = clean(soup.get_text(" "))

    equipos_primera = [
        "Alaves", "Athletic Club", "Atletico Madrid", "Barcelona", "Celta Vigo",
        "Elche", "Espanyol", "Getafe", "Girona", "Levante", "Mallorca",
        "Osasuna", "Oviedo", "Rayo Vallecano", "Real Betis", "Real Madrid",
        "Real Sociedad", "Sevilla", "Valencia", "Villarreal"
    ]

    equipos_segunda = [
        "AD Ceuta FC", "Albacete", "Almeria", "Burgos", "Cadiz", "Castellón",
        "Cordoba", "Cultural Leonesa", "Deportivo La Coruna", "Eibar",
        "FC Andorra", "Granada CF", "Huesca", "Las Palmas", "Leganes",
        "Malaga", "Mirandes", "Racing Santander", "Real Sociedad II",
        "Sporting Gijon", "Valladolid", "Zaragoza"
    ]

    equipos = equipos_primera if nombre == "primera" else equipos_segunda
    equipos_regex = "|".join(sorted(map(re.escape, equipos), key=len, reverse=True))

    patron = re.compile(
        rf"(\d{{1,2}}:\d{{2}})\s+(\d{{1,2}})\s+({equipos_regex})\s+({equipos_regex})\s+(.+?)\s+(Jugado|Programado|Aplazado|Suspendido)\s+(\d+–\d+|\d+-\d+|)",
        re.I
    )

    jornadas = {}

    for m in patron.finditer(texto):
        hora, jornada, local, visitante, ciudad_estadio, estado, resultado = m.groups()
        jornada = int(jornada)

        partido = {
            "hora": hora,
            "local": clean(local),
            "visitante": clean(visitante),
            "estado": clean(estado),
            "resultado": clean(resultado).replace("–", "-") if resultado else ""
        }

        jornadas.setdefault(jornada, []).append(partido)

    if len(jornadas) < 30:
        print(f"WARNING: calendario {nombre} parcial ({len(jornadas)} jornadas)")

    salida = {
        "competicion": nombre,
        "fuente": url,
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

for nombre, url in FUENTES.items():
    extraer_calendario(nombre, url)

print("Calendarios reales generados correctamente")
