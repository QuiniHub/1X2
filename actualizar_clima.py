#!/usr/bin/env python3
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

with open(DATA / "xg_template.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["equipo","xg_for_5","xg_against_5","xg_diff_5","fuente"])

print("xG template creado.")
