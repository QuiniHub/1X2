import os
import json

def obtener_datos_base_jornadas():
    return {
        "61": [
            {"local": "Levante UD", "Local": "Levante UD", "visitante": "CA Osasuna", "Visitante": "CA Osasuna", "estado": "Programado"},
            {"local": "Elche CF", "Local": "Elche CF", "visitante": "Deportivo Alavés", "Visitante": "Deportivo Alavés", "estado": "Programado"},
            {"local": "Sevilla FC", "Local": "Sevilla FC", "visitante": "RCD Espanyol de Barcelona", "Visitante": "RCD Espanyol de Barcelona", "estado": "Programado"},
            {"local": "Club Atlético de Madrid", "Local": "Club Atlético de Madrid", "visitante": "RC Celta de Vigo", "Visitante": "RC Celta de Vigo", "estado": "Programado"},
            {"local": "Real Sociedad de Fútbol", "Local": "Real Sociedad de Fútbol", "visitante": "Real Betis Balompié", "Visitante": "Real Betis Balompié", "estado": "Programado"},
            {"local": "RCD Mallorca", "Local": "RCD Mallorca", "visitante": "Villarreal CF", "Visitante": "Villarreal CF", "estado": "Programado"},
            {"local": "Athletic Club", "Local": "Athletic Club", "visitante": "Valencia CF", "Visitante": "Valencia CF", "estado": "Programado"},
            {"local": "Real Oviedo", "Local": "Real Oviedo", "visitante": "Getafe CF", "Visitante": "Getafe CF", "estado": "Programado"},
            {"local": "FC Barcelona", "Local": "FC Barcelona", "visitante": "Real Madrid CF", "Visitante": "Real Madrid CF", "estado": "Programado"},
            {"local": "Rayo Vallecano de Madrid", "Local": "Rayo Vallecano de Madrid", "visitante": "Girona FC", "Visitante": "Girona FC", "estado": "Programado"},
            {"local": "Albacete CF", "Local": "Albacete CF", "visitante": "Cultural Leonesa", "Visitante": "Cultural Leonesa", "estado": "Programado"},
            {"local": "Cádiz CF", "Local": "Cádiz CF", "visitante": "Deportivo La Coruña", "Visitante": "Deportivo La Coruña", "estado": "Programado"},
            {"local": "Córdoba CF", "Local": "Córdoba CF", "visitante": "Granada CF", "Visitante": "Granada CF", "estado": "Programado"},
            {"local": "SD Huesca", "Local": "SD Huesca", "visitante": "Real Sociedad B", "Visitante": "Real Sociedad B", "estado": "Programado"},
            {"local": "CD Leganés", "Local": "CD Leganés", "visitante": "Racing Santander", "Visitante": "Racing Santander", "estado": "Programado"}
        ]
    }

def generar_archivos_jornadas_limpios():
    os.makedirs("data", exist_ok=True)
    jornadas_datos = obtener_datos_base_jornadas()
    for num_jornada, partidos in jornadas_datos.items():
        partidos_primera, partidos_segunda = [], []
        for idx, partido in enumerate(partidos):
            partido.update({"goles_local": "", "Goles_Local": "", "goles_visitante": "", "Goles_Visitante": ""})
            if idx < 10: partidos_primera.append(partid)
            else: partidos_segunda.append(partido)
        with open("data/partidos_primera.json", "w", encoding="utf-8") as f: json.dump(partidos_primera, f, indent=4, ensure_ascii=False)
        with open("data/partidos_segunda.json", "w", encoding="utf-8") as f: json.dump(partidos_segunda, f, indent=4, ensure_ascii=False)

if __name__ == "__main__": generar_archivos_jornadas_limpios()
