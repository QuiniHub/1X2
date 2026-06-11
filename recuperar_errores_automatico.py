"""
Sistema de recuperación automática de errores.
Detecta y restaura archivos corruptos, implementa rollback de cambios fallidos.
"""

import json
import shutil
import sys
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORIA = DATA / "memoria_ia"
BACKUPS = DATA / ".backups"


def crear_backup(ruta_archivo, prefijo="pre"):
    """
    Crear backup de un archivo antes de modificarlo.
    
    Args:
        ruta_archivo: Ruta del archivo a respaldar
        prefijo: Prefijo del nombre del backup (pre, post, etc)
        
    Returns:
        Ruta del archivo de backup creado
    """
    if not ruta_archivo.exists():
        return None
    
    BACKUPS.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_backup = f"{prefijo}_{ruta_archivo.stem}_{timestamp}.json"
    ruta_backup = BACKUPS / nombre_backup
    
    try:
        shutil.copy2(ruta_archivo, ruta_backup)
        return ruta_backup
    except Exception as e:
        print(f"⚠ No se pudo crear backup de {ruta_archivo}: {e}")
        return None


def restaurar_desde_backup(ruta_archivo, ruta_backup):
    """
    Restaurar un archivo desde un backup.
    
    Args:
        ruta_archivo: Ruta del archivo a restaurar
        ruta_backup: Ruta del archivo de backup
        
    Returns:
        bool: True si la restauración fue exitosa
    """
    if not ruta_backup.exists():
        print(f"❌ Backup no encontrado: {ruta_backup}")
        return False
    
    try:
        shutil.copy2(ruta_backup, ruta_archivo)
        print(f"✓ Archivo restaurado desde backup: {ruta_archivo}")
        return True
    except Exception as e:
        print(f"❌ Error al restaurar desde backup: {e}")
        return False


def validar_json(ruta):
    """
    Validar que un archivo JSON es válido.
    
    Args:
        ruta: Ruta del archivo JSON
        
    Returns:
        (es_valido: bool, datos: dict o None, error: str o None)
    """
    if not ruta.exists():
        return False, None, f"Archivo no existe: {ruta}"
    
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return True, datos, None
    except json.JSONDecodeError as e:
        return False, None, f"JSON inválido: {str(e)[:100]}"
    except Exception as e:
        return False, None, f"Error al leer archivo: {str(e)[:100]}"


def intentar_reparar_json(ruta):
    """
    Intentar reparar un archivo JSON corrupto.
    
    Args:
        ruta: Ruta del archivo JSON corrupto
        
    Returns:
        (reparado: bool, datos: dict o None)
    """
    if not ruta.exists():
        return False, None
    
    contenido = ruta.read_text(encoding="utf-8", errors="ignore")
    
    # Intentar quitar comentarios y trailing commas
    contenido = contenido.split("//")[0]  # Quitar comentarios
    contenido = contenido.rsplit("}", 1)[0] + "}"  # Quitar trailing commas
    
    try:
        datos = json.loads(contenido)
        print(f"✓ Archivo JSON reparado: {ruta}")
        return True, datos
    except Exception:
        return False, None


def recuperar_desde_backup_temporal(ruta_archivo):
    """
    Buscar el backup más reciente de un archivo y restaurarlo.
    
    Args:
        ruta_archivo: Ruta del archivo a recuperar
        
    Returns:
        (recuperado: bool, ruta_backup: Path o None)
    """
    if not BACKUPS.exists():
        return False, None
    
    # Buscar backups de este archivo
    nombre_base = ruta_archivo.stem
    backups = sorted(
        BACKUPS.glob(f"*_{nombre_base}_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if not backups:
        return False, None
    
    backup_mas_reciente = backups[0]
    
    es_valido, _, error = validar_json(backup_mas_reciente)
    if es_valido:
        if restaurar_desde_backup(ruta_archivo, backup_mas_reciente):
            return True, backup_mas_reciente
    
    return False, None


def verificar_integridad_critica():
    """
    Verificar la integridad de los archivos críticos del sistema.
    
    Returns:
        (todo_ok: bool, problemas: list)
    """
    problemas = []
    
    archivos_criticos = [
        ("Memoria IA", MEMORIA / "aprendizaje_global.json"),
        ("Contexto competitivo", MEMORIA / "contexto_competitivo.json"),
        ("Predicción actual", DATA / "predicciones" / "ultima_prediccion.json"),
    ]
    
    for nombre, ruta in archivos_criticos:
        es_valido, datos, error = validar_json(ruta)
        
        if not es_valido:
            print(f"⚠ {nombre} corrupto o inválido: {error}")
            
            # Intentar reparar
            reparado, datos_reparados = intentar_reparar_json(ruta)
            if reparado:
                ruta.write_text(json.dumps(datos_reparados, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"✓ {nombre} reparado automáticamente")
            else:
                # Intentar restaurar desde backup
                recuperado, backup = recuperar_desde_backup_temporal(ruta)
                if recuperado:
                    print(f"✓ {nombre} recuperado desde backup")
                else:
                    problemas.append(f"{nombre}: No se pudo recuperar")
    
    return len(problemas) == 0, problemas


def limpiar_backups_antiguos(dias=7):
    """
    Limpiar backups más antiguos que N días.
    
    Args:
        dias: Número de días a retener
    """
    if not BACKUPS.exists():
        return
    
    ahora = datetime.now()
    
    for archivo in BACKUPS.glob("*.json"):
        edad_archivo = ahora - datetime.fromtimestamp(archivo.stat().st_mtime)
        
        if edad_archivo.days > dias:
            try:
                archivo.unlink()
                print(f"🗑 Backup antiguo eliminado: {archivo.name}")
            except Exception as e:
                print(f"⚠ No se pudo eliminar backup: {e}")


def generar_reporte_recuperacion():
    """Generar reporte de estado del sistema de recuperación."""
    reporte = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "backups_disponibles": len(list(BACKUPS.glob("*.json"))) if BACKUPS.exists() else 0,
        "directorio_backups": str(BACKUPS),
        "verificaciones": {}
    }
    
    # Verificar integridad
    todo_ok, problemas = verificar_integridad_critica()
    
    reporte["verificaciones"]["integridad"] = "ok" if todo_ok else "problemas_detectados"
    reporte["verificaciones"]["problemas"] = problemas
    reporte["estado_general"] = "operativo" if todo_ok else "degradado"
    
    # Guardar reporte
    ruta_reporte = DATA / "reporte_recuperacion.json"
    ruta_reporte.parent.mkdir(parents=True, exist_ok=True)
    ruta_reporte.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return reporte


def main():
    print("\n" + "="*60)
    print("Sistema de recuperación automática")
    print("="*60 + "\n")
    
    print("1. Verificando integridad de archivos críticos...")
    reporte = generar_reporte_recuperacion()
    
    print("\n2. Limpiando backups antiguos (>7 días)...")
    limpiar_backups_antiguos(dias=7)
    
    print("\n" + "="*60)
    print(f"Estado general: {reporte['estado_general'].upper()}")
    print(f"Backups disponibles: {reporte['backups_disponibles']}")
    print("="*60 + "\n")
    
    sys.exit(0 if reporte['estado_general'] == 'operativo' else 1)


if __name__ == "__main__":
    main()
