import json
import os


def obtener_datos_base_jornadas():
    # Define el orden oficial de los partidos del boleto activo de la Quiniela.
    # Aqui se anade la jornada objetivo sin cambiar el contrato de los JSON actuales.
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
            {"local": "Barcelona", "visitante": "Real Madrid", "estado": "Programado"},
        ]
    }
    return jornadas_maestras


def cargar_json_seguro(ruta_archivo, defecto):
    if not os.path.exists(ruta_archivo):
        return defecto
    try:
        with open(ruta_archivo, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        print(f"Archivo {ruta_archivo} corrupto o vacio. Se usa valor por defecto.")
        return defecto
    return datos


def cargar_historial_existente(ruta_archivo):
    # El historial debe ser un diccionario por jornada.
    # Si por error apunta a un JSON antiguo tipo lista, no lo usa como historial para evitar TypeError.
    datos = cargar_json_seguro(ruta_archivo, {})
    if isinstance(datos, dict):
        return datos
    print(f"{ruta_archivo} no tiene formato historial; se inicia historial nuevo sin tocar el JSON actual.")
    return {}


def preparar_partido(partido):
    partido = dict(partido)
    partido.setdefault("goles_local", "")
    partido.setdefault("goles_visitante", "")
    return partido


def guardar_json(ruta_archivo, datos):
    with open(ruta_archivo, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)


def generar_archivos_jornadas_limpios():
    print("Actualizando jornadas sin romper los JSON que ya usa la web...")
    os.makedirs("data", exist_ok=True)

    # Archivos actuales: se mantienen como listas para no romper dependencias existentes.
    ruta_1a_actual = "data/partidos_primera.json"
    ruta_2a_actual = "data/partidos_segunda.json"

    # Archivos historicos nuevos: aqui si se guarda por numero de jornada.
    ruta_1a_historial = "data/historial_partidos_primera.json"
    ruta_2a_historial = "data/historial_partidos_segunda.json"

    historial_primera = cargar_historial_existente(ruta_1a_historial)
    historial_segunda = cargar_historial_existente(ruta_2a_historial)

    ultimos_primera = []
    ultimos_segunda = []

    for num_jornada, partidos in obtener_datos_base_jornadas().items():
        partidos_primera = []
        partidos_segunda = []

        for idx, partido_original in enumerate(partidos):
            partido = preparar_partido(partido_original)
            if idx < 8 or idx == 14:
                partidos_primera.append(partido)
            else:
                partidos_segunda.append(partido)

        historial_primera[str(num_jornada)] = partidos_primera
        historial_segunda[str(num_jornada)] = partidos_segunda
        ultimos_primera = partidos_primera
        ultimos_segunda = partidos_segunda

    guardar_json(ruta_1a_historial, historial_primera)
    guardar_json(ruta_2a_historial, historial_segunda)

    # Se escriben tambien los archivos actuales, pero conservando su formato de lista.
    if ultimos_primera:
        guardar_json(ruta_1a_actual, ultimos_primera)
    if ultimos_segunda:
        guardar_json(ruta_2a_actual, ultimos_segunda)

    print(f"Historial Primera guardado en: {ruta_1a_historial}")
    print(f"Historial Segunda guardado en: {ruta_2a_historial}")
    print(f"JSON actual Primera conservado como lista en: {ruta_1a_actual}")
    print(f"JSON actual Segunda conservado como lista en: {ruta_2a_actual}")


if __name__ == "__main__":
    generar_archivos_jornadas_limpios()
    print("Proceso de consolidacion de jornadas finalizado OK.")