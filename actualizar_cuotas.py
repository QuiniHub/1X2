#!/usr/bin/env python3
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

with open(DATA / "porcentajes_apostados_template.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["temporada","jornada","partido","pct_1","pct_x","pct_2","fuente"])

print("Template porcentajes apostados creado.")
