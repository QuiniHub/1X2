import json
import re
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


FUENTES = {
    "primera": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/es.1.json",
    "segunda": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/es.2.json",
}

FUENTES_SEGUNDA_RESULTADOS = [
    "https://www.mundodeportivo.com/resultados/futbol/liga-segunda-division/2025-2026/jornada-{}",
    "https://www.mundodeportivo.com/resultados/futbol/liga-segunda-division/jornada-{}",
    "https://as.com/resultados/futbol/segunda/2025_2026/jornada/regular_a_{}/",
    "https://www.laliga.com/laliga-hypermotion/resultados/2025-26/jornada-{}",
]

Path("data").mkdir(exist_ok=True)


def descargar(url):
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    )
    return urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")


def clean(x):
    return re.sub(r"\s+", " ", str(x or "")).strip()


def sin_acentos(x):
    return unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode("ascii")


def normalizar(txt):
    txt = sin_acentos(clean(txt).lower())

    equivalencias = {
        "deportivo la coruna": "deportivo",
        "deportivo de la coruna": "deportivo",
        "deportivo coruna": "deportivo",
        "racing santander": "racing",
        "racing de santander": "racing",
        "sporting gijon": "sporting",
        "sporting de gijon": "sporting",
        "real sporting": "sporting",
        "real sociedad b": "sociedad b",
        "real sociedad ii": "sociedad b",
        "real sociedad de futbol b": "sociedad b",
        "real zaragoza": "zaragoza",
        "real valladolid": "valladolid",
        "fc andorra": "andorra",
        "andorra fc": "andorra",
        "ad ceuta fc": "ceuta",
        "ad ceuta": "ceuta",
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
        "cultural leonesa": "cultural",
        "albacete balompie": "albacete",
    }

    for a, b in equivalencias.items():
        txt = txt.replace(a, b)

    quitar = [
        "club de futbol",
        "club deportivo",
        "union deportiva",
        " real ",
        " cf ",
        " fc ",
        " ud ",
        " cd ",
        " sd ",
        " rcd ",
    ]

    txt = f" {txt} "
    for q in quitar:
        txt = txt.replace(q, " ")

    txt = re.sub(r"[^a-z0-9 ]+", " ", txt)
    return clean(txt)


def equipo_nombre(equipo):
    if isinstance(equipo, dict):
        return clean(equipo.get("name", ""))
    return clean(equipo)


def cargar_openfootball(nombre, url):
    data = json.loads(descargar(url))
    jornadas = {}

    for match in data.get("matches", []):
        jornada_txt = str(match.get("round", ""))
        nums = re.findall(r"\d+", jornada_txt)

        if not nums:
            continue

        jornada = int(nums[0])
        score = match.get("score", {})
        ft = score.get("ft", []) if isinstance(score, dict) else []

        estado = "Programado"
        resultado = ""

        if isinstance(ft, list) and len(ft) == 2:
            estado = "Jugado"
            resultado = f"{ft[0]}-{ft[1]}"

        partido = {
            "fecha": clean(match.get("date", "")),
            "hora": clean(match.get("time", "")),
            "local": equipo_nombre(match.get("team1")),
            "visitante": equipo_nombre(match.get("team2")),
            "estado": estado,
            "resultado": resultado,
        }

        if partido["local"] and partido["visitante"]:
            jornadas.setdefault(jornada, []).append(partido)

    if not jornadas:
        raise SystemExit(f"ERROR: calendario {nombre} vacío")

    return jornadas


def aplicar_resultado(jornadas, jornada, local_web, visitante_web, resultado):
    nl = normalizar(local_web)
    nv = normalizar(visitante_web)
    resultado = clean(resultado).replace(" ", "")

    for p in jornadas.get(jornada, []):
        if p.get("resultado"):
            continue

        pl = normalizar(p["local"])
        pv = normalizar(p["visitante"])

        mismo = (pl in nl or nl in pl) and (pv in nv or nv in pv)
        inverso = (pl in nv or nv in pl) and (pv in nl or nl in pv)

        if mismo:
            p["resultado"] = resultado
            p["estado"] = "Jugado"
            return True

        if inverso:
            goles = resultado.split("-")
            p["resultado"] = f"{goles[1]}-{goles[0]}" if len(goles) == 2 else resultado
            p["estado"] = "Jugado"
            return True

    return False


def reforzar_segunda(jornadas):
    equipos = set()

    for partidos in jornadas.values():
        for p in partidos:
            equipos.add(p["local"])
            equipos.add(p["visitante"])

    equipos_re = "|".join(sorted(map(re.escape, equipos), key=len, reverse=True))

    patrones = [
        re.compile(rf"({equipos_re})\s+(\d+)\s*-\s*(\d+)\s+({equipos_re})", re.I),
        re.compile(rf"({equipos_re})\s+(\d+\s*-\s*\d+)\s+({equipos_re})", re.I),
    ]

    for jornada in sorted(jornadas):
        anadidos = 0

        for plantilla in FUENTES_SEGUNDA_RESULTADOS:
            url = plantilla.format(jornada)

            try:
                html = descargar(url)
            except Exception as e:
                print(f"WARNING Segunda J{jornada}: no leída {url}: {e}")
                continue

            soup = BeautifulSoup(html, "html.parser")
            texto = clean(soup.get_text(" "))

            for patron in patrones:
                for m in patron.finditer(texto):
                    grupos = m.groups()

                    if len(grupos) == 4:
                        local, g1, g2, visitante = grupos
                        resultado = f"{g1}-{g2}"
                    else:
                        local, resultado, visitante = grupos

                    if aplicar_resultado(jornadas, jornada, local, visitante, resultado):
                        anadidos += 1

        pendientes = [p for p in jornadas[jornada] if not p.get("resultado")]
        print(f"Segunda J{jornada}: añadidos {anadidos}, pendientes {len(pendientes)}")


def escribir(nombre, fuente, jornadas):
    salida = {
        "competicion": nombre,
        "fuente": fuente,
        "jornadas": [
            {
                "jornada": j,
                "partidos": jornadas[j],
            }
            for j in sorted(jornadas)
        ],
    }

    Path(f"data/calendario_{nombre}.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Calendario {nombre}: {len(jornadas)} jornadas generadas")


primera = cargar_openfootball("primera", FUENTES["primera"])
segunda = cargar_openfootball("segunda", FUENTES["segunda"])

reforzar_segunda(segunda)
actualizar_resultados_segunda_laliga(segunda)

escribir("primera", FUENTES["primera"], primera)
escribir("segunda", FUENTES["segunda"], segunda)

print("Calendarios generados correctamente")
