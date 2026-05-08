import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

BASE_LISTADO = "https://www.quinielafutbol.info/resultados/jornadas-de-la-quiniela.html"
BASE = "https://www.quinielafutbol.info"
URL_J61 = "https://www.libertaddigital.com/deportes/liga/2025-2026/quiniela/61.html"

OUT = Path("data/jornadas")
OUT.mkdir(parents=True, exist_ok=True)

def get_html(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")

def clean(x):
    return re.sub(r"\s+", " ", x).strip()

def extraer_links_quinielafutbol():
    html = get_html(BASE_LISTADO)
    soup = BeautifulSoup(html, "html.parser")
    links = {}

    for a in soup.find_all("a", href=True):
        txt = clean(a.get_text(" "))
        href = a["href"]

        m = re.search(r"Jornada\s+(\d+)", txt, re.I)
        if not m:
            continue

        j = int(m.group(1))
        if 1 <= j <= 60 and "jornada-quiniela" in href:
            if href.startswith("/"):
                href = BASE + href
            links[j] = href

    return links

def extraer_jornada_qf(jornada, url):
    html = get_html(url)
    soup = BeautifulSoup(html, "html.parser")

    partidos = []
    pleno15 = {
        "local": "Pleno al 15",
        "visitante": "",
        "resultado": "",
        "signo_oficial": "",
        "signo_nuestro": "No jugada"
    }

    fecha = ""

    h1 = soup.find(["h1", "h2"])
    if h1:
        fecha = clean(h1.get_text(" "))

    for tr in soup.find_all("tr"):
        celdas = [clean(td.get_text(" ")) for td in tr.find_all(["td", "th"])]

        if len(celdas) < 4:
            continue

        if not celdas[0].isdigit():
            continue

        num = int(celdas[0])

        if num < 1 or num > 15:
            continue

        equipos = celdas[1]
        resultado = celdas[2]
        signo = celdas[3]

        if " - " in equipos:
            local, visitante = equipos.split(" - ", 1)
        else:
            local = equipos
            visitante = ""

        item = {
            "num": num,
            "local": clean(local),
            "visitante": clean(visitante),
            "resultado": clean(resultado),
            "signo_oficial": clean(signo),
            "signo_nuestro": "No jugada"
        }

        if num <= 14:
            partidos.append(item)
        else:
            pleno15 = item

    if len(partidos) < 14:
        raise SystemExit(f"ERROR jornada {jornada}: solo {len(partidos)} partidos reales extraídos")

    return {
        "jornada": jornada,
        "fecha": fecha,
        "fuente": url,
        "partidos": partidos,
        "pleno15": pleno15
    }
def extraer_jornada_61():
    html = get_html(URL_J61)
    soup = BeautifulSoup(html, "html.parser")
    texto = clean(soup.get_text(" "))

    equipos = [
        ("Elche", "Alavés"),
        ("Sevilla", "Espanyol"),
        ("Atlético de Madrid", "Celta"),
        ("Real Sociedad", "Betis"),
        ("Mallorca", "Villarreal"),
        ("Athletic de Bilbao", "Valencia"),
        ("Oviedo", "Getafe"),
        ("Rayo Vallecano", "Girona"),
        ("Ceuta", "Castellón"),
        ("Burgos", "Almería"),
        ("Málaga", "Sporting de Gijón"),
        ("Andorra", "Las Palmas"),
        ("Leganés", "Racing de Santander"),
        ("Córdoba", "Granada")
    ]

    partidos = []
    for i, (local, visitante) in enumerate(equipos, start=1):
        partidos.append({
            "num": i,
            "local": local,
            "visitante": visitante,
            "resultado": "Pendiente",
            "signo_oficial": "Pendiente",
            "signo_nuestro": "No jugada"
        })

    return {
        "jornada": 61,
        "fecha": "10/05/2026",
        "fuente": URL_J61,
        "partidos": partidos,
        "pleno15": {
            "local": "Barcelona",
            "visitante": "Real Madrid",
            "resultado": "Pendiente",
            "signo_oficial": "Pendiente",
            "signo_nuestro": "No jugada"
        }
    }

links = extraer_links_quinielafutbol()
print("Links encontrados:", len(links))

creadas = 0

for jornada in range(1, 61):
    if jornada not in links:
        raise SystemExit(f"ERROR: falta URL real para jornada {jornada}")

    datos = extraer_jornada_qf(jornada, links[jornada])
    Path(f"data/jornadas/jornada_{jornada}.json").write_text(
        json.dumps(datos, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    creadas += 1
    print(f"OK jornada {jornada}")

datos61 = extraer_jornada_61()
Path("data/jornadas/jornada_61.json").write_text(
    json.dumps(datos61, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
creadas += 1

print(f"Generadas {creadas} jornadas reales con equipos.")
