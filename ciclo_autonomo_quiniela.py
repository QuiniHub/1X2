import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent

SCRIPTS_CICLO_AUTONOMO = [
    "actualizar_resultados_directo.py",
    "aplicar_correcciones_resultados.py",
    "actualizar_aprendizaje_ia.py",
    "construir_memoria_ia.py",
    "memoria_autonoma_quiniela.py",
    "modelo_metricas_1x2.py",
    "aprender_patrones_competitivos.py",
    "calibrar_probabilidades.py",
    "motor_prediccion_quiniela.py",
    "aplicar_elige8_seguro.py",
    "limpiar_prediccion_bloqueada.py",
    "validar_publicacion_autonoma.py",
]


def ejecutar_script(nombre):
    ruta = ROOT / nombre
    if not ruta.exists():
        raise SystemExit(f"Falta script del ciclo autonomo: {nombre}")
    print(f"\n=== {datetime.now(timezone.utc).isoformat()} :: {nombre} ===")
    subprocess.run([sys.executable, str(ruta)], cwd=ROOT, check=True)


def ejecutar_ciclo():
    for script in SCRIPTS_CICLO_AUTONOMO:
        ejecutar_script(script)
    print("\nCiclo autonomo completado: resultados, aprendizaje, memoria, modelo y publicacion validados.")


if __name__ == "__main__":
    ejecutar_ciclo()
