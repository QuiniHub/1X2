import os
import re
import requests
import json
import xml.etree.ElementTree as ET

# Diccionarios globales de mapeo y limpieza
MAPEO_EQUIPOS = {
    "primera": {
        "barcelona": "Barcelona", "real madrid": "Real Madrid", "atletico": "Ath Madrid",
        "atleti": "Ath Madrid", "athletic": "Ath Bilbao", "real sociedad": "Sociedad", 
        "betis": "Betis", "villarreal": "Villarreal", "valencia": "Valencia", 
        "sevilla": "Sevilla", "osasuna": "Osasuna", "girona": "Girona", 
        "rayo": "Vallecano", "celta": "Celta", "getafe": "Getafe", 
        "mallorca": "Mallorca", "alaves": "Alaves", "valladolid": "Valladolid",
        "leganes": "Leganes", "espanyol": "Espanol", "levante": "Levante", 
        "elche": "Elche", "oviedo": "Real Oviedo"
    },
    "segunda": {
        "albacete": "Albacete", "almeria": "Almeria", "andorra": "Andorra",
        "burgos": "Burgos", "cadiz": "Cadiz", "castellon": "Castellon",
        "ceuta": "Ceuta", "cordoba": "Cordoba", "coruña": "La Coruña",
        "deportivo": "La Coruña", "eibar": "Eibar", "eldense": "Eldense", 
        "granada": "Granada", "huesca": "Huesca", "malaga": "Malaga", 
        "mirandes": "Mirandes", "oviedo": "Oviedo", "racing": "Santander", 
        "santander": "Santander", "sporting": "Sp Gijon", "gijon": "Sp Gijon", 
        "tenerife": "Tenerife", "zaragoza": "Zaragoza", "ferrol": "Racing Ferrol", 
        "leonesa": "Cultural Leonesa", "cultural": "Cultural Leonesa", 
        "sociedad b": "Sociedad B", "las palmas": "Las Palmas"
    }
}

ALIAS_EXTRA = {
    "primera": [
        "Barcelona", "Real Madrid", "Atletico", "Atleti", "Athletic", "Real Sociedad", "Betis",
        "Villarreal", "Valencia", "Sevilla", "Osasuna", "Girona", "Rayo", "Celta",
        "Getafe", "Mallorca", "Alaves", "Valladolid", "Leganes", "Espanyol", "Levante", "Elche", "Oviedo"
    ],
    "segunda": [
        "Albacete", "Deportivo", "La Coruña", "Racing", "Sporting", "Gijon",
        "Sociedad B", "Valladolid", "Cultural", "Leonesa", "Ceuta", "Almeria", 
        "Las Palmas", "Castellon", "Cordoba", "Malaga", "Cadiz", "Granada", 
        "Burgos", "Huesca", "Eibar", "Mirandes", "Leganes", "Andorra", "Zaragoza"
    ]
}


def clean(txt):
    if not txt:
        return ""
    return " ".join(txt.split())

def sin_acentos(txt):
    reemplazos = {('á', 'é', 'í', 'ó', 'ú'): ('a', 'e', 'i', 'o', 'u')}
    for origenes, destino in reemplazos.items():
        for origen in origenes:
            txt = txt.replace(origen, destino)
    return txt

def normalizar(txt, tipo):
    txt = sin_acentos(clean(txt).lower())
      palabras_a_eliminar = [
        "cf", "sad", "ud", "rc", "club", "de futbol", 
        "balompie", "de madrid", "de vigo"
    ]
    for palabra in palabras_a_eliminar:
        txt = txt.replace(palabra, "")
    txt = txt.strip()

    for clave, valor in MAPEO_EQUIPOS[tipo].items():
        if clave in txt:
            return valor
    return None

def construir_regex_equipos(tipo):
    todos = ALIAS_EXTRA[tipo]
    todos_esc = [re.escape(x) for x in todos]
    return "|".join(todos_esc)

def descargar_texto_url(url):
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            return r.text
    except Exception as e:
        print(f"Error accediendo a {url}: {e}")
    return ""

def reforzar_resultados_y_horas(tipo, jornadas_dict):
    print(f"Reforzando {tipo}...")
    equipos_re = construir_regex_equipos(tipo)
    
    # Expresiones regulares adaptadas a los alias elásticos
    patrones = [
        re.compile(rf"({equipos_re})\s+(\d+)\s*-\s*(\d+)\s+({equipos_re})", re.I),
        re.compile(rf"({equipos_re})\s*vs\s*({equipos_re})\s*.*?(\d{{2}}:\d{{2}})", re.I)
    ]
    
    urls_fuentes = [
        "mundodeportivo.com",
        "as.com"
    ]
    
    for url in urls_fuentes:
        html_content = descargar_texto_url(url)
        if not html_content:
            continue
            
        # Buscar partidos ya jugados (goles)
        for m in patrones[0].finditer(html_content):
            loc_web, g_l, g_v, vis_web = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
            loc_norm = normalizar(loc_web, tipo)
            vis_norm = normalizar(vis_web, tipo)
            
            if loc_norm and vis_norm:
                for j_num, partidos in jornadas_dict.items():
                    for p in partidos:
                        if p["local"] == loc_norm and p["visitante"] == vis_norm:
                            p["goles_local"] = str(g_l)
                            p["goles_visitante"] = str(g_v)
                            p["estado"] = "Finalizado"

        # Buscar horarios de partidos futuros
        for m in patrones[1].finditer(html_content):
            loc_web, vis_web, hora = m.group(1), m.group(2), m.group(3)
            loc_norm = normalizar(loc_web, tipo)
            vis_norm = normalizar(vis_web, tipo)
            
            if loc_norm and vis_norm:
                for j_num, partidos in jornadas_dict.items():
                    for p in partidos:
                        if p["local"] == loc_norm and p["visitante"] == vis_norm:
                            if not p.get("goles_local"):
                                p["hora"] = hora
                                p["estado"] = "Programado"

def procesar_actualizacion():
    os.makedirs("data", exist_ok=True)
    
    for tipo in ["primera", "segunda"]:
        ruta_archivo = f"data/partidos_{tipo}.json"
        
        # Cargar base de datos existente o crear estructura básica vacía si no existe
        if os.path.exists(ruta_archivo):
            try:
                with open(ruta_archivo, "r", encoding="utf-8") as f:
                    jornadas = json.load(f)
            except Exception:
                jornadas = {}
        else:
            jornadas = {}
            
        reforzar_resultados_y_horas(tipo, jornadas)
        
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            json.dump(jornadas, f, indent=4, ensure_ascii=False)
            print(f"Archivo actualizado guardado con éxito: {ruta_archivo}")

if __name__ == "__main__":
    procesar_actualizacion()
