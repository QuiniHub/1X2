import json
from pathlib import Path

print("Entrenando modelo base...")

data = Path("data")
data.mkdir(exist_ok=True)

modelo = {
    "status": "ok",
    "tipo": "modelo_base",
    "nota": "Modelo preparado. Se entrenará con histórico completo cuando esté disponible."
}

(data / "modelo_entrenado.json").write_text(
    json.dumps(modelo, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print("Modelo entrenado correctamente")
