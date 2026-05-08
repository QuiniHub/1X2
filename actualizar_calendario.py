import json
import re
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

FUENTES = {
    "primera": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/es.1.json",
    "segunda": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/es.2.json"
}

LALIGA_SEGUNDA_RESULTADOS = "https://www.laliga.com/laliga-hypermotion/resultados/2025-26/jornada-{}"

Path("data").mkdir(exist_ok=True)

def descargar(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")

def clean(x):
    return re.sub(r"\s+", " ", str(x)).strip()

def normalizar(txt):
    txt = clean(txt).lower()
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii")

    reemplazos = {
        "ud ": "",
        "cd ": "",
        "cf ": "",
        "sd ": "",
        "fc ": "",
        "real ": "",
        "club ": "",
        "deportivo ": "",
        "la coruna": "coruna",
        "racing de santander": "racing santander",
        "sporting de gijon": "sporting gijon",
        "almeria": "almeria",
        "las palmas": "las palmas",
        "castellon": "castellon",
        "cordoba": "cordoba",
        "malaga": "malaga",
        "cadiz": "cadiz",
        "leganes": "leganes",
        "zaragoza": "zaragoza",
        "valladolid": "valladolid",
        "huesca": "huesca",
        "eibar": "eibar",
        "mirandes": "mirandes",
        "burgos": "burgos",
        "granada": "granada",
        "ceuta": "ceuta",
        "andorra": "andorra",
        "cultural leonesa": "cultural leonesa",
        "real sociedad b": "real sociedad b",
        "albacete": "albacete"
    }

    for a, b in reemplazos.items():
        txt = txt.replace(a, b)

    return clean(txt)
    txt = clean(txt).lower()
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii")
    for basura in [" cf", " cd", " sd", " ud", " fc", " real ", " club"]:
        txt = txt.replace(basura, " ")
    return clean(txt)

def equipo_nombre(equipo):
    if isinstance(equipo, dict):
        return equipo.get("name", "")
    return str(equipo or "")

def cargar_openfootball(nombre, url):
    data = json.loads(descargar(url))
    jornadas = {}

    for match in data.get("matches", []):
        jornada_txt = str(match.get("round", ""))
        numeros = "".join(ch for ch in jornada_txt if ch.isdigit())
        if not numeros:
            continue

        jornada = int(numeros)

        score = match.get("score", {})
        ft = score.get("ft", []) if isinstance(score, dict) else []

        resultado = ""
        estado = "Programado"

        if isinstance(ft, list) and len(ft) == 2:
            resultado = f"{ft[0]}-{ft[1]}"
            estado = "Jugado"

        partido = {
            "fecha": match.get("date", ""),
            "hora": match.get("time", ""),
            "local": equipo_nombre(match.get("team1")),
            "visitante": equipo_nombre(match.get("team2")),
            "estado": estado,
            "resultado": resultado
        }

        if partido["local"] and partido["visitante"]:
            jornadas.setdefault(jornada, []).append(partido)

    return jornadas

def actualizar_resultados_segunda_laliga(jornadas):
    equipos = set()

    for partidos in jornadas.values():
        for p in partidos:
            equipos.add(p["local"])
            equipos.add(p["visitante"])

    equipos_re = "|".join(sorted(map(re.escape, equipos), key=len, reverse=True))

    for jornada in sorted(jornadas):
        url = LALIGA_SEGUNDA_RESULTADOS.format(jornada)

        try:
            html = descargar(url)
        except Exception as e:
            print(f"WARNING jornada {jornada}: no se pudo leer LALIGA ({e})")
            continue

        soup = BeautifulSoup(html, "html.parser")
        texto = clean(soup.get_text(" "))

        patron = re.compile(
            rf"({equipos_re})\s+(\d+\s*-\s*\d+)\s+({equipos_re})",
            re.I
        )

        encontrados = 0

        for m in patron.finditer(texto):
            local_web, resultado, visitante_web = m.groups()
            nl = normalizar(local_web)
            nv = normalizar(visitante_web)

            for p in jornadas[jornada]:
                if normalizar(p["local"]) == nl and normalizar(p["visitante"]) == nv:
                    p["resultado"] = clean(resultado).replace(" ", "")
                    p["estado"] = "Jugado"
                    encontrados += 1

        print(f"Segunda jornada {jornada}: {encontrados} resultados oficiales añadidos")

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

primera = cargar_openfootball("primera", FUENTES["primera"])
segunda = cargar_openfootball("segunda", FUENTES["segunda"])

actualizar_resultados_segunda_laliga(segunda)

escribir("primera", FUENTES["primera"], primera)
escribir("segunda", FUENTES["segunda"], segunda)

print("Calendarios generados correctamente")
