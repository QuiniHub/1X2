#!/usr/bin/env python3
from pathlib import Path
import csv, json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

src = DATA / "historico_quinielas.csv"
rows = list(csv.DictReader(src.open(encoding="utf-8")))

summary = {
    "jornadas_cargadas": len(rows),
    "analisis": [],
    "nota": "Cuando el histórico esté completo, calculará frecuencias, dificultad, patrones de premios y sorpresas."
}

for r in rows:
    signs = [r.get(f"signo_{i}", "") for i in range(1, 15)]
    filled = [s for s in signs if s in ("1", "X", "2")]
    summary["analisis"].append({
        "temporada": r.get("temporada"),
        "jornada": r.get("jornada"),
        "num_1": filled.count("1"),
        "num_x": filled.count("X"),
        "num_2": filled.count("2"),
        "completada": len(filled) == 14
    })

(DATA / "analisis_historico_quinielas.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print("Análisis histórico generado.")
