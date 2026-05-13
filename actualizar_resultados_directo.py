import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"

FUENTES_DIRECTO = [
    "https://www.quiniela15.com/resultados-quiniela",
    "https://dondeverlo.es/quiniela/directo/",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalizar(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|club|real|de|del|la|el|balompie|futbol)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def candidatos_equipo(nombre):
    n = normalizar(nombre)
    partes = [p for p in n.split() if len(p) > 2]
    candidatos = {n}
    candidatos.update(partes)
    alias = {
        "atletico madrid": ["at madrid", "atletico"],
        "athletic bilbao": ["athletic", "ath club"],
        "athletic": ["ath club"],
        "racing santander": ["r santander", "racing"],
        "real sociedad": ["r sociedad", "sociedad"],
        "rayo vallecano": ["rayo"],
        "real oviedo": ["r oviedo", "oviedo"],
        "deportivo alaves": ["alaves"],
        "sporting gijon": ["sporting"],
        "celtic glasgow": ["celtic"],
        "glasgow rangers": ["rangers"],
    }
    for key, vals in alias.items():
        if key in n:
            candidatos.update(vals)
    return {c for c in candidatos if c}


def contiene_equipo(texto, equipo):
    base = normalizar(texto)
    return any(c in base for c in candidatos_equipo(equipo))


def descargar_fuentes():
    textos = []
    for url in FUENTES_DIRECTO:
        try:
            response = requests.get(url, headers=HEADERS, timeout=25)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            texto = " ".join(soup.get_text(" ").split())
            textos.append(texto)
            print(f"Fuente directa OK: {url}")
        except Exception as exc:
            print(f"No se pudo consultar {url}: {exc}")
    return "\n".join(textos)


def jornada_directo(texto):
    m = re.search(r"jornada\s+(\d{1,3})", texto, re.I)
    return int(m.group(1)) if m else None


def signo_resultado(resultado):
    gl, gv = [int(x) for x in resultado.split("-")]
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def buscar_partido_en_calendario(partido):
    for archivo in (DATA / "calendario_primera.json", DATA / "calendario_segunda.json"):
        data = cargar_json(archivo, {})
        for jornada in data.get("jornadas", []):
            for p_cal in jornada.get("partidos", []):
                if contiene_equipo(p_cal.get("local", ""), partido.get("local", "")) and contiene_equipo(p_cal.get("visitante", ""), partido.get("visitante", "")):
                    return p_cal
    return None


def partido_esta_programado_en_futuro(partido):
    p_cal = buscar_partido_en_calendario(partido)
    if not p_cal:
        return False
    try:
        fecha = datetime.fromisoformat(str(p_cal.get("fecha", ""))).date()
    except ValueError:
        return False
    return fecha > datetime.utcnow().date()


def buscar_resultado_final(texto, partido):
    local = partido.get("local", "")
    visitante = partido.get("visitante", "")
    patrones = [
        r"(?P<a>\d{1,2})\s*[-]\s*(?P<b>\d{1,2})",
        r"(?P<a>\d{1,2})\s+a\s+(?P<b>\d{1,2})",
    ]
    for patron in patrones:
        for match in re.finditer(patron, texto, re.I):
            fragmento = texto[max(0, match.start() - 180): min(len(texto), match.end() + 180)]
            if not (contiene_equipo(fragmento, local) and contiene_equipo(fragmento, visitante)):
                continue
            if re.search(r"\b(descanso|1t|2t|min\.?|minuto|en juego|pend)\b", fragmento, re.I):
                continue
            return f"{int(match.group('a'))}-{int(match.group('b'))}"
    return None


def jornada_activa_desde_archivos(jornada_detectada=None):
    if jornada_detectada:
        path = JORNADAS / f"jornada_{jornada_detectada}.json"
        if path.exists():
            return jornada_detectada
    candidatas = []
    for path in JORNADAS.glob("jornada_*.json"):
        data = cargar_json(path, {})
        numero = data.get("jornada")
        pendientes = sum(1 for p in data.get("partidos", []) if str(p.get("signo_oficial", "")).lower() == "pendiente")
        if pendientes and isinstance(numero, int):
            candidatas.append(numero)
    return max(candidatas) if candidatas else jornada_detectada


def actualizar_jornada_quiniela(texto):
    numero = jornada_activa_desde_archivos(jornada_directo(texto))
    if not numero:
        print("No se detecto jornada activa.")
        return 0, []

    path = JORNADAS / f"jornada_{numero}.json"
    data = cargar_json(path, {})
    if not data:
        print(f"No existe {path}")
        return 0, []

    cambios = 0
    actualizados = []
    for partido in data.get("partidos", []):
        if partido_esta_programado_en_futuro(partido):
            continue
        anterior = partido.get("resultado")
        resultado = buscar_resultado_final(texto, partido)
        if not resultado:
            continue
        signo = signo_resultado(resultado)
        if anterior != resultado or partido.get("signo_oficial") != signo:
            partido["resultado"] = resultado
            partido["signo_oficial"] = signo
            partido["actualizado_en"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            cambios += 1
        actualizados.append(partido)

    pleno = data.get("pleno15") or {}
    if pleno:
        resultado = None if partido_esta_programado_en_futuro(pleno) else buscar_resultado_final(texto, pleno)
        if resultado and pleno.get("resultado") != resultado:
            pleno["resultado"] = resultado
            pleno["signo_oficial"] = resultado
            pleno["actualizado_en"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            cambios += 1

    if cambios:
        data["estado"] = "cerrada" if all(str(p.get("signo_oficial", "")).upper() in ("1", "X", "2") for p in data.get("partidos", [])) else "en_juego"
        guardar_json(path, data)
    print(f"Jornada quiniela {numero}: {cambios} cambios.")
    return cambios, actualizados


def sincronizar_calendario_liga(partidos):
    cambios = 0
    for archivo in (DATA / "calendario_primera.json", DATA / "calendario_segunda.json"):
        data = cargar_json(archivo, {})
        if not data:
            continue
        for jornada in data.get("jornadas", []):
            for p_cal in jornada.get("partidos", []):
                for p_q in partidos:
                    resultado = p_q.get("resultado")
                    if not resultado or resultado == "Pendiente":
                        continue
                    if contiene_equipo(p_cal.get("local", ""), p_q.get("local", "")) and contiene_equipo(p_cal.get("visitante", ""), p_q.get("visitante", "")):
                        if p_cal.get("resultado") != resultado:
                            p_cal["resultado"] = resultado
                            p_cal["estado"] = "Jugado"
                            p_cal["actualizado_en"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
                            cambios += 1
        guardar_json(archivo, data)
    print(f"Calendarios sincronizados desde quiniela: {cambios} cambios.")
    return cambios


def main():
    texto = descargar_fuentes()
    if not texto:
        print("Sin texto de fuentes directas.")
        return
    cambios, partidos = actualizar_jornada_quiniela(texto)
    if partidos:
        cambios += sincronizar_calendario_liga(partidos)
    print(f"Actualizacion directa finalizada: {cambios} cambios.")


if __name__ == "__main__":
    main()
