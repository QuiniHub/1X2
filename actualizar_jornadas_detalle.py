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
    texto = clean(soup.get_text(" "))

    fecha = ""
    mfecha = re.search(r"Jornada\s+\d+\s*-\s*([^P]+?)\s+P\.\s+Equipos", texto, re.I)
    if mfecha:
        fecha = clean(mfecha.group(1))

    partidos = []

    patron = re.compile(
        r"(\d{1,2})\s+(.+?)\s+-\s+(.+?)\s+"
        r"(\d+\s*-\s*\d+|[0-9M]\s*-\s*[0-9M])\s+"
        r"([12X])(?=\s+\d{1,2}\s+|$)",
        re.I
    )

    for m in patron.finditer(texto):
        num = int(m.group(1))
        if not 1 <= num <= 15:
            continue

        local = clean(m.group(2))
        visitante = clean(m.group(3))
        resultado = clean(m.group(4)).replace(" ", "")
        signo = clean(m.group(5))

        if num <= 14:
            partidos.append({
                "num": num,
                "local": local,
                "visitante": visitante,
                "resultado": resultado,
                "signo_oficial": signo,
                "signo_nuestro": "No jugada"
            })
        else:
            pleno15 = {
                "local": local,
                "visitante": visitante,
                "resultado": resultado,
                "signo_oficial": signo,
                "signo_nuestro": "No jugada"
            }

    if len(partidos) < 14:
        raise ValueError(f"Jornada {jornada}: solo {len(partidos)} partidos extraídos")

    datos = {
        "jornada": jornada,
        "fecha": fecha,
        "fuente": url,
        "partidos": partidos[:14],
        "pleno15": locals().get("pleno15", {
            "local": "Pleno al 15",
            "visitante": "",
            "resultado": "",
            "signo_oficial": "",
            "signo_nuestro": "No jugada"
        })
    }

    return datos

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
