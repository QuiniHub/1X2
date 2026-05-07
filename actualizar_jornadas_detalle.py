import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

URL_HISTORICO = "https://www.quinielafutbol.info/historico/resultados-la-quiniela-2025-2026.html"

def descargar(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")

Path("data/jornadas").mkdir(parents=True, exist_ok=True)

html = descargar(URL_HISTORICO)
texto = re.sub(r"<[^>]+>", " ", html)
texto = re.sub(r"\s+", " ", texto)

patron = re.compile(
    r"(\d{1,2})\s*-\s*(2025|2026)\s+"
    r"(\d{1,2})\s+"
    r"(Q-[A-ZÁÉÍÓÚÑ]+)\s+"
    r"(\d{4}/\d{3})\s+"
    r"([12XM0,]+)",
    re.I
)

creados = 0

for match in patron.finditer(texto):
    semana, anio, jornada, dia, sorteo, combinacion = match.groups()
    jornada = int(jornada)

    if jornada < 1 or jornada > 60:
        continue

    partes = combinacion.split(",")
    signos14 = partes[:14]
    pleno15 = partes[14] if len(partes) > 14 else ""

    datos = {
        "jornada": jornada,
        "fecha": f"Semana {semana} - {anio}",
        "fuente": "QuinielaFutbol",
        "sorteo": sorteo,
        "tipo": dia,
        "partidos": [],
        "pleno15": {
            "signo_oficial": pleno15,
            "signo_nuestro": "No jugada"
        }
    }

    for i, signo in enumerate(signos14, start=1):
        datos["partidos"].append({
            "num": i,
            "local": f"Partido {i}",
            "visitante": "",
            "signo_oficial": signo,
            "signo_nuestro": "No jugada"
        })

    Path(f"data/jornadas/jornada_{jornada}.json").write_text(
        json.dumps(datos, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    creados += 1

if creados < 50:
    raise SystemExit(f"ERROR: solo se generaron {creados} jornadas")

print(f"Jornadas detalle generadas: {creados}")
