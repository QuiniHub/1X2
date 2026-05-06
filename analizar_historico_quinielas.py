#!/usr/bin/env python3
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

with open(DATA / "arbitros_template.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["partido","arbitro","tarjetas_media","penaltis_media","rojas_media","fuente"])

print("Árbitros template creado.")
