import subprocess
import sys
import json
import logging
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

# Configurar logging estructurado
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Lista de scripts activos (SIN DUPLICADOS - corregido)
SCRIPTS_ACTIVOS = [
    # Fase 1: Ingesta de datos crudos
    "actualizar_jornadas_detalle.py",
    "asegurar_proxima_jornada.py",
    "actualizar_selector_jornadas_web.py",
    "actualizar_resultados_directo.py",
    "aplicar_correcciones_resultados.py",
    "actualizar_clasificaciones_oficiales.py",
    "corregir_clasificacion_segunda.py",
    "actualizar_ligas_football_data.py",
    "recalcular_dinamicas_calendario.py",
    
    # Fase 2: Construcción de memoria e índices
    "actualizar_contexto_equipos.py",
    "actualizar_analisis_ia.py",
    "construir_historial_quinielas.py",
    "actualizar_aprendizaje_ia.py",
    "construir_memoria_ia.py",
    "sincronizar_dinamicas_memoria.py",

    # Fase 3: Fuente única de verdad competitiva (CRÍTICA)
    "generar_contexto_competitivo.py",
    "aplicar_objetivos_oficiales_json.py",
    "forzar_overrides.py",
    "validar_contexto_actual.py",
    "construir_fuente_verdad_competitiva.py",

    # Fase 4: Motor y generación de predicción
    "aprender_patrones_competitivos.py",
    "aplicar_patrones_motor.py",
    "reforzar_patrones_motor.py",
    "corregir_emparejamiento_motor.py",
    "mejorar_motor_dinamica_10.py",
    "alinear_pronostico_analisis.py",
    "mejorar_prioridad_coberturas.py",
    "motor_prediccion_quiniela.py",
    
    # Fase 5: Alineación boleto-análisis y asistentes
    "alinear_boleto_con_analisis.py",
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
    
    # Fase 6: Estado vivo y coherencia
    "generar_estado_vivo_ia.py",
    "regenerar_estado_vivo_actual.py",
    "ajustar_estado_vivo_motivacion.py",
    "aplicar_patrones_web.py",
    "corregir_emparejamiento_equipos.py",
    "verificar_coherencia_pronostico.py",
    
    # Fase 7: Persistencia y validación
    "guardar_snapshot_prediccion.py",
    "backtesting_pre_cierre.py",
    
    # Fase 8: Diagnóstico final
    "diagnostico_sistema.py",
    "control_calidad_actualizacion.py",
    "normalizar_diagnostico_control.py",
    "normalizar_textos_generados.py",
]

# Validar que no hay duplicados
_duplicados = [script for script in SCRIPTS_ACTIVOS if SCRIPTS_ACTIVOS.count(script) > 1]
if _duplicados:
    logger.error(f"❌ Scripts duplicados detectados: {set(_duplicados)}")
    raise SystemExit("Hay scripts duplicados en SCRIPTS_ACTIVOS")

logger.info(f"✓ Ejecutarán {len(SCRIPTS_ACTIVOS)} scripts sin duplicados")


def gestionar_mercado_y_temporada():
    """Detectar cambios de temporada y alertar si es necesario."""
    mes = datetime.now().month
    year = datetime.now().year
    if mes >= 8:
        logger.warning(f"⚠ Pretemporada detectada: preparar temporada {year}/{year + 1}.")


def validar_script_existe(nombre):
    """Validar que el script existe antes de intentar ejecutarlo."""
    ruta = ROOT / nombre
    if not ruta.exists():
        logger.error(f"❌ Falta script activo: {nombre}")
        raise SystemExit(f"Archivo no encontrado: {ruta}")
    if not ruta.suffix == ".py":
        logger.error(f"❌ {nombre} no es un archivo Python")
        raise SystemExit(f"No es un archivo .py: {nombre}")


