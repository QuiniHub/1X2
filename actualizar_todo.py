import os

scripts = [
    "actualizar_historico_real.py",
    "actualizar_clasificaciones.py"
    "actualizar_jornadas_detalle.py"
]

for script in scripts:
    print(f"Ejecutando {script}...")
    os.system(f"python {script}")
