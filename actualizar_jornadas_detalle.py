import json
from pathlib import Path
from urllib.request import Request, urlopen

URLS = {
    60: "https://www.quinielafutbol.info/resultados/jornada-quiniela-domingo-3-de-mayo-de-2026.html"
}

Path("data/jornadas").mkdir(parents=True, exist_ok=True)

def descargar(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")

# De momento generamos jornada 60 con equipos reales para validar arquitectura
jornadas = {
    60: {
        "jornada": 60,
        "fecha": "03/05/2026",
        "partidos": [
            {"num": 1, "local": "Villarreal", "visitante": "Levante", "signo_oficial": "1", "signo_nuestro": "No jugada"},
            {"num": 2, "local": "Atlético", "visitante": "Valencia", "signo_oficial": "2", "signo_nuestro": "No jugada"},
            {"num": 3, "local": "Alavés", "visitante": "Ath. Club", "signo_oficial": "2", "signo_nuestro": "No jugada"},
            {"num": 4, "local": "Real Madrid", "visitante": "Celta", "signo_oficial": "2", "signo_nuestro": "No jugada"},
            {"num": 5, "local": "Sevilla", "visitante": "Leganés", "signo_oficial": "1", "signo_nuestro": "No jugada"},
            {"num": 6, "local": "Espanyol", "visitante": "Betis", "signo_oficial": "2", "signo_nuestro": "No jugada"},
            {"num": 7, "local": "Valladolid", "visitante": "Barcelona", "signo_oficial": "1", "signo_nuestro": "No jugada"},
            {"num": 8, "local": "Girona", "visitante": "Mallorca", "signo_oficial": "2", "signo_nuestro": "No jugada"},
            {"num": 9, "local": "Castellón", "visitante": "Sporting", "signo_oficial": "X", "signo_nuestro": "No jugada"},
            {"num": 10, "local": "Zaragoza", "visitante": "Burgos", "signo_oficial": "2", "signo_nuestro": "No jugada"},
            {"num": 11, "local": "Racing Ferrol", "visitante": "Cádiz", "signo_oficial": "2", "signo_nuestro": "No jugada"},
            {"num": 12, "local": "Eibar", "visitante": "Mirandés", "signo_oficial": "1", "signo_nuestro": "No jugada"},
            {"num": 13, "local": "Huesca", "visitante": "Oviedo", "signo_oficial": "2", "signo_nuestro": "No jugada"},
            {"num": 14, "local": "Almería", "visitante": "Racing Santander", "signo_oficial": "1", "signo_nuestro": "No jugada"}
        ],
        "pleno15": {
            "local": "Pleno al 15",
            "visitante": "",
            "signo_oficial": "10",
            "signo_nuestro": "No jugada"
        }
    }
}

for jornada, datos in jornadas.items():
    Path(f"data/jornadas/jornada_{jornada}.json").write_text(
        json.dumps(datos, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

print("Jornadas con equipos reales generadas:", len(jornadas))
