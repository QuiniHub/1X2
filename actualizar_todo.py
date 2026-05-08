import os

scripts = [
    "actualizar_historico_real.py",
    "actualizar_clasificaciones.py",
    "actualizar_jornadas_detalle.py",
    "actualizar_calendario.py",
]

for script in scripts:
    print(f"Ejecutando {script}...")
    resultado = os.system(f"python {script}")
    if resultado != 0:
        raise SystemExit(f"Error ejecutando {script}")
