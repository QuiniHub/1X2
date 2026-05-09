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

def normalizar(txt):
    txt = clean(txt).lower()
    txt = txt.replace("cf", "")
    txt = txt.replace("fc", "")
    txt = txt.replace("ud", "")
    txt = txt.replace("cd", "")
    txt = txt.replace("sd", "")
    txt = txt.replace("rcd", "")
    txt = txt.replace("real ", "")
    txt = txt.replace("deportivo ", "")
    return clean(txt)

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
            "resultado": clean(resultado or "").replace(" ", "")
        }

        jornadas.setdefault(jornada, []).append(partido)

    escribir("primera", FUENTES["primera"], jornadas)

def extraer_segunda():
    texto = descargar(FUENTES["segunda"])
    data = json.loads(texto)

    jornadas = {}

    for match in data.get("matches", []):
        jornada_txt = str(match.get("round", ""))
        numeros = re.findall(r"\d+", jornada_txt)

        if not numeros:
            continue

        jornada = int(numeros[0])

        score = match.get("score", {})
        ft = score.get("ft", []) if isinstance(score, dict) else []

        estado = "Programado"
        resultado = ""

        if isinstance(ft, list) and len(ft) == 2:
            estado = "Jugado"
            resultado = f"{ft[0]}-{ft[1]}"

        partido = {
            "fecha": match.get("date", ""),
            "hora": match.get("time", ""),
            "local": clean(match.get("team1", "")),
            "visitante": clean(match.get("team2", "")),
            "estado": estado,
            "resultado": resultado
        }

        if partido["local"] and partido["visitante"]:
            jornadas.setdefault(jornada, []).append(partido)

    escribir("segunda", FUENTES["segunda"], jornadas)

def actualizar_resultados_segunda_laliga(jornadas):
    for jornada in jornadas:
        url = f"https://www.laliga.com/laliga-hypermotion/resultados/{jornada}"

        try:
            html = descargar(url)
        except:
            continue

        soup = BeautifulSoup(html, "html.parser")
        texto = clean(soup.get_text(" "))

        equipos = set()

        for p in jornadas[jornada]:
            equipos.add(p["local"])
            equipos.add(p["visitante"])

        equipos_re = "|".join(
            sorted(map(re.escape, equipos), key=len, reverse=True)
        )

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
                pl = normalizar(p["local"])
                pv = normalizar(p["visitante"])

                if (pl in nl or nl in pl) and (pv in nv or nv in pv):
                    p["resultado"] = clean(resultado).replace(" ", "")
                    p["estado"] = "Jugado"
                    encontrados += 1

        print(f"Segunda jornada {jornada}: {encontrados} resultados oficiales añadidos")

extraer_primera()
extraer_segunda()

print("Calendarios generados correctamente")
