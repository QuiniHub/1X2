import os
import re
import requests
import json
import xml.etree.ElementTree as ET

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
    if not txt: return ""
    return " ".join(txt.split())

def sin_acentos(txt):
    reemplazos = {('á', 'é', 'í', 'ó', 'ú'): ('a', 'e', 'i', 'o', 'u')}
    for origenes, destino in reemplazos.items():
        for origen in origenes:
            txt = txt.replace(origen, destino)
    return txt

def normalizar(txt, tipo):
    txt = sin_acentos(clean(txt).lower())
    palabras_a_eliminar = ["cf", "sad", "ud", "rc", "club", "de futbol", "balompie", "de madrid", "de vigo"]
    for palabra in palabras_a_eliminar:
        txt = txt.replace(palabra, "")
    txt = txt.strip()
    for clave, valor in MAPEO_EQUIPOS[tipo].items():
        if clave in txt: return valor
    return None

def construir_regex_equipos(tipo):
    todos = ALIAS_EXTRA[tipo]
    return "|".join([re.escape(x) for x in todos])

def descargar_texto_url(url):
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        if r.status_code == 200: return r.text
    except Exception as e:
        print(f"⚠️ Error al raspar la URL {url}: {e}")
    return ""

def procesar_fuente_html(url, tipo, jornadas, patrones):
    """ Escanea el HTML de un periódico deportivo en busca de goles u horarios """
    html_content = descargar_texto_url(url)
    if not html_content: return

    # Buscar goles y partidos finalizados
    for m in patrones["goles"].finditer(html_content):
        loc_web, g_l, g_v, vis_web = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        loc_norm, vis_norm = normalizar(loc_web, tipo), normalizar(vis_web, tipo)
        if loc_norm and vis_norm:
            for j_num, partidos in jornadas.items():
                for p in partidos:
                    if p["local"] == loc_norm and p["visitante"] == vis_norm:
                        # Si no hay goles guardados o están vacíos, los actualiza
                        if not p.get("goles_local") or p["estado"] != "Finalizado":
                            p["goles_local"] = str(g_l)
                            p["goles_visitante"] = str(g_v)
                            p["estado"] = "Finalizado"

    # Buscar horarios planificados
    for m in patrones["horas"].finditer(html_content):
        loc_web, vis_web, hora = m.group(1), m.group(2), m.group(3)
        loc_norm, vis_norm = normalizar(loc_web, tipo), normalizar(vis_web, tipo)
        if loc_norm and vis_norm:
            for j_num, partidos in jornadas.items():
                for p in partidos:
                    if p["local"] == loc_norm and p["visitante"] == vis_norm:
                        if not p.get("goles_local"):
                            p["hora"] = hora
                            p["estado"] = "Programado"

def procesar_fuente_rss(url, tipo, jornadas):
    """ Lee feeds de noticias/resultados RSS en formato XML como alternativa rápida """
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200: return
        root = ET.fromstring(r.content)
        for item in root.findall('.//item'):
            titulo = item.find('title').text if item.find('title') is not None else ""
            # Ejemplo de parseo de títulos RSS: "Real Madrid 2-1 Barcelona"
            m = re.search(r"([\w\s]+)\s+(\d+)\s*-\s*(\d+)\s+([\w\s]+)", titulo)
            if m:
                loc_web, g_l, g_v, vis_web = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
                loc_norm, vis_norm = normalizar(loc_web, tipo), normalizar(vis_web, tipo)
                if loc_norm and vis_norm:
                    for j_num, partidos in jornadas.items():
                        for p in partidos:
                            if p["local"] == loc_norm and p["visitante"] == vis_norm:
                                if not p.get("goles_local"):
                                    p["goles_local"] = str(g_l)
                                    p["goles_visitante"] = str(g_v)
                                    p["estado"] = "Finalizado"
    except Exception as e:
        print(f"⚠️ Error procesando RSS {url}: {e}")

def reforzar_resultados_y_horas(tipo, jornadas):
    print(f"🚀 Iniciando recopilación multi-fuente para {tipo}...")
    equipos_re = construir_regex_equipos(tipo)
    
    patrones = {
        "goles": re.compile(rf"({equipos_re})\s+(\d+)\s*-\s*(\d+)\s+({equipos_re})", re.I),
        "horas": re.compile(rf"({equipos_re})\s*vs\s*({equipos_re})\s*.*?(\d{{2}}:\d{{2}})", re.I)
    }
    
    # 🌍 RED DE FUENTES 1: Periódicos y diarios deportivos por Web Scraping
    fuentes_web = [
        "mundodeportivo.com",
        "as.com",
        "marca.com",
        "sport.es"
    ] if tipo == "primera" else [
        "mundodeportivo.com",
        "as.com",
        "marca.com"
    ]
    
    for url in fuentes_web:
        print(f"   -> Escaneando Web: {url}")
        procesar_fuente_html(url, tipo, jornadas, patrones)
        
    # 🌍 RED DE FUENTES 2: Feeds RSS alternativos en tiempo real (Soporte de caída)
    fuentes_rss = [
        "eldesmarque.com",
        "resultados-futbol.com"
    ] if tipo == "primera" else [
        "eldesmarque.com"
    ]
    
    for url in fuentes_rss:
        print(f"   -> Escaneando RSS de respaldo: {url}")
        procesar_fuente_rss(url, tipo, jornadas)

def procesar_actualizacion():
    os.makedirs("data", exist_ok=True)
    for tipo in ["primera", "segunda"]:
        ruta_archivo = f"data/partidos_{tipo}.json"
        if os.path.exists(ruta_archivo):
            try:
                with open(ruta_archivo, "r", encoding="utf-8") as f:
                    jornadas = json.load(f)
            except Exception: jornadas = {}
        else: jornadas = {}
            
        reforzar_resultados_y_horas(tipo, jornadas)
        
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            json.dump(jornadas, f, indent=4, ensure_ascii=False)
        print(f"💾 Base de datos multi-fuente consolidada para {tipo}.\n")

if __name__ == "__main__":
    procesar_actualizacion()
