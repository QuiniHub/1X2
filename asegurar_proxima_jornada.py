import json
import re
import unicodedata
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
FUENTE = "https://www.quinielafutbol.info/proximas-jornadas-de-la-quiniela.html"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
}


def reparar_mojibake(texto):
    texto = str(texto or "")
    if not any(marca in texto for marca in ("Ã", "Â", "â", "�")):
        return texto
    try:
        reparado = texto.encode("latin1").decode("utf-8")
        if "�" not in reparado:
            return reparado
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return texto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def normalizar(texto):
    texto = reparar_mojibake(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def descargar_html(url):
    if requests:
        respuesta = requests.get(url, headers=HEADERS, timeout=30)
        respuesta.raise_for_status()
        contenido = respuesta.content
        charset = respuesta.encoding
    else:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=30) as respuesta:
            contenido = respuesta.read()
            charset = respuesta.headers.get_content_charset()

    candidatos = [charset, "utf-8", "cp1252", "latin-1"]
    mejores = []
    for enc in [c for c in candidatos if c]:
        try:
            texto = contenido.decode(enc)
        except UnicodeDecodeError:
            texto = contenido.decode(enc, errors="replace")
        penalizacion = texto.count("�") * 10 + texto.count("Ã") + texto.count("Â")
        mejores.append((penalizacion, texto))
    mejores.sort(key=lambda item: item[0])
    return mejores[0][1]


def html_a_lineas(html):
    if BeautifulSoup:
        texto = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    else:
        texto = re.sub(r"(?is)<(script|style).*?</\\1>", "\n", html)
        texto = re.sub(r"(?i)<br\s*/?>", "\n", texto)
        texto = re.sub(r"(?i)</(p|div|li|tr|td|th|h[1-6]|section|article)>", "\n", texto)
        texto = re.sub(r"(?s)<[^>]+>", " ", texto)
        texto = unescape(texto)
    return [reparar_mojibake(linea.strip()) for linea in texto.splitlines() if linea.strip()]


def fecha_iso(fecha):
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", fecha.strip())
    if not m:
        return fecha
    dia, mes, year = m.groups()
    return f"{year}-{mes}-{dia}"


def parsear_partido(linea):
    linea = reparar_mojibake(re.sub(r"\s+", " ", linea).strip())
    m = re.match(r"^(\d{1,2})\s+(.+?)\s+(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2})$", linea)
    if not m:
        return None
    num, equipos, fecha, hora = m.groups()
    if " - " not in equipos:
        return None
    local, visitante = [reparar_mojibake(x.strip()) for x in equipos.split(" - ", 1)]
    return {
        "num": int(num),
        "local": local,
        "visitante": visitante,
        "fecha": fecha_iso(fecha),
        "hora": hora,
        "resultado": "Pendiente",
        "signo_oficial": "Pendiente",
        "signo_nuestro": "No jugada",
    }


def parsear_jornadas_publicadas(lineas):
    jornadas = []
    actual = None
    for linea in lineas:
        cabecera = re.search(r"JORNADA\s*(?:N[ºo]\s*)?(\d{1,3})\s+(.+)$", linea, re.I)
        if cabecera:
            if actual and len(actual["items"]) >= 15:
                jornadas.append(actual)
            actual = {
                "jornada": int(cabecera.group(1)),
                "fecha_texto": reparar_mojibake(cabecera.group(2).strip()),
                "items": [],
            }
            continue
        if not actual:
            continue
        partido = parsear_partido(linea)
        if partido:
            actual["items"].append(partido)
            if len(actual["items"]) >= 15:
                jornadas.append(actual)
                actual = None
    if actual and len(actual["items"]) >= 15:
        jornadas.append(actual)
    return jornadas


def jornada_a_json(jornada):
    items = sorted(jornada["items"], key=lambda p: p["num"])
    partidos = [p for p in items if p["num"] <= 14]
    pleno = next((p for p in items if p["num"] == 15), None)
    return {
        "jornada": jornada["jornada"],
        "fecha": jornada["fecha_texto"],
        "fuente": FUENTE,
        "estado": "abierta",
        "actualizado_en": datetime.now(timezone.utc).isoformat(),
        "partidos": partidos,
        "pleno15": pleno,
    }


def numeros_existentes():
    nums = []
    for path in JORNADAS.glob("jornada_*.json"):
        m = re.search(r"jornada_(\d+)", path.stem)
        if m:
            nums.append(int(m.group(1)))
    return sorted(nums)


def jornada_cerrada(data):
    partidos = data.get("partidos", [])
    if not partidos:
        return False
    return all(str(p.get("signo_oficial") or "").upper() in {"1", "X", "2"} for p in partidos[:14])


def debe_guardar(jornada_num):
    existentes = numeros_existentes()
    if not existentes:
        return True
    ultimo = max(existentes)
    if jornada_num > ultimo:
        return jornada_cerrada(cargar_json(JORNADAS / f"jornada_{ultimo}.json", {})) or jornada_num == ultimo + 1
    return False


def main():
    lineas = html_a_lineas(descargar_html(FUENTE))
    jornadas = parsear_jornadas_publicadas(lineas)
    guardadas = []
    for jornada in jornadas:
        numero = int(jornada["jornada"])
        path = JORNADAS / f"jornada_{numero}.json"
        if path.exists() or not debe_guardar(numero):
            continue
        data = jornada_a_json(jornada)
        guardar_json(path, data)
        guardadas.append(numero)

    if guardadas:
        print("Jornadas futuras incorporadas: " + ", ".join(map(str, guardadas)))
    else:
        print("No hay jornadas futuras nuevas que incorporar.")


if __name__ == "__main__":
    main()
