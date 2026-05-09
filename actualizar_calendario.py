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
    txt = txt.replace("sporting gijón", "sporting")
    txt = txt.replace("real sociedad b", "real sociedad")
    txt = txt.replace("deportivo la coruña", "deportivo")
    txt = txt.replace("real zaragoza", "zaragoza")
    txt = txt.replace("cádiz cf", "cadiz")
    txt = txt.replace("málaga cf", "malaga")
        equivalencias = {
        "deportivo la coruna": "deportivo",
        "deportivo coruna": "deportivo",
        "deportivo de la coruna": "deportivo",
        "deportivo la Coruña": "deportivo",
        "racing santander": "racing",
        "racing de santander": "racing",
        "sporting gijon": "sporting",
        "sporting de gijon": "sporting",
        "real sporting": "sporting",
        "real sociedad b": "sociedad b",
        "real sociedad ii": "sociedad b",
        "real sociedad de futbol b": "sociedad b",
        "fc andorra": "andorra",
        "ad ceuta": "ceuta",
        "ad ceuta fc": "ceuta",
        "ud almeria": "almeria",
        "ud las palmas": "las palmas",
        "cd castellon": "castellon",
        "cordoba cf": "cordoba",
        "malaga cf": "malaga",
        "cadiz cf": "cadiz",
        "granada cf": "granada",
        "burgos cf": "burgos",
        "sd huesca": "huesca",
        "sd eibar": "eibar",
        "cd mirandes": "mirandes",
        "real zaragoza": "zaragoza",
        "real valladolid": "valladolid",
        "cultural leonesa": "cultural",
        "albacete balompie": "albacete"
    }

    for a, b in equivalencias.items():
        txt = txt.replace(a, b)
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
    fuentes = [
        "https://www.mundodeportivo.com/resultados/futbol/liga-segunda-division/2025-2026/jornada-{}",
        "https://as.com/resultados/futbol/segunda/2025_2026/jornada/regular_a_{}/",
        "https://elpais.com/deportes/resultados/futbol/segunda/2025_2026/jornada/regular-a-{}/"
    ]

    def marcar_resultado(jornada, local_web, visitante_web, resultado):
        nl = normalizar(local_web)
        nv = normalizar(visitante_web)

        for p in jornadas.get(jornada, []):
            pl = normalizar(p["local"])
            pv = normalizar(p["visitante"])

            mismo_orden = (pl in nl or nl in pl) and (pv in nv or nv in pv)
            orden_inverso = (pl in nv or nv in pl) and (pv in nl or nl in pv)

            if mismo_orden:
                p["resultado"] = clean(resultado).replace(" ", "")
                p["estado"] = "Jugado"
                return True

            if orden_inverso:
                goles = clean(resultado).replace(" ", "").split("-")
                if len(goles) == 2:
                    p["resultado"] = f"{goles[1]}-{goles[0]}"
                else:
                    p["resultado"] = clean(resultado).replace(" ", "")
                p["estado"] = "Jugado"
                return True

        return False

    equipos = set()
    for partidos in jornadas.values():
        for p in partidos:
            equipos.add(p["local"])
            equipos.add(p["visitante"])

    equipos_re = "|".join(sorted(map(re.escape, equipos), key=len, reverse=True))

    patrones = [
        re.compile(
            rf"({equipos_re})\s+(\d+\s*-\s*\d+)\s+({equipos_re})",
            re.I
        ),
        re.compile(
            rf"({equipos_re})\s+(\d+)\s*-\s*(\d+)\s+({equipos_re})",
            re.I
        )
    ]

    for jornada in sorted(jornadas):
        añadidos_total = 0

        for plantilla in fuentes:
            url = plantilla.format(jornada)

            try:
                html = descargar(url)
            except Exception as e:
                print(f"WARNING Segunda J{jornada}: no se pudo leer {url} ({e})")
                continue

            soup = BeautifulSoup(html, "html.parser")
            texto = clean(soup.get_text(" "))

            añadidos = 0

            for patron in patrones:
                for m in patron.finditer(texto):
                    if len(m.groups()) == 3:
                        local_web, resultado, visitante_web = m.groups()
                    else:
                        local_web, g1, g2, visitante_web = m.groups()
                        resultado = f"{g1}-{g2}"

                    if marcar_resultado(jornada, local_web, visitante_web, resultado):
                        añadidos += 1
                        añadidos_total += 1

            if añadidos > 0:
                print(f"Segunda J{jornada}: {añadidos} resultados añadidos desde {url}")

        pendientes = [
            f'{p["local"]}-{p["visitante"]}'
            for p in jornadas[jornada]
            if not p.get("resultado")
        ]

        if pendientes:
            print(f"Segunda J{jornada}: pendientes {len(pendientes)} -> {pendientes}")
extraer_primera()
extraer_segunda()

print("Calendarios generados correctamente")
