import os, re, requests, json
from bs4 import BeautifulSoup

MAPEO_EQUIPOS = {
    "primera": {
        "barcelona": "Barcelona", "real madrid": "Real Madrid", "atletico": "Ath Madrid",
        "atleti": "Ath Madrid", "athletic": "Ath Bilbao", "real sociedad": "Sociedad", 
        "betis": "Betis", "villarreal": "Villarreal", "valencia": "Valencia", 
        "sevilla": "Sevilla", "osasuna": "Osasuna", "girona": "Girona", 
        "rayo": "Vallecano", "celta": "Celta", "getafe": "Getafe", 
        "mallorca": "Mallorca", "alaves": "Alaves", "espanyol": "Espanol",
        "elche": "Elche", "oviedo": "Oviedo", "levante": "Levante"
    },
    "segunda": {
        "santander": "Santander", "racing": "Santander", "almeria": "Almeria",
        "coruña": "La Coruna", "deportivo": "La Coruna", "las palmas": "Las Palmas",
        "castellon": "Castellon", "malaga": "Malaga", "burgos": "Burgos",
        "eibar": "Eibar", "cordoba": "Cordoba", "andorra": "Andorra",
        "ceuta": "Ceuta", "gijon": "Sp Gijon", "sporting": "Sp Gijon",
        "albacete": "Albacete", "granada": "Granada", "valladolid": "Valladolid",
        "leganes": "Leganes", "sociedad b": "Sociedad B", "cadiz": "Cadiz",
        "huesca": "Huesca", "mirandes": "Mirandes", "zaragoza": "Zaragoza",
        "leonesa": "Cultural Leonesa", "cultural": "Cultural Leonesa"
    }
}

ALIAS_EXTRA = {
    "primera": ["Barcelona", "Real Madrid", "Atletico", "Atleti", "Athletic", "Real Sociedad", "Betis", "Villarreal", "Valencia", "Sevilla", "Osasuna", "Girona", "Rayo", "Celta", "Getafe", "Mallorca", "Alaves", "Espanyol", "Elche", "Oviedo", "Levante"],
    "segunda": ["Santander", "Racing", "Almeria", "La Coruna", "Deportivo", "Las Palmas", "Castellon", "Malaga", "Burgos", "Eibar", "Cordoba", "Andorra", "Ceuta", "Sporting", "Gijon", "Albacete", "Granada", "Valladolid", "Leganes", "Sociedad B", "Cadiz", "Huesca", "Mirandes", "Zaragoza", "Leonesa", "Cultural"]
}

def normalizar(txt, tipo):
    txt = txt.lower().strip()
    for p in ["cf", "sad", "ud", "rc", "rcd", "club", "de futbol", "balompie", "de madrid", "de vigo", "de barcelona", "ca", "real", "sd", "ad"]:
        txt = txt.replace(p, "")
    txt = txt.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").strip()
    for clave, valor in MAPEO_EQUIPOS[tipo].items():
        if clave in txt: return valor
    return None

def raspar_contexto():
    noticias = []
    for url in ["https://marca.com", "https://futbolfantasy.com"]:
        try:
            r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla"})
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                for tag in soup.find_all(['h2', 'h3'])[:5]:
                    if len(tag.text.strip()) > 15: noticias.append(tag.text.strip())
        except: pass
    with open("data/contexto_ia.json", "w", encoding="utf-8") as f: json.dump({"noticias": noticias}, f, indent=4, ensure_ascii=False)

def reforzar_partidos(tipo, partidos):
    regex = re.compile(rf"({'|'.join([re.escape(x) for x in ALIAS_EXTRA[tipo]])})\s+(\d+)\s*-\s*(\d+)\s+({'|'.join([re.escape(x) for x in ALIAS_EXTRA[tipo]])})", re.I)
    for url in ["https://mundodeportivo.com", "https://as.com"]:
        try:
            r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla"})
            for m in regex.finditer(r.text):
                l_web, g_l, g_v, v_web = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
                l_norm, v_norm = normalizar(l_web, tipo), normalizar(v_web, tipo)
                for p in partidos:
                    if normalizar(p["local"], tipo) == l_norm and normalizar(p["visitante"], tipo) == v_norm:
                        p.update({"goles_local": str(g_l), "Goles_Local": str(g_l), "goles_visitante": str(g_v), "Goles_Visitante": str(g_v), "estado": "Finalizado"})
        except: pass

def ejecutar():
    os.makedirs("data", exist_ok=True)
    raspar_contexto()
    for tipo in ["primera", "segunda"]:
        ruta = f"data/partidos_{tipo}.json"
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f: partidos = json.load(f)
            reforzar_partidos(tipo, partidos)
            with open(ruta, "w", encoding="utf-8") as f: json.dump(partidos, f, indent=4, ensure_ascii=False)

if __name__ == "__main__": ejecutar()

