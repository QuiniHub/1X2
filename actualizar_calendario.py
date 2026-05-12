import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


RESULTADOS_VERIFICADOS = {
    "primera": {
        35: {
            ("Levante UD", "CA Osasuna"): "3-2",
            ("Elche CF", "Deportivo Alaves"): "1-1",
            ("Sevilla FC", "RCD Espanyol de Barcelona"): "2-1",
            ("Club Atletico de Madrid", "RC Celta de Vigo"): "0-1",
            ("Real Sociedad de Futbol", "Real Betis Balompie"): "2-2",
            ("RCD Mallorca", "Villarreal CF"): "1-1",
            ("Athletic Club", "Valencia CF"): "0-1",
            ("Real Oviedo", "Getafe CF"): "0-0",
            ("FC Barcelona", "Real Madrid CF"): "2-0",
            ("Rayo Vallecano de Madrid", "Girona FC"): "1-1",
        }
    },
    "segunda": {
        39: {
            ("Albacete", "Cultural Leonesa"): "2-1",
            ("Cadiz CF", "Deportivo La Coruna"): "0-1",
            ("Cordoba CF", "Granada CF"): "1-0",
            ("SD Huesca", "Real Sociedad B"): "1-2",
            ("CD Leganes", "Racing Santander"): "1-2",
            ("Malaga CF", "Sporting Gijon"): "2-1",
            ("Real Valladolid", "Real Zaragoza"): "2-0",
            ("FC Andorra", "UD Las Palmas"): "5-1",
            ("AD Ceuta FC", "CD Castellon"): "1-1",
            ("CD Mirandes", "SD Eibar"): "0-1",
            ("Burgos CF", "UD Almeria"): "0-0",
        }
    },
}


def normalizar(texto):
    reemplazos = str.maketrans(
        "áéíóúüñÁÉÍÓÚÜÑ",
        "aeiouunAEIOUUN",
    )
    texto = str(texto or "").translate(reemplazos)
    return " ".join(texto.split())


def cargar_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def actualizar_calendario_liga(tipo):
    path = DATA / f"calendario_{tipo}.json"
    data = cargar_json(path)
    actualizados = 0

    for jornada in data.get("jornadas", []):
        resultados_jornada = RESULTADOS_VERIFICADOS.get(tipo, {}).get(jornada.get("jornada"), {})
        if not resultados_jornada:
            continue

        indice = {
            (normalizar(local), normalizar(visitante)): resultado
            for (local, visitante), resultado in resultados_jornada.items()
        }

        for partido in jornada.get("partidos", []):
            clave = (normalizar(partido.get("local")), normalizar(partido.get("visitante")))
            resultado = indice.get(clave)
            if resultado:
                partido["resultado"] = resultado
                partido["estado"] = "Jugado"
                actualizados += 1

    guardar_json(path, data)
    return actualizados


def ejecutar_calendario():
    total = 0
    for tipo in ("primera", "segunda"):
        actualizados = actualizar_calendario_liga(tipo)
        total += actualizados
        print(f"{tipo}: {actualizados} marcadores consolidados.")
    print(f"Calendarios actualizados: {total} marcadores verificados.")


if __name__ == "__main__":
    ejecutar_calendario()
