#!/usr/bin/env python3
from pathlib import Path
import csv, json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

boletos = list(csv.DictReader((DATA / "boletos_generados.csv").open(encoding="utf-8")))
historico = list(csv.DictReader((DATA / "historico_quinielas.csv").open(encoding="utf-8")))

results = []
for b in boletos:
    match = next((h for h in historico if h["temporada"] == b["temporada"] and h["jornada"] == b["jornada"]), None)
    results.append({
        "id_boleto": b["id_boleto"],
        "temporada": b["temporada"],
        "jornada": b["jornada"],
        "estado": "pendiente_resultado" if not match or not match.get("signo_1") else "comparado",
        "aciertos": None
    })

(DATA / "comparacion_boletos.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print("Comparación de boletos generada.")
