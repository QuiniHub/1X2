import csv
import re
from pathlib import Path
from urllib.request import Request, urlopen

URL = "https://www.quinielafutbol.info/historico/resultados-la-quiniela-2025-2026.html"

def descargar(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")

html = descargar(URL)

# Quitar saltos raros
texto = re.sub(r"\s+", " ", html)

# Extrae bloques por jornada
bloques = re.findall(
    r"Jornada\s+(\d+).*?Resultado.*?([1X2]{14})",
    html,
    flags=re.I | re.S
)

filas = []

for jornada, bloque in bloques:
    jornada = int(jornada)

    if jornada > 60:
        continue

    fecha_match = re.search(
        r"(Domingo|Lunes|Martes|Miércoles|Miercoles|Jueves|Viernes|Sábado|Sabado),?\s+(\d{1,2}\s+de\s+\w+\s+de\s+2026|\d{1,2}\s+de\s+\w+\s+de\s+2025)",
        bloque,
        flags=re.I
    )
    fecha = fecha_match.group(0) if fecha_match else "Fecha pendiente"

    signos = re.findall(r">\s*([1X2])\s*<", bloque)

    if len(signos) < 14:
        signos = re.findall(r"\b([1X2])\b", bloque)

    resultado = "".join(signos[:14])

    if len(resultado) == 14:
        filas.append([
            jornada,
            fecha,
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

print(f"Jornadas cargadas: {len(filas)}")
print("Archivo generado:", salida)
