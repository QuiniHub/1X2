#!/usr/bin/env python3
from pathlib import Path
import subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

steps = [
    "actualizar_resultados.py",
    "actualizar_historico_boletos.py",
    "actualizar_porcentajes_apostados.py",
    "actualizar_eduardo_losilla.py",
    "actualizar_cuotas.py",
    "actualizar_plantillas.py",
    "actualizar_xg.py",
    "actualizar_arbitros.py",
    "actualizar_clima.py",
    "analizar_historico_quinielas.py",
    "comparar_boletos.py",
    "entrenar_modelo.py",
    "generar_pronostico.py",
]

for step in steps:
    print(f"\n=== {step} ===")
    subprocess.run([sys.executable, str(SCRIPTS / step)], check=False)

print("\nActualización completa.")
