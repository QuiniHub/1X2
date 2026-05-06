print("Actualización Quiniela IA Pro iniciada")

import subprocess
import sys

scripts = [
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

for script in scripts:
    print(f"Ejecutando {script}")
    subprocess.run([sys.executable, script], check=False)

print("Actualización terminada")
