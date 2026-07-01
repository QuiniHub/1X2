import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class ErrorCriticoPrediccion(Exception):
    """Fallo que debe detener el proceso por datos de prediccion."""


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
    "estabilizar_web.py",
}

SCRIPTS_CRITICOS_PREDICCION = {
    "motor_prediccion_objetivo.py",
    "validar_publicacion_autonoma.py",
}

# Estos scripts dependen de fuentes externas o son etapas auxiliares de datos.
# Si una fuente falla por red, DNS, timeout o servicio caido, se registra aviso
# y se conserva el ultimo dato local valido. Las etapas predictivas y de
# validacion final siguen siendo criticas y pueden detener la publicacion.
SCRIPTS_NO_CRITICOS_RED = {
    "preparar_temporada_2026_2027.py",
    "actualizar_fuente_lae.py",
    "alimentar_sorpresas_mercado.py",
    "actualizar_resultados_libres.py",
    "actualizar_jornadas_detalle.py",
    "actualizar_boleto_vivo.py",
    "asegurar_proxima_jornada.py",
    "actualizar_selector_jornadas_web.py",
    "buscar_resultados_google.py",
    "actualizar_resultados_directo.py",
    "aplicar_correcciones_resultados.py",
    "actualizar_monitor_temporadas.py",
    "actualizar_clasificaciones_oficiales.py",
    "corregir_clasificacion_segunda.py",
    "actualizar_ligas_football_data.py",
    "recalcular_dinamicas_calendario.py",
    "actualizar_fuente_losilla.py",
    "actualizar_contexto_equipos.py",
    "actualizar_analisis_ia.py",
    "construir_historial_quinielas.py",
    "actualizar_aprendizaje_ia.py",
    "generar_artefactos_compuerta_aprendizaje.py",
    "generar_diario_aprendizaje.py",
    "construir_memoria_ia.py",
    "alimentar_sorpresas_mercado.py",
    "construir_memoria_historica_profunda.py",
    "aprender_de_historial_resultados.py",
    "aplicar_objetivos_oficiales_json.py",
    "forzar_overrides.py",
    "actualizar_resultados_apis.py",
    "actualizar_datos_profesionales.py",
    "auditar_fuentes_profesionales.py",
    "resolver_competiciones_profesionales.py",
    "sincronizar_resultados_jornada.py",
    "aprender_patrones_competitivos.py",
    "generar_estado_vivo_ia.py",
    "ajustar_estado_vivo_motivacion.py",
    "calcular_premios.py",
    "guardar_snapshot_prediccion.py",
    "backtesting_pre_cierre.py",
    "calibrar_probabilidades.py",
    "diagnostico_sistema.py",
    "control_calidad_actualizacion.py",
    "normalizar_diagnostico_control.py",
    "normalizar_textos_generados.py",
}

SCRIPTS_ACTIVOS = [
    # --- Fuente oficial prioritaria ---
    "actualizar_fuente_lae.py",

    # --- Datos base ---
    "actualizar_jornadas_detalle.py",
    "actualizar_boleto_vivo.py",
    "asegurar_proxima_jornada.py",
    "actualizar_selector_jornadas_web.py",
    "buscar_resultados_google.py",
    "actualizar_resultados_directo.py",
    "aplicar_correcciones_resultados.py",
    "actualizar_monitor_temporadas.py",
    "actualizar_clasificaciones_oficiales.py",
    "corregir_clasificacion_segunda.py",
    "actualizar_ligas_football_data.py",
    "recalcular_dinamicas_calendario.py",
    "actualizar_fuente_losilla.py",
    "actualizar_contexto_equipos.py",
    "actualizar_analisis_ia.py",
    "construir_historial_quinielas.py",
    "actualizar_aprendizaje_ia.py",
    "generar_artefactos_compuerta_aprendizaje.py",
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
    # --- Resultados via fuentes libres (ESPN, TheSportsDB, OpenFootball — sin key) ---
    "actualizar_resultados_libres.py",
    # --- Resultados via APIs (BallDontLie, API-Football, openfootball) ---
    "actualizar_resultados_apis.py",
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
        mensaje = f"Falta script activo: {nombre}"
        if nombre in SCRIPTS_CRITICOS_PREDICCION:
            raise ErrorCriticoPrediccion(mensaje)
        print(f"AVISO: {mensaje}. Se continua con el siguiente script.")
        return False

    print(f"\n=== Ejecutando {nombre} ===")
    try:
        subprocess.run([sys.executable, str(ruta)], cwd=ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        if nombre in SCRIPTS_CRITICOS_PREDICCION:
            raise ErrorCriticoPrediccion(
                f"Error critico de prediccion en {nombre}: codigo {exc.returncode}."
            ) from exc
        print(f"AVISO: {nombre} termino con codigo {exc.returncode}; se continua.")
        return False
    except Exception as exc:
        if nombre in SCRIPTS_CRITICOS_PREDICCION:
            raise ErrorCriticoPrediccion(
                f"Excepcion critica de prediccion en {nombre}: {exc}"
            ) from exc
        print(f"AVISO: excepcion no critica en {nombre}: {exc}")
        traceback.print_exc()
        return False
    return True


def ejecutar_sistema():
    gestionar_mercado_y_temporada()
    for script in SCRIPTS_ACTIVOS:
        if script in SCRIPTS_VISUALES_DESACTIVADOS:
            print(f"\n=== Omitiendo {script}: bloqueo de cambios visuales activo ===")
            continue
        ejecutar_script(script)
    print("\nActualizacion completa; cualquier fallo no critico queda avisado en el log.")


def main():
    try:
        ejecutar_sistema()
    except ErrorCriticoPrediccion:
        print("ERROR_CRITICO_PREDICCION: se detiene por validacion de prediccion.")
        traceback.print_exc()
        raise
    except Exception as exc:
        print("AVISO_GLOBAL_ACTUALIZACION: excepcion no critica capturada en actualizar_todo.py")
        print(f"Tipo: {type(exc).__name__}")
        print(f"Detalle: {exc}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
