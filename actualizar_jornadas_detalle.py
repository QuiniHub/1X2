import os
import json

def obtener_datos_base_jornadas():
    """
    Define el orden oficial de los partidos del boleto activo de la Quiniela.
    Aquí añades la jornada actual del fin de semana sin afectar al historial.
    """
    jornadas_maestras = {
        "61": [
            {"local": "Elche", "visitante": "Alaves", "estado": "Programado"},
            {"local": "Sevilla", "visitante": "Espanyol", "estado": "Programado"},
            {"local": "Ath Madrid", "visitante": "Celta", "estado": "Programado"},
            {"local": "Sociedad", "visitante": "Betis", "estado": "Programado"},
            {"local": "Mallorca", "visitante": "Villarreal", "estado": "Programado"},
            {"local": "Ath Bilbao", "visitante": "Valencia", "estado": "Programado"},
            {"local": "Real Oviedo", "visitante": "Getafe", "estado": "Programado"},
            {"local": "Vallecano", "visitante": "Girona", "estado": "Programado"},
            {"local": "Ceuta", "visitante": "Castellon", "estado": "Programado"},
            {"local": "Burgos", "visitante": "Almeria", "estado": "Programado"},
            {"local": "Sp Gijon", "visitante": "Malaga", "estado": "Programado"},
            {"local": "Andorra", "visitante": "Las Palmas", "estado": "Programado"},
            {"local": "Leganes", "visitante": "Santander", "estado": "Programado"},
            {"local": "Cordoba", "visitante": "Granada", "estado": "Programado"},
            {"local": "Barcelona", "visitante": "Real Madrid", "estado": "Programado"} # Pleno al 15
        ]
    }
    return jornadas_maestras

def cargar_historial_existente(ruta_archivo):
    """
    Carga de forma segura el archivo JSON histórico para no borrar las jornadas anteriores.
    """
    if os.path.exists(ruta_archivo):
        try:
            with open(ruta_archivo, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            print(f"⚠️ Archivo {ruta_archivo} corrupto o vacío. Creando nuevo historial.")
            return {}
    return {}

def generar_archivos_jornadas_limpios():
    print("🔄 Actualizando base de datos global de jornadas sin borrar el historial...")
    os.makedirs("data", exist_ok=True)
    
    # 1. Cargar el historial que ya tienes guardado en tu servidor de GitHub
    ruta_1a = "data/partidos_primera.json"
    ruta_2a = "data/partidos_segunda.json"
    
    historial_primera = cargar_historial_existente(ruta_1a)
    historial_segunda = cargar_historial_existente(ruta_2a)
    
    # 2. Obtener la nueva jornada a integrar
    nuevas_jornadas = obtener_datos_base_jornadas()
    
    for num_jornada, partidos in nuevas_jornadas.items():
        partidos_primera = []
        partidos_segunda = []
        
        # Clasificar los partidos según su orden oficial en el boleto
        for idx, partido in enumerate(partidos):
            if "goles_local" not in partido:
                partio["goles_local"] = ""
            if "goles_visitante" not in partido:
                partido["goles_visitante"] = ""
                
            # Separación estricta por ligas
            if idx < 8 or idx == 14:
                partidos_primera.append(partido)
            else:
                partidos_segunda.append(partido)
        
        # 3. Guardar o actualizar la jornada en el diccionario global sin machacar el resto
        historial_primera[num_jornada] = partidos_primera
        historial_segunda[num_jornada] = partidos_segunda
        
    # 4. Escribir el nuevo archivo consolidado con TODAS las jornadas juntas
    with open(ruta_1a, "w", encoding="utf-8") as f:
        json.dump(historial_primera, f, indent=4, ensure_ascii=False)
    print(f"✅ Historial consolidado de Primera División guardado en: {ruta_1a}")
        
    with open(ruta_2a, "w", encoding="utf-8") as f:
        json.dump(historial_segunda, f, indent=4, ensure_ascii=False)
    print(f"✅ Historial consolidado de Segunda División guardado en: {ruta_2a}")

if __name__ == "__main__":
    generar_archivos_jornadas_limpios()
    print("🚀 Proceso de consolidación de jornadas finalizado OK.")

