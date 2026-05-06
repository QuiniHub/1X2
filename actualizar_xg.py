#!/usr/bin/env python3
import os, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

api_key = os.getenv("THE_ODDS_API_KEY")
if not api_key:
    DATA.joinpath("cuotas_tiempo_real.json").write_text(json.dumps({"status":"missing_THE_ODDS_API_KEY"}, indent=2), encoding="utf-8")
    print("Sin THE_ODDS_API_KEY. Añade la clave en GitHub Secrets.")
else:
    DATA.joinpath("cuotas_tiempo_real.json").write_text(json.dumps({"status":"api_key_detected", "nota":"Implementar llamada según proveedor."}, indent=2), encoding="utf-8")
    print("API key de cuotas detectada.")
