import os
import json

# CENSO TIPOGRÁFICO DE TU WEB CORREGIDO AL 100% (Atlético y Ath Bilbao)
EQUIPOS_LIGA = {
    "primera": [
        "Barcelona", "Real Madrid", "Villarreal", "Atlético", "Betis", "Celta", 
        "Getafe", "Ath Bilbao", "Sociedad", "Osasuna", "Vallecano", "Valencia", 
        "Espanol", "Elche", "Mallorca", "Girona", "Sevilla", "Alaves", "Levante", "Oviedo"
    ],
    "segunda": [
        "Santander", "Almeria", "La Coruna", "Las Palmas", "Castellon", "Malaga", 
        "Burgos", "Eibar", "Cordoba", "Andorra", "Ceuta", "Sp Gijon", "Albacete", 
        "Granada", "Valladolid", "Leganes", "Sociedad B", "Cadiz", "Huesca", 
        "Mirandes", "Zaragoza", "Cultural Leonesa"
    ]
}

# TRADUCTOR CRUZADO PARA ENLAZAR LOS PARTIDOS DEL BOLETO CON TUS TABLAS REALES
TRADUCTOR_IA = {
    "club atletico de madrid": "Atlético",
    "atletico de madrid": "Atlético",
    "atleti": "Atlético",
    "atletico": "Atlético",
    "real sociedad de futbol": "Sociedad",
    "real sociedad": "Sociedad",
    "rayo vallecano de madrid": "Vallecano",
    "rayo vallecano": "Vallecano",
    "athletic club": "Ath Bilbao",
    "athletic de bilbao": "Ath Bilbao",
    "rc celta de vigo": "Celta",
    "celta de vigo": "Celta",
    "real betis balompie": "Betis",
    "real betis": "Betis",
    "villarreal cf": "Villarreal",
    "valencia cf": "Valencia",
    "sevilla fc": "Sevilla",
    "ca osasuna": "Osasuna",
    "girona fc": "Girona",
    "getafe cf": "Getafe",
    "rcd mallorca": "Mallorca",
    "deportivo alaves": "Alaves",
    "rcd espanyol de barcelona": "Espanol",
    "rcd espanyol": "Espanol",
    "elche cf": "Elche",
    "real oviedo": "Oviedo",
    "levante ud": "Levante",
    "real madrid cf": "Real Madrid",
    "fc barcelona": "Barcelona",
    "albacete cf": "Albacete",
    "cadiz cf": "Cadiz",
    "cordoba cf": "Cordoba",
    "sd huesca": "Huesca",
    "cd leganes": "Leganes",
    "real sociedad b": "Sociedad B",
    "racing santander": "Santander",
    "deportivo la coruña": "La Coruna"
}

def normalizar_nombre_equipo(nombre):
    if not nombre:
        return ""
    txt = " ".join(nombre.split()).lower()
    
    if txt in TRADUCTOR_IA:
        return TRADUCTOR_IA[txt]
    
    palabras_vacias = ["cf", "sad", "ud", "rc", "rcd", "club", "de futbol", "balompie", "ca", "real", "sd"]
    for p in palabras_vacias:
        txt = txt.replace(p, "")
    txt = txt.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").strip()
    return txt.capitalize()

def procesar_tablas_en_vivo():
    print("📊 Iniciando cómputo de posiciones real para la Quiniela...")
    salida_web = {}

    for tipo in ["primera", "segunda"]:
        tabla = {}
        for eq in EQUIPOS_LIGA[tipo]:
            tabla[eq] = {
                "equipo": eq, "Equipo": eq, "pj": 0, "PJ": 0, "g": 0, "G": 0, 
                "e": 0, "E": 0, "p": 0, "P": 0, "gf": 0, "GF": 0, "gc": 0, "GC": 0, 
                "pts": 0, "PTS": 0
            }
        
        ruta_partidos = f"data/partidos_{tipo}.json"
        if os.path.exists(ruta_partidos):
            try:
                with open(ruta_partidos, "r", encoding="utf-8") as f:
                    partidos = json.load(f)
                
                for p in partidos:
                    gl = p.get("goles_local")
                    gv = p.get("goles_visitante")
                    
                    if gl != "" and gv != "" and gl is not None and gv is not None:
                        l_norm = normalizar_nombre_equipo(p["local"])
                        v_norm = normalizar_nombre_equipo(p["visitante"])
                        
                        l_key = next((k for k in tabla if k.lower() in l_norm.lower() or l_norm.lower() in k.lower()), None)
                        v_key = next((k for k in tabla if k.lower() in v_norm.lower() or v_norm.lower() in k.lower()), None)
                        
                        if l_key and v_key:
                            g_local, g_vis = int(gl), int(gv)
                            
                            tabla[l_key]["pj"] += 1; tabla[l_key]["PJ"] += 1
                            tabla[v_key]["pj"] += 1; tabla[v_key]["PJ"] += 1
                            tabla[l_key]["gf"] += g_local; tabla[l_key]["GF"] += g_local
                            tabla[v_key]["gf"] += g_vis; tabla[v_key]["GF"] += g_vis
                            tabla[l_key]["gc"] += g_vis; tabla[l_key]["GC"] += g_vis
                            tabla[v_key]["gc"] += g_local; tabla[v_key]["GC"] += g_local
                            
                            if g_local > g_vis:
                                tabla[l_key]["g"] += 1; tabla[l_key]["G"] += 1; tabla[l_key]["pts"] += 3; tabla[l_key]["PTS"] += 3
                                tabla[v_key]["p"] += 1; tabla[v_key]["P"] += 1
                            elif g_local < g_vis:
                                tabla[v_key]["g"] += 1; tabla[v_key]["G"] += 1; tabla[v_key]["pts"] += 3; tabla[v_key]["PTS"] += 3
                                tabla[l_key]["p"] += 1; tabla[l_key]["P"] += 1
                            else:
                                tabla[l_key]["e"] += 1; tabla[l_key]["E"] += 1; tabla[l_key]["pts"] += 1; tabla[l_key]["PTS"] += 1
                                tabla[v_key]["e"] += 1; tabla[v_key]["E"] += 1; tabla[v_key]["pts"] += 1; tabla[v_key]["PTS"] += 1
            except Exception as err:
                print(f"⚠️ Alerta leyendo partidos de {tipo}: {err}")

        lista_ordenada = sorted(tabla.values(), key=lambda x: (x["pts"], x["gf"] - x["gc"]), reverse=True)
        salida_web[tipo] = lista_ordenada

    with open("clasificaciones.json", "w", encoding="utf-8") as f:
        json.dump(salida_web, f, indent=4, ensure_ascii=False)
    print("✅ Archivo clasificaciones.json guardado en la raíz con éxito.")

if __name__ == "__main__":
    procesar_tablas_en_vivo()
