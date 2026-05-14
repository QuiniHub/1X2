import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent

SCRIPTS_ACTIVOS = [
    "actualizar_jornadas_detalle.py",
    "actualizar_resultados_directo.py",
    "aplicar_correcciones_resultados.py",
    "actualizar_clasificaciones_oficiales.py",
    "actualizar_contexto_equipos.py",
    "actualizar_analisis_ia.py",
    "actualizar_aprendizaje_ia.py",
    "construir_historial_quinielas.py",
    "construir_memoria_ia.py",
    "generar_contexto_competitivo.py",
    "motor_prediccion_quiniela.py",
    "generar_estado_vivo_ia.py",
    "diagnostico_sistema.py",
]


def gestionar_mercado_y_temporada():
    mes = datetime.now().month
    year = datetime.now().year
    if mes >= 8:
        print(f"Pretemporada detectada: preparar temporada {year}/{year + 1}.")


def ejecutar_script(nombre):
    ruta = ROOT / nombre
    if not ruta.exists():
        raise SystemExit(f"Falta script activo: {nombre}")
    print(f"\n=== Ejecutando {nombre} ===")
    subprocess.run([sys.executable, str(ruta)], cwd=ROOT, check=True)


def ejecutar_sistema():
    gestionar_mercado_y_temporada()
    for script in SCRIPTS_ACTIVOS:
        ejecutar_script(script)
    print("\nActualizacion completa sin errores ocultos.")


if __name__ == "__main__":
    ejecutar_sistema()
