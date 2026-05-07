import csv
import re
from pathlib import Path
from urllib.request import Request, urlopen

URL = "https://www.quinielafutbol.info/historico/resultados-la-quiniela-2025-2026.html"

req = Request(URL, headers={"User-Agent": "Mozilla/5.0"})
html = urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")

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

filas = []

for match in patron.finditer(texto):
    semana, anio, jornada, dia, sorteo, combinacion = match.groups()
    jornada = int(jornada)

    if jornada > 60:
        continue

    partes = [p.strip() for p in combinacion.split(",") if p.strip()]
    signos = [p for p in partes if p in ["1", "X", "2"]]

    if len(signos) < 14:
        continue

    resultado_14 = "".join(signos[:14])
    pleno15 = partes[-1] if partes else ""

    resultado = resultado_14 + " | P15 " + pleno15

    filas.append([
        jornada,
        f"Semana {semana} - {anio}",
        resultado,
        "No jugada por nosotros",
        "Pendiente",
        "Pendiente",
        "Pendiente",
        "Cargada automáticamente desde QuinielaFutbol"
    ])

filas = sorted({fila[0]: fila for fila in filas}.values(), key=lambda x: x[0])

salida = Path("historico_quinielas.csv")

with salida.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "jornada",
        "fecha",
        "resultado_oficial",
        "nuestra_quiniela",
        "aciertos",
        "fallos_claros",
        "fallos_sorpresa",
        "lectura"
    ])

    writer.writerows(filas)

    writer.writerow([
        61,
        "10/05/2026",
        "Pendiente",
        "1X2 X 1 1X2 1X 1 X 1X2 2 X2 1 X 2 1",
        "Pendiente",
        "Pendiente",
        "Pendiente",
        "Se actualizará al terminar la jornada"
    ])

print("Jornadas reales cargadas:", len(filas))
