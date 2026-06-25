import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent

# Scripts que existen en el repo pero cuya ejecucion esta temporalmente
# bloqueada para evitar cambios visuales no controlados.
SCRIPTS_VISUALES_DESACTIVADOS = {
    "actualizar_selector_jornadas_web.py",
    "aplicar_coherencia_pro_boleto.py",
    "aplicar_patrones_web.py",
    "ajustar_coberturas_contexto_global.py",
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
    "corregir_elige8_web.py",
    "estabilizar_web.py",
}

SCRIPTS_ACTIVOS = [
    # --- Datos base ---
    "actualizar_jornadas_detalle.py",
    "actualizar_boleto_vivo.py",
    "asegurar_proxima_jornada.py",
    "actualizar_selector_jornadas_web.py",
    "actualizar_resultados_directo.py",
    "aplicar_correcciones_resultados.py",
    "actualizar_monitor_temporadas.py",
    "actualizar_clasificaciones_oficiales.py",
    "corregir_clasificacion_segunda.py",
    "actualizar_ligas_football_data.py",
    "recalcular_dinamicas_calendario.py",
    "actualizar_contexto_equipos.py",
    "actualizar_analisis_ia.py",
    "construir_historial_quinielas.py",
    "actualizar_aprendizaje_ia.py",
    "generar_diario_aprendizaje.py",
    "construir_memoria_ia.py",
    "aprender_de_historial_resultados.py",
    "memoria_autonoma_quiniela.py",
    "sincronizar_dinamicas_memoria.py",

    # --- Fuente unica de verdad competitiva ---
    "generar_contexto_competitivo.py",
    "aplicar_objetivos_oficiales_json.py",
    "forzar_overrides.py",
    "validar_contexto_actual.py",
    "construir_fuente_verdad_competitiva.py",

    # --- Competiciones internacionales y datos profesionales ---
    "actualizar_mundial_2026.py",
    "actualizar_clasificaciones_mundial_2026.py",
    "generar_memoria_mundial_2026.py",
    "actualizar_datos_profesionales.py",
    "auditar_fuentes_profesionales.py",
    "resolver_competiciones_profesionales.py",

    # --- Capa predictiva entrenable ---
    "modelo_metricas_1x2.py",

    # --- Comp puerta de resultados antes de predecir ---
    "sincronizar_resultados_jornada.py",
    "compuerta_jornada.py",

    # --- Motor predictivo y salidas ---
    "aprender_patrones_competitivos.py",
    "aplicar_patrones_motor.py",
    "reforzar_patrones_motor.py",
    "corregir_emparejamiento_motor.py",
    "mejorar_motor_dinamica_10.py",
    "alinear_pronostico_analisis.py",
    "mejorar_prioridad_coberturas.py",
    "motor_prediccion_objetivo.py",
    "aplicar_memoria_mundial_prediccion.py",
    "alinear_boleto_con_analisis.py",
    "generar_estado_vivo_ia.py",
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
    "ajustar_coberturas_contexto_global.py",
    "verificar_coherencia_pronostico.py",

    # --- Premios ---
    "calcular_premios.py",

    # --- Control de calidad ---
    "guardar_snapshot_prediccion.py",
    "backtesting_pre_cierre.py",
    "calibrar_probabilidades.py",
    "diagnostico_sistema.py",
    "control_calidad_actualizacion.py",
    "normalizar_diagnostico_control.py",
    "normalizar_textos_generados.py",

    # --- Cierre final: web y publicacion ---
    "aplicar_elige8_seguro.py",
    "limpiar_prediccion_bloqueada.py",
    "estabilizar_web.py",
    "seleccionar_pleno15.py",
    "validar_publicacion_autonoma.py",
]


def gestionar_mercado_y_temporada():
    mes = datetime.now().month
    year = datetime.now().year
    if mes in {7, 8}:
        print(f"Pretemporada detectada: preparar temporada {year}/{year + 1}.")
        ejecutar_script("preparar_temporada_2026_2027.py")
    elif mes >= 9:
        print(f"Temporada {year}/{year + 1} en marcha o mercado cerrado: flujo normal.")


def ejecutar_script(nombre):
    ruta = ROOT / nombre
    if not ruta.exists():
        raise SystemExit(f"Falta script activo: {nombre}")
    print(f"\n=== Ejecutando {nombre} ===")
    subprocess.run([sys.executable, str(ruta)], cwd=ROOT, check=True)


def ejecutar_sistema():
    gestionar_mercado_y_temporada()
    for script in SCRIPTS_ACTIVOS:
        if script in SCRIPTS_VISUALES_DESACTIVADOS:
            print(f"\n=== Omitiendo {script}: bloqueo de cambios visuales activo ===")
            continue
        ejecutar_script(script)
    print("\nActualizacion completa sin errores ocultos.")


if __name__ == "__main__":
    ejecutar_sistema()
