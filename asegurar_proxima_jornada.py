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


def ultima_jornada_por_fecha():
    """Ultima jornada guardada por FECHA real (dict de cronologia_jornadas) o
    None. Nunca por numero: data/jornadas mezcla J1-J27 de 26/27 con J28-J76
    de 25/26 y max(numero) da siempre la 76 (auditoria 26/11, 142 y 168)."""
    import cronologia_jornadas

    con_fecha = [j for j in cronologia_jornadas.indice_jornadas(JORNADAS) if j["fecha"] is not None]
    return con_fecha[-1] if con_fecha else None


def _fecha_y_temporada(data, numero):
    import cronologia_jornadas

    fecha = cronologia_jornadas.fecha_real_jornada(data) if isinstance(data, dict) else None
    return fecha, cronologia_jornadas.temporada_de_fecha(fecha, numero) if fecha else None


def fichero_de_otra_temporada(numero, data_nueva):
    """True si jornada_{numero}.json ya existe pero es de una temporada
    ANTERIOR a la jornada publicada (mismo numero, otra jornada real)."""
    existente = cargar_json(JORNADAS / f"jornada_{numero}.json", {})
    fecha_vieja, temp_vieja = _fecha_y_temporada(existente, numero)
    fecha_nueva, temp_nueva = _fecha_y_temporada(data_nueva, numero)
    if not fecha_nueva or not fecha_vieja or not temp_vieja or not temp_nueva:
        return False
    return temp_vieja != temp_nueva and fecha_vieja < fecha_nueva


def archivar_jornada_de_otra_temporada(path, numero):
    """Antes de sobrescribir un jornada_N.json de una temporada anterior con
    la jornada N de la nueva, se copia a data/temporadas/<temporada>/jornadas/
    (no se pisa un archivo ya guardado). Devuelve la ruta o None."""
    path = Path(path)
    if not path.exists():
        return None
    _fecha, temporada = _fecha_y_temporada(cargar_json(path, {}), numero)
    if not temporada:
        return None
    destino = DATA / "temporadas" / temporada / "jornadas" / path.name
    if destino.exists():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(path.read_bytes())
    print(f"Jornada {numero} de {temporada} archivada antes de sobrescribirla.")
    return destino


def debe_guardar(jornada_num, data_nueva=None):
    """Se guarda si es posterior POR FECHA a la ultima jornada conocida y es la
    siguiente de la temporada (o la ultima ya esta cerrada)."""
    if not numeros_existentes():
        return True
    ultima = ultima_jornada_por_fecha()
    if ultima is None:
        return False
    fecha_nueva, temp_nueva = _fecha_y_temporada(data_nueva, jornada_num)
    if fecha_nueva is not None and fecha_nueva <= ultima["fecha"]:
        return False
    if temp_nueva and ultima.get("temporada") and temp_nueva != ultima["temporada"]:
        # Temporada nueva: la numeracion se reinicia, vale cualquier numero bajo.
        return fecha_nueva > ultima["fecha"]
    if jornada_num == ultima["numero"] + 1:
        return True
    return jornada_num > ultima["numero"] and bool(ultima.get("cerrada"))


def usar_cache_si_falla(error):
    existentes = numeros_existentes()
    if existentes:
        ultima = ultima_jornada_por_fecha()
        etiqueta = f"jornada {ultima['numero']} ({ultima['fecha']})" if ultima else "sin fecha conocida"
        print(
            "AVISO: no se pudo descargar la proxima jornada desde la fuente externa; "
            f"se mantiene cache local hasta {etiqueta}. Error: {error}"
        )
        return True
    print(f"AVISO: no se pudo descargar la proxima jornada y no hay cache local. Error: {error}")
    return True


def main():
    try:
        html = descargar_html(FUENTE)
    except Exception as exc:
        usar_cache_si_falla(exc)
        return

    lineas = html_a_lineas(html)
    jornadas = parsear_jornadas_publicadas(lineas)
    guardadas = []
    for jornada in jornadas:
        numero = int(jornada["jornada"])
        path = JORNADAS / f"jornada_{numero}.json"
        data = jornada_a_json(jornada)
        # Un fichero con el mismo numero solo bloquea si es de ESTA temporada.
        if path.exists() and not fichero_de_otra_temporada(numero, data):
            continue
        if not debe_guardar(numero, data):
            continue
        if path.exists():
            archivar_jornada_de_otra_temporada(path, numero)
        guardar_json(path, data)
        guardadas.append(numero)

    if guardadas:
        print("Jornadas futuras incorporadas: " + ", ".join(map(str, guardadas)))
    else:
        print("No hay jornadas futuras nuevas que incorporar.")


if __name__ == "__main__":
    main()
