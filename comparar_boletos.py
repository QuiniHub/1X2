#!/usr/bin/env python3
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

sample = [
    {"estadio":"Son Moix","lat":39.589,"lon":2.630,"status":"pendiente_fecha_partido"},
    {"estadio":"Sanchez-Pizjuan","lat":37.384,"lon":-5.970,"status":"pendiente_fecha_partido"}
]
(DATA / "clima_partidos.json").write_text(json.dumps(sample, indent=2, ensure_ascii=False), encoding="utf-8")
print("Clima preparado.")
