import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent

SCRIPTS_ACTIVOS = [
    "actualizar_jornadas_detalle.py",
    "actualizar_selector_jornadas_web.py",
    "actualizar_resultados_directo.py",
    "aplicar_correcciones_resultados.py",
    "actualizar_clasificaciones_oficiales.py",
    "corregir_clasificacion_segunda.py",
    "recalcular_dinamicas_calendario.py",
    "actualizar_contexto_equipos.py",
    "actualizar_analisis_ia.py",
    "construir_historial_quinielas.py",
    "actualizar_aprendizaje_ia.py",
    "construir_memoria_ia.py",
    "recalcular_dinamicas_calendario.py",
    "sincronizar_dinamicas_memoria.py",
    "generar_contexto_competitivo.py",
    "aprender_patrones_competitivos.py",
    "aplicar_patrones_motor.py",
    "reforzar_patrones_motor.py",
    "corregir_emparejamiento_motor.py",
    "mejorar_motor_dinamica_10.py",
    "motor_prediccion_quiniela.py",
    "generar_estado_vivo_ia.py",
    "regenerar_estado_vivo_actual.py",
    "ajustar_estado_vivo_motivacion.py",
    "mejorar_asistente_ia.py",
    "corregir_asistente_objeciones.py",
    "corregir_puntos_asistente.py",
    "mejorar_asistente_estrategia_apuesta.py",
    "corregir_comparacion_estrategia.py",
    "corregir_recomendacion_estrategia.py",
    "ajustar_estrategia_motivacion.py",
    "mejorar_lectura_competitiva_global.py",
    "mejorar_coberturas_necesidad.py",
    "corregir_ajuste_necesidad_boleto.py",
    "reforzar_coberturas_descenso.py",
    "aplicar_patrones_web.py",
    "corregir_emparejamiento_equipos.py",
    "diagnostico_sistema.py",
    "control_calidad_actualizacion.py",
    "normalizar_diagnostico_control.py",
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