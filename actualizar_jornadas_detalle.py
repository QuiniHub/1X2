import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
FUENTE_PROXIMAS = "https://www.quinielafutbol.info/proximas-jornadas-de-la-quiniela.html"

CANONICOS = {
    "alaves": "Deportivo Alaves",
    "rayo": "Rayo Vallecano de Madrid",
    "betis": "Real Betis Balompie",
    "levante": "Levante UD",
    "celta": "RC Celta de Vigo",
    "sevilla": "Sevilla FC",
    "espanyol": "RCD Espanyol de Barcelona",
    "r sociedad": "Real Sociedad de Futbol",
    "getafe": "Getafe CF",
    "osasuna": "CA Osasuna",
    "mallorca": "RCD Mallorca",
    "r oviedo": "Real Oviedo",
    "villarreal": "Villarreal CF",
    "at madrid": "Club Atletico de Madrid",
    "valencia": "Valencia CF",
    "barcelona": "FC Barcelona",
    "girona": "Girona FC",
    "elche": "Elche CF",
    "malaga": "Malaga CF",
    "racing s": "Real Racing Club de Santander",
    "andorra fc": "FC Andorra",
    "ceuta": "AD Ceuta FC",
    "huesca": "SD Huesca",
    "castellon": "CD Castellon",
    "eibar": "SD Eibar",
    "cordoba": "Cordoba CF",
    "sporting": "Real Sporting de Gijon",
    "almeria": "UD Almeria",
    "r madrid": "Real Madrid CF",
    "ath club": "Athletic Club",
}


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalizar(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def canonico(nombre):
    clave = normalizar(nombre)
    return CANONICOS.get(clave, nombre.strip())


def descargar_lineas():
    respuesta = requests.get(
        FUENTE_PROXIMAS,
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    )
    respuesta.raise_for_status()
    soup = BeautifulSoup(respuesta.text, "html.parser")
    return [linea.strip() for linea in soup.get_text("\n", strip=True).splitlines() if linea.strip()]


def fecha_iso(fecha):
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", fecha.strip())
    if not m:
        return fecha
    dia, mes, year = m.groups()
    return f"{year}-{mes}-{dia}"


def parsear_partido(linea):
    m = re.match(r"^(\d{1,2})\s+(.+?)\s+(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2})$", linea)
    if not m:
        return None
    num, equipos, fecha, hora = m.groups()
    if " - " not in equipos:
        return None
    local, visitante = equipos.split(" - ", 1)
    return {
        "num": int(num),
        "local": canonico(local),
        "visitante": canonico(visitante),
        "fecha": fecha_iso(fecha),
        "hora": hora,
        "resultado": "Pendiente",
        "signo_oficial": "Pendiente",
        "signo_nuestro": "No jugada",
    }


def extraer_jornadas():
    lineas = descargar_lineas()
    jornadas = []
    actual = None

    for linea in lineas:
        cabecera = re.search(r"JORNADA\s*(?:N[ºO]\s*)?(\d{1,3})\s+(.+)$", linea, re.I)
        if cabecera:
            if actual and len(actual["items"]) >= 15:
                jornadas.append(actual)
            actual = {
                "jornada": int(cabecera.group(1)),
                "fecha_texto": cabecera.group(2).strip(),
                "items": [],
            }
            continue

        if actual:
            partido = parsear_partido(linea)
            if partido:
                actual["items"].append(partido)
                if len(actual["items"]) >= 15:
                    jornadas.append(actual)
                    actual = None

    if actual and len(actual["items"]) >= 15:
        jornadas.append(actual)

    return jornadas


def fusionar_con_existente(nuevo, existente):
    if not existente:
        return nuevo
    existentes_por_num = {
        int(p.get("num", 0)): p
        for p in existente.get("partidos", [])
        if str(p.get("num", "")).isdigit()
    }
    partidos = []
    for partido in nuevo.get("partidos", []):
        anterior = existentes_por_num.get(int(partido.get("num", 0)), {})
        fusionado = dict(partido)
        for campo in ("resultado", "signo_oficial", "signo_nuestro", "actualizado_en"):
            valor = anterior.get(campo)
            if valor and str(valor).lower() not in {"pendiente", "no jugada"}:
                fusionado[campo] = valor
        partidos.append(fusionado)
    nuevo["partidos"] = partidos

    pleno_anterior = existente.get("pleno15") or {}
    pleno = dict(nuevo.get("pleno15") or {})
    for campo in ("resultado", "signo_oficial", "signo_nuestro", "actualizado_en"):
        valor = pleno_anterior.get(campo)
        if valor and str(valor).lower() not in {"pendiente", "no jugada"}:
            pleno[campo] = valor
    nuevo["pleno15"] = pleno
    return nuevo


def jornada_a_json(jornada):
    items = sorted(jornada["items"], key=lambda p: p["num"])
    partidos = [p for p in items if p["num"] <= 14]
    pleno = next((p for p in items if p["num"] == 15), None)
    return {
        "jornada": jornada["jornada"],
        "fecha": jornada["fecha_texto"],
        "fuente": FUENTE_PROXIMAS,
        "estado": "abierta",
        "actualizado_en": datetime.now(timezone.utc).isoformat(),
        "partidos": partidos,
        "pleno15": pleno,
    }


def actualizar_legado(jornada_json):
    primera = []
    segunda = []
    for partido in jornada_json.get("partidos", []):
        item = {
            "local": partido.get("local"),
            "visitante": partido.get("visitante"),
            "fecha": partido.get("fecha"),
            "hora": partido.get("hora"),
            "estado": "Programado",
        }
        if int(partido.get("num", 0)) <= 9:
            primera.append(item)
        else:
            segunda.append(item)
    guardar_json(DATA / "partidos_primera.json", primera)
    guardar_json(DATA / "partidos_segunda.json", segunda)


def main():
    jornadas = extraer_jornadas()
    if not jornadas:
        raise SystemExit("No se encontraron proximas jornadas de La Quiniela.")

    creadas = []
    for jornada in jornadas:
        data = jornada_a_json(jornada)
        path = JORNADAS / f"jornada_{data['jornada']}.json"
        data = fusionar_con_existente(data, cargar_json(path, {}))
        guardar_json(path, data)
        actualizar_legado(data)
        creadas.append(data["jornada"])

    print(f"Jornadas actualizadas automaticamente: {', '.join(map(str, creadas))}")


if __name__ == "__main__":
    main()
