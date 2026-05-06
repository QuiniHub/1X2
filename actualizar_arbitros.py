#!/usr/bin/env python3
import os, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

status = {
    "lesiones": "pendiente_api",
    "sanciones": "pendiente_api",
    "alineaciones_probables": "pendiente_api",
    "api_football": bool(os.getenv("API_FOOTBALL_KEY")),
    "sportmonks": bool(os.getenv("SPORTMONKS_KEY"))
}
(DATA / "plantillas_estado.json").write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
print("Plantillas/lesiones/sanciones preparadas.")
