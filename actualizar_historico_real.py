import csv
import re
from pathlib import Path
from urllib.request import Request, urlopen

URL = "https://www.quinielafutbol.info/resultados/jornadas-de-la-quiniela.html"

print("Descargando histórico real de Quiniela...")

headers = {
    "User-Agent": "Mozilla/5.0"
}

req = Request(URL, headers=headers)
html = urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")

# Buscamos patrones de jornada y columnas 1X2 dentro de la página
patrones = re.findall(r"Jornada\s+(\d+).*?([12X]{14,15})", html, re.IGNORECASE | re.DOTALL)

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

    if not patrones:
        print("No se han encontrado jornadas automáticamente.")
        writer.writerow([
            61,
            "10/05/2026",
            "Pendiente",
            "1X2 X 1 1X2 1X 1 X 1X2 2 X2 1 X 2 1",
            "Pendiente",
            "Pendiente",
            "Pendiente",
            "Pendiente de cargar histórico real"
        ])
    else:
        vistos = set()
for jornada in range(1, 61):
    if jornada not in vistos:
        writer.writerow([
            jornada,
            "Fecha pendiente",
            "XXXXXXXXXXXXXX",
            "No jugada por nosotros",
            "Pendiente",
            "Pendiente",
            "Pendiente",
            "Cargada desde histórico real"
        ])
        for jornada, signos in patrones:
            if jornada in vistos:
                continue

            vistos.add(jornada)

            writer.writerow([
                jornada,
                "Fecha pendiente",
                signos,
                "No jugada por nosotros",
                "Pendiente",
                "Pendiente",
                "Pendiente",
                "Cargada desde QuinielaFutbol"
            ])

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

print("Histórico generado:", salida)
