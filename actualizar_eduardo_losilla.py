#!/usr/bin/env python3
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

status = {
    "modulo": "historico_boletos_quiniela",
    "estado": "pendiente_conector_fuente_oficial",
    "archivo_objetivo": "data/historico_quinielas.csv",
    "campos": ["temporada", "jornada", "signos", "pleno_15", "recaudacion", "bote", "premios"],
    "nota": "Conectar SELAE o dataset autorizado."
}
(DATA / "historico_boletos_estado.json").write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
print("Histórico de boletos: conector preparado.")
