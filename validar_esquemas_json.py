"""
Validador de esquemas JSON para el sistema de predicción de quinielas.
Asegura que los archivos JSON críticos tienen la estructura correcta.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORIA = DATA / "memoria_ia"


# Esquemas de validación
ESQUEMAS = {
    "prediccion": {
        "type": "object",
        "required": ["version", "jornada", "partidos", "coste"],
        "properties": {
            "version": {"type": "string"},
            "jornada": {"type": "integer", "minimum": 1, "maximum": 42},
            "partidos": {
                "type": "array",
                "minItems": 14,
                "maxItems": 14,
                "items": {
                    "type": "object",
                    "required": ["num", "signo_final", "probabilidades"],
                    "properties": {
                        "num": {"type": "integer"},
                        "signo_final": {"type": "string", "enum": ["1", "X", "2", "1X", "1X2", "X2", "12"]},
                        "tipo": {"type": "string", "enum": ["FIJO", "DOBLE", "TRIPLE"]},
                        "probabilidades": {
                            "type": "object",
                            "properties": {
                                "1": {"type": "number"},
                                "X": {"type": "number"},
                                "2": {"type": "number"}
                            }
                        }
                    }
                }
            },
            "coste": {
                "type": "object",
                "properties": {
                    "apuestas": {"type": "integer"},
                    "importe_quiniela": {"type": "number"},
                    "importe_total": {"type": "number"}
                }
            }
        }
    },
    
    "memoria_ia": {
        "type": "object",
        "required": ["version", "temporada", "ligas"],
        "properties": {
            "version": {"type": "string"},
            "temporada": {"type": "string"},
            "ligas": {
                "type": "object",
                "properties": {
                    "primera": {
                        "type": "object",
                        "properties": {
                            "equipos": {"type": "array"}
                        }
                    },
                    "segunda": {
                        "type": "object",
                        "properties": {
                            "equipos": {"type": "array"}
                        }
                    }
                }
            }
        }
    },
    
    "contexto_competitivo": {
        "type": "object",
        "properties": {
            "primera": {
                "type": "object",
                "properties": {
                    "equipos": {"type": "array"}
                }
            },
            "segunda": {
                "type": "object",
                "properties": {
                    "equipos": {"type": "array"}
                }
            }
        }
    },
    
    "jornada": {
        "type": "object",
        "required": ["jornada", "partidos"],
        "properties": {
            "jornada": {"type": "integer"},
            "partidos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["num", "local", "visitante"],
                    "properties": {
                        "num": {"type": "integer"},
                        "local": {"type": "string"},
                        "visitante": {"type": "string"},
                        "resultado": {"type": ["string", "null"]},
                        "signo_oficial": {"type": ["string", "null"]}
                    }
                }
            }
        }
    }
}


def validar_schema(datos, schema):
    """
    Validación básica de esquema JSON.
    
    Args:
        datos: Diccionario a validar
        schema: Esquema de validación
        
    Returns:
        (es_valido: bool, errores: list)
    """
    errores = []
    
    if not isinstance(datos, dict):
        return False, ["Datos no son un diccionario"]
    
    if "required" in schema:
        for campo in schema["required"]:
            if campo not in datos:
                errores.append(f"Campo requerido ausente: {campo}")
    
    if "properties" in schema:
        for campo, definicion in schema.get("properties", {}).items():
            if campo in datos:
                valor = datos[campo]
                
                if "type" in definicion:
                    tipos_esperados = definicion["type"] if isinstance(definicion["type"], list) else [definicion["type"]]
                    tipo_actual = type(valor).__name__
                    
                    tipo_valido = False
                    for tipo_esp in tipos_esperados:
                        if tipo_esp == "object" and isinstance(valor, dict):
                            tipo_valido = True
                        elif tipo_esp == "array" and isinstance(valor, list):
                            tipo_valido = True
                        elif tipo_esp == "string" and isinstance(valor, str):
                            tipo_valido = True
                        elif tipo_esp == "integer" and isinstance(valor, int) and not isinstance(valor, bool):
                            tipo_valido = True
                        elif tipo_esp == "number" and isinstance(valor, (int, float)) and not isinstance(valor, bool):
                            tipo_valido = True
                        elif tipo_esp == "null" and valor is None:
                            tipo_valido = True
                    
                    if not tipo_valido:
                        errores.append(f"Campo {campo}: tipo {tipo_actual}, esperado {definicion['type']}")
    
    return len(errores) == 0, errores


def validar_archivo(nombre, ruta, schema_tipo):
    """
    Validar un archivo JSON específico.
    
    Args:
        nombre: Nombre descriptivo del archivo
        ruta: Ruta del archivo
        schema_tipo: Tipo de esquema a usar
        
    Returns:
        (es_valido: bool, mensaje: str)
    """
    if not ruta.exists():
        return False, f"❌ {nombre}: Archivo no encontrado ({ruta})"
    
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, f"❌ {nombre}: JSON inválido - {str(e)[:100]}"
    except Exception as e:
        return False, f"❌ {nombre}: Error al leer - {str(e)[:100]}"
    
    schema = ESQUEMAS.get(schema_tipo, {})
    if not schema:
        return False, f"❌ {nombre}: Esquema no definido ({schema_tipo})"
    
    es_valido, errores = validar_schema(datos, schema)
    
    if es_valido:
        return True, f"✓ {nombre}: Validado correctamente"
    else:
        errores_str = "; ".join(errores[:3])  # Mostrar solo los 3 primeros errores
        return False, f"❌ {nombre}: {errores_str}"


def validar_prediccion_actual():
    """Validar la predicción más reciente generada."""
    ruta = DATA / "predicciones" / "ultima_prediccion.json"
    return validar_archivo("Predicción actual", ruta, "prediccion")


def validar_memoria_ia():
    """Validar la memoria global de aprendizaje."""
    ruta = MEMORIA / "aprendizaje_global.json"
    return validar_archivo("Memoria IA", ruta, "memoria_ia")


def validar_contexto_competitivo():
    """Validar el contexto competitivo."""
    ruta = MEMORIA / "contexto_competitivo.json"
    return validar_archivo("Contexto competitivo", ruta, "contexto_competitivo")


def validar_jornada_actual():
    """Validar la jornada actual."""
    # Buscar la última jornada generada
    jornadas_dir = DATA / "jornadas"
    if not jornadas_dir.exists():
        return False, "❌ Directorio de jornadas no existe"
    
    jornadas = sorted(jornadas_dir.glob("jornada_*.json"), 
                     key=lambda p: int(p.stem.split("_")[1]) if "_" in p.stem else 0,
                     reverse=True)
    
    if not jornadas:
        return False, "❌ No hay jornadas disponibles"
    
    ultima_jornada = jornadas[0]
    return validar_archivo(f"Jornada {ultima_jornada.stem}", ultima_jornada, "jornada")


def generar_reporte_validacion():
    """Generar reporte completo de validación."""
    reporte = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "validaciones": []
    }
    
    validaciones = [
        ("prediccion_actual", validar_prediccion_actual),
        ("memoria_ia", validar_memoria_ia),
        ("contexto_competitivo", validar_contexto_competitivo),
        ("jornada_actual", validar_jornada_actual),
    ]
    
    todas_validas = True
    for nombre, funcion_validacion in validaciones:
        es_valido, mensaje = funcion_validacion()
        print(mensaje)
        reporte["validaciones"].append({
            "nombre": nombre,
            "valido": es_valido,
            "mensaje": mensaje
        })
        if not es_valido:
            todas_validas = False
    
    reporte["estado"] = "ok" if todas_validas else "errores_detectados"
    
    # Guardar reporte
    ruta_reporte = DATA / "validacion_schema.json"
    ruta_reporte.parent.mkdir(parents=True, exist_ok=True)
    ruta_reporte.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return todas_validas, reporte


def main():
    print("\n" + "="*60)
    print("Validación de esquemas JSON")
    print("="*60 + "\n")
    
    todas_validas, reporte = generar_reporte_validacion()
    
    print("\n" + "="*60)
    if todas_validas:
        print("✓ TODAS LAS VALIDACIONES PASARON")
    else:
        print("❌ ALGUNOS ARCHIVOS TIENEN PROBLEMAS")
    print("="*60 + "\n")
    
    sys.exit(0 if todas_validas else 1)


if __name__ == "__main__":
    main()
