import os

scripts = [
    "actualizar_historico_real.py"
]

for script in scripts:
    print(f"Ejecutando {script}...")
    os.system(f"python {script}")

print("Actualización Quiniela IA Pro completada")