def ejecutar_script(nombre, numero, total):
    """
    Ejecutar un script individual con logging mejorado.
    
    Args:
        nombre: Nombre del script a ejecutar
        numero: Número secuencial (para logging)
        total: Total de scripts (para logging)
    """
    validar_script_existe(nombre)
    
    ruta = ROOT / nombre
    logger.info(f"[{numero}/{total}] Ejecutando {nombre}...")
    
    try:
        resultado = subprocess.run(
            [sys.executable, str(ruta)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        if resultado.returncode != 0:
            logger.error(f"❌ Fallo en {nombre} (código {resultado.returncode})")
            if resultado.stderr:
                logger.error(f"   Stderr: {resultado.stderr[:500]}")
            raise SystemExit(f"El script {nombre} falló con código {resultado.returncode}")
        
        if resultado.stdout.strip():
            for linea in resultado.stdout.strip().split('\n'):
                logger.info(f"   {linea}")
                
    except subprocess.TimeoutExpired:
        logger.error(f"❌ Timeout en {nombre} (>1 hora)")
        raise SystemExit(f"El script {nombre} tardó demasiado")
    except Exception as e:
        logger.error(f"❌ Error ejecutando {nombre}: {e}")
        raise


def generar_registro_ejecucion(fecha_inicio, fecha_fin, exitoso=True):
    """Generar un registro JSON de la ejecución para auditoría."""
    registro = {
        "version": "1.0",
        "fecha_inicio": fecha_inicio.isoformat(),
        "fecha_fin": fecha_fin.isoformat(),
        "duracion_segundos": (fecha_fin - fecha_inicio).total_seconds(),
        "scripts_totales": len(SCRIPTS_ACTIVOS),
        "exitoso": exitoso,
        "scripts_ejecutados": SCRIPTS_ACTIVOS,
    }
    
    ruta_registro = DATA / "registros_ejecucion"
    ruta_registro.mkdir(parents=True, exist_ok=True)
    
    archivo = ruta_registro / f"ejecucion_{fecha_inicio.strftime('%Y%m%d_%H%M%S')}.json"
    try:
        archivo.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"✓ Registro de ejecución guardado: {archivo}")
    except Exception as e:
        logger.warning(f"⚠ No se pudo guardar registro de ejecución: {e}")
    
    ultima = DATA / "ultima_ejecucion.json"
    try:
        ultima.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"⚠ No se pudo guardar último registro: {e}")


def ejecutar_sistema():
    """Orquestador principal: ejecuta todos los scripts en orden."""
    fecha_inicio = datetime.now()
    logger.info(f"\n{'='*60}")
    logger.info(f"Iniciando actualización completa del sistema")
    logger.info(f"Hora: {fecha_inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Scripts a ejecutar: {len(SCRIPTS_ACTIVOS)}")
    logger.info(f"{'='*60}\n")
    
    gestionar_mercado_y_temporada()
    
    scripts_exitosos = 0
    script_fallido = None
    
    try:
        for idx, script in enumerate(SCRIPTS_ACTIVOS, 1):
            ejecutar_script(script, idx, len(SCRIPTS_ACTIVOS))
            scripts_exitosos += 1
            
    except SystemExit as e:
        script_fallido = str(e)
        fecha_fin = datetime.now()
        logger.error(f"\n{'='*60}")
        logger.error(f"❌ ACTUALIZACIÓN FALLIDA")
        logger.error(f"Scripts completados: {scripts_exitosos}/{len(SCRIPTS_ACTIVOS)}")
        logger.error(f"Error: {script_fallido}")
        logger.error(f"{'='*60}\n")
        generar_registro_ejecucion(fecha_inicio, fecha_fin, exitoso=False)
        raise
    
    fecha_fin = datetime.now()
    duracion = (fecha_fin - fecha_inicio).total_seconds()
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✓ ACTUALIZACIÓN COMPLETADA SIN ERRORES")
    logger.info(f"Scripts ejecutados: {scripts_exitosos}")
    logger.info(f"Duración: {duracion:.1f} segundos ({duracion/60:.1f} minutos)")
    logger.info(f"Fecha finalización: {fecha_fin.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*60}\n")
    
    generar_registro_ejecucion(fecha_inicio, fecha_fin, exitoso=True)


if __name__ == "__main__":
    try:
        ejecutar_sistema()
    except Exception as e:
        logger.critical(f"Error fatal: {e}")
        sys.exit(1)
