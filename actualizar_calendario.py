import csv
import json
from pathlib import Path
from urllib.request import Request, urlopen
from io import StringIO
    FUENTES = {
    "primera": "https://fixturedownload.com/download/laliga-2025-UTC.csv",
    "segunda": "https://fixturedownload.com/download/laliga2-2025-UTC.csv"
}
}

OUT = Path("data")
OUT.mkdir(exist_ok=True)

def descargar_csv(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")

def valor(row, nombres):
    for n in nombres:
        if n in row and row[n]:
            return row[n].strip()
    return ""

def generar(nombre, url):
    texto = descargar_csv(url)
    reader = csv.DictReader(StringIO(texto))

    jornadas = {}

    for row in reader:
        jornada_txt = valor(row, ["Round Number", "Round", "Matchday", "Jornada"])
        if not jornada_txt:
            continue

        jornada = int("".join(ch for ch in jornada_txt if ch.isdigit()))

        partido = {
            "fecha": valor(row, ["Date", "Fecha"]),
            "hora": valor(row, ["Time", "Hora"]),
            "local": valor(row, ["Home Team", "Home", "Local"]),
            "visitante": valor(row, ["Away Team", "Away", "Visitante"]),
            "resultado": valor(row, ["Result", "Score", "Resultado"]),
            "estado": valor(row, ["Status", "Estado"])
        }

        if not partido["local"] or not partido["visitante"]:
            continue

        jornadas.setdefault(jornada, []).append(partido)

    if len(jornadas) < 38:
        raise SystemExit(
            f"ERROR: calendario {nombre} incompleto. Jornadas encontradas: {len(jornadas)}"
        )

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
    generar(nombre, url)

print("Calendarios reales completos generados correctamente")
