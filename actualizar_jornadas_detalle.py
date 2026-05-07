import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

BASE = "https://www.quinielafutbol.info/resultados/jornada-quiniela-"

JORNADAS = range(1, 61)

def descargar(url):
    req = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    return urlopen(req, timeout=30).read().decode(
        "utf-8",
        errors="ignore"
    )

Path("data/jornadas").mkdir(
    parents=True,
    exist_ok=True
)

for jornada in JORNADAS:

    print(f"Procesando jornada {jornada}...")

    # URL dinámica aproximada
    url = f"{BASE}{jornada}.html"

    try:

        html = descargar(url)

        partidos = re.findall(
            r'(\d+)\s*</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>([12X])</td>',
            html,
            flags=re.I | re.S
        )

        datos = {
            "jornada": jornada,
            "partidos": []
        }

        for numero, local, visitante, signo in partidos:

            local = re.sub(r"<.*?>", "", local).strip()
            visitante = re.sub(r"<.*?>", "", visitante).strip()

            datos["partidos"].append({
                "num": int(numero),
                "local": local,
                "visitante": visitante,
                "signo_oficial": signo,
                "signo_nuestro": "No jugada"
            })

        salida = Path(
            f"data/jornadas/jornada_{jornada}.json"
        )

        salida.write_text(
            json.dumps(
                datos,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        print(f"OK jornada {jornada}")

    except Exception as e:

        print(
            f"Error jornada {jornada}:",
            e
        )

print("Detalles de jornadas generados.")
