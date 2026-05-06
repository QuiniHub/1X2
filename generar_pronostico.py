import json
from pathlib import Path

print("Generando pronóstico...")

data = Path("data")
data.mkdir(exist_ok=True)

pronostico = {
    "jornada": 61,
    "estado": "ok",
    "quiniela": "1X2,X,1,1X2,1X,1,X,1X2,2,X2,1,X,2,1",
    "pleno_15": "M-1"
}

(data / "pronostico_actual.json").write_text(
    json.dumps(pronostico, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print("Pronóstico generado correctamente")
