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
FUENTE_PROXIMAS = "https://www.quinielafutbol.info/proximas-jornadas-de-la-quiniela.html"
FUENTE_LIBERTAD = "https://www.libertaddigital.com/deportes/liga/2025-2026/quiniela/{jornada}.html"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

CANONICOS = {
    "alaves": "Deportivo Alaves",
    "rayo": "Rayo Vallecano de Madrid",
    "rayo vallecano": "Rayo Vallecano de Madrid",
    "rayo vallecano de madrid": "Rayo Vallecano de Madrid",
    "betis": "Real Betis Balompie",
    "real betis": "Real Betis Balompie",
    "real betis balompie": "Real Betis Balompie",
    "levante": "Levante UD",
    "levante ud": "Levante UD",
    "celta": "RC Celta de Vigo",
    "rc celta": "RC Celta de Vigo",
    "rc celta de vigo": "RC Celta de Vigo",
    "sevilla": "Sevilla FC",
    "sevilla fc": "Sevilla FC",
    "espanyol": "RCD Espanyol de Barcelona",
    "rcd espanyol": "RCD Espanyol de Barcelona",
    "rcd espanyol de barcelona": "RCD Espanyol de Barcelona",
    "r sociedad": "Real Sociedad de Futbol",
    "real sociedad": "Real Sociedad de Futbol",
    "real sociedad de futbol": "Real Sociedad de Futbol",
    "getafe": "Getafe CF",
    "getafe cf": "Getafe CF",
    "osasuna": "CA Osasuna",
    "ca osasuna": "CA Osasuna",
    "mallorca": "RCD Mallorca",
    "rcd mallorca": "RCD Mallorca",
    "r oviedo": "Real Oviedo",
    "oviedo": "Real Oviedo",
    "real oviedo": "Real Oviedo",
    "villarreal": "Villarreal CF",
    "villarreal cf": "Villarreal CF",
    "atletico": "Club Atletico de Madrid",
    "atletico de madrid": "Club Atletico de Madrid",
    "at madrid": "Club Atletico de Madrid",
    "club atletico de madrid": "Club Atletico de Madrid",
    "valencia": "Valencia CF",
    "valencia cf": "Valencia CF",
    "barcelona": "FC Barcelona",
    "fc barcelona": "FC Barcelona",
    "girona": "Girona FC",
    "girona fc": "Girona FC",
    "elche": "Elche CF",
    "elche cf": "Elche CF",
    "malaga": "Malaga CF",
    "malaga cf": "Malaga CF",
    "racing": "Real Racing Club de Santander",
    "racing s": "Real Racing Club de Santander",
    "racing de santander": "Real Racing Club de Santander",
    "racing santander": "Real Racing Club de Santander",
    "real racing club de santander": "Real Racing Club de Santander",
    "andorra fc": "FC Andorra",
    "andorra": "FC Andorra",
    "fc andorra": "FC Andorra",
    "ceuta": "AD Ceuta FC",
    "ad ceuta": "AD Ceuta FC",
    "ad ceuta fc": "AD Ceuta FC",
    "huesca": "SD Huesca",
    "sd huesca": "SD Huesca",
    "castellon": "CD Castellon",
    "cd castellon": "CD Castellon",
    "eibar": "SD Eibar",
    "sd eibar": "SD Eibar",
    "cordoba": "Cordoba CF",
    "cordoba cf": "Cordoba CF",
    "sporting": "Real Sporting de Gijon",
    "sporting de gijon": "Real Sporting de Gijon",
    "real sporting": "Real Sporting de Gijon",
    "real sporting de gijon": "Real Sporting de Gijon",
    "almeria": "UD Almeria",
    "ud almeria": "UD Almeria",
    "r madrid": "Real Madrid CF",
    "real madrid": "Real Madrid CF",
    "real madrid cf": "Real Madrid CF",
    "ath club": "Athletic Club",
    "athletic": "Athletic Club",
    "athletic club": "Athletic Club",
    "athletic de bilbao": "Athletic Club",
    "deportivo": "RC Deportivo de La Coruna",
    "deportivo la coruna": "RC Deportivo de La Coruna",
    "deportivo de la coruna": "RC Deportivo de La Coruna",
    "rc deportivo de la coruna": "RC Deportivo de La Coruna",
    "depor": "RC Deportivo de La Coruna",
    "las palmas": "UD Las Palmas",
    "ud las palmas": "UD Las Palmas",
    "leganes": "CD Leganes",
    "cd leganes": "CD Leganes",
    "cadiz": "Cadiz CF",
    "cadiz cf": "Cadiz CF",
    "mirandes": "CD Mirandes",
    "cd mirandes": "CD Mirandes",
    "burgos": "Burgos CF",
    "burgos cf": "Burgos CF",
    "real sociedad b": "Real Sociedad B",
    "cultural leonesa": "Cultural Leonesa",
    "zaragoza": "Real Zaragoza",
    "real zaragoza": "Real Zaragoza",
    "valladolid": "Real Valladolid CF",
    "real valladolid": "Real Valladolid CF",
    "real valladolid cf": "Real Valladolid CF",
    "granada": "Granada CF",
    "granada cf": "Granada CF",
    "albacete": "Albacete Balompie",
    "albacete balompie": "Albacete Balompie",
    "ee uu": "EEUU",
    "eeuu": "EEUU",
    "estados unidos": "EEUU",
    "usa": "EEUU",
    "united states": "EEUU",
    "mexico": "Mexico",
    "australia": "Australia",
    "japon": "Japon",
    "islandia": "Islandia",
    "alemania": "Alemania",
    "finlandia": "Finlandia",
    "holanda": "Países Bajos",
    "paises bajos": "Países Bajos",
    "curaçao": "Curazao",
    "curacao": "Curazao",
    "curazao": "Curazao",
    "costa de marfil": "Costa Marfil",
    "costa marfil": "Costa Marfil",
    "paris saint germain": "Paris Saint-Germain",
    "psg": "Paris Saint-Germain",
    "arsenal": "Arsenal",
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


def descargar_html(url):
    def decodificar(contenido, charset=None):
        candidatos = []
        if charset:
            candidatos.append(charset)
        candidatos.extend(["utf-8", "cp1252", "latin-1"])
        mejores = []
        for enc in dict.fromkeys(candidatos):
            try:
                texto = contenido.decode(enc)
            except UnicodeDecodeError:
                texto = contenido.decode(enc, errors="replace")
            penalizacion = texto.count("\ufffd") * 10 + texto.count("Ã") + texto.count("Â")
            mejores.append((penalizacion, texto))
        mejores.sort(key=lambda item: item[0])
        return mejores[0][1]

    if requests:
        respuesta = requests.get(
            url,
            timeout=30,
            headers=HEADERS,
        )
        respuesta.raise_for_status()
        return decodificar(respuesta.content, respuesta.encoding)

    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as respuesta:
        charset = respuesta.headers.get_content_charset()
        return decodificar(respuesta.read(), charset)


def html_a_lineas(html):
    if BeautifulSoup:
        texto = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    else:
        texto = re.sub(r"(?is)<(script|style).*?</\1>", "\n", html)
        texto = re.sub(r"(?i)<br\s*/?>", "\n", texto)
        texto = re.sub(r"(?i)</(p|div|li|tr|td|th|h[1-6]|section|article)>", "\n", texto)
        texto = re.sub(r"(?s)<[^>]+>", " ", texto)
        texto = unescape(texto)
    return [linea.strip() for linea in texto.splitlines() if linea.strip()]


def descargar_lineas():
    return html_a_lineas(descargar_html(FUENTE_PROXIMAS))


def alias_equipos():
    alias = {normalizar(k): v for k, v in CANONICOS.items()}
    for valor in set(CANONICOS.values()):
        alias.setdefault(normalizar(valor), valor)
    return alias


def separar_equipos_sin_guion(texto):
    texto_norm = normalizar(texto)
    alias = alias_equipos()
    claves = sorted(alias, key=len, reverse=True)
    for local_key in claves:
        if not texto_norm.startswith(local_key + " "):
            continue
        resto = texto_norm[len(local_key):].strip()
        if resto in alias:
            return alias[local_key], alias[resto]
    return None


def parsear_partido_libertad(linea):
    limpia = re.sub(r"\s+", " ", linea).strip()
    m = re.match(r"^(\d{1,2})\s+(.+?)\s+1\s+X\s+2$", limpia)
    if not m:
        return None
    num, equipos = m.groups()
    separados = separar_equipos_sin_guion(equipos)
    if not separados:
        return None
    local, visitante = separados
    return {
        "num": int(num),
        "local": local,
        "visitante": visitante,
        "fecha": "",
        "hora": "--:--",
        "resultado": "Pendiente",
        "signo_oficial": "Pendiente",
        "signo_nuestro": "No jugada",
    }


def extraer_fecha_libertad(lineas):
    meses = {
        "enero": "01",
        "febrero": "02",
        "marzo": "03",
        "abril": "04",
        "mayo": "05",
        "junio": "06",
        "julio": "07",
        "agosto": "08",
        "septiembre": "09",
        "octubre": "10",
        "noviembre": "11",
        "diciembre": "12",
    }
    for linea in lineas:
        m = re.match(r"^(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)\s+de\s+(\d{4})", linea)
        if not m:
            continue
        dia, mes, year = m.groups()
        mes_num = meses.get(normalizar(mes))
        if mes_num:
            return f"{year}-{mes_num}-{int(dia):02d}"
    return "Pendiente"


def parsear_nombre_pleno_libertad(linea):
    limpia = re.sub(r"\s+", " ", linea).strip()
    limpia = re.sub(r"^Pleno\s+al\s+15\s+", "", limpia, flags=re.I)
    limpia = re.sub(r"\s+0\s+1\s+2\s+M$", "", limpia)
    return canonico(limpia) if limpia else ""


def extraer_partidos_libertad_tabla(lineas, fecha):
    items = []
    i = 0
    while i < len(lineas):
        if not re.fullmatch(r"\d{1,2}", lineas[i] or ""):
            i += 1
            continue

        num = int(lineas[i])
        if not 1 <= num <= 14:
            i += 1
            continue

        if i + 5 >= len(lineas):
            break

        local = lineas[i + 1]
        visitante = lineas[i + 2]
        marca = [lineas[i + 3], lineas[i + 4], lineas[i + 5]]
        if marca != ["1", "X", "2"]:
            i += 1
            continue

        items.append({
            "num": num,
            "local": canonico(local),
            "visitante": canonico(visitante),
            "fecha": fecha,
            "hora": "--:--",
            "resultado": "Pendiente",
            "signo_oficial": "Pendiente",
            "signo_nuestro": "No jugada",
        })
        i += 6
    return items


def extraer_pleno_libertad_tabla(lineas):
    for i, linea in enumerate(lineas):
        if not re.match(r"^Pleno\s+al\s+15\b", linea, re.I):
            continue
        if i + 6 >= len(lineas):
            return None
        local = parsear_nombre_pleno_libertad(lineas[i + 1])
        visitante = parsear_nombre_pleno_libertad(lineas[i + 6])
        if local and visitante:
            return {
                "num": 15,
                "local": local,
                "visitante": visitante,
                "fecha": "",
                "hora": "--:--",
                "resultado": "Pendiente",
                "signo_oficial": "Pendiente",
                "signo_nuestro": "No jugada",
            }
    return None


def extraer_jornada_libertad(numero):
    url = FUENTE_LIBERTAD.format(jornada=numero)
    lineas = html_a_lineas(descargar_html(url))
    if not any(f"Jornada {numero}" in linea for linea in lineas):
        return None

    fecha = extraer_fecha_libertad(lineas)
    items = extraer_partidos_libertad_tabla(lineas, fecha)
    pleno_tabla = extraer_pleno_libertad_tabla(lineas)
    if pleno_tabla:
        pleno_tabla["fecha"] = fecha
        items.append(pleno_tabla)

    pleno_local = None
    if len([p for p in items if p["num"] <= 14]) < 14:
        items = []
        for linea in lineas:
            partido = parsear_partido_libertad(linea)
            if partido and 1 <= partido["num"] <= 14:
                partido["fecha"] = fecha
                items.append(partido)
                continue
            if re.match(r"^Pleno\s+al\s+15\b", linea, re.I):
                pleno_local = parsear_nombre_pleno_libertad(linea)
                continue
            if pleno_local and len(items) >= 14:
                pleno_visitante = parsear_nombre_pleno_libertad(linea)
                if pleno_visitante:
                    items.append({
                        "num": 15,
                        "local": pleno_local,
                        "visitante": pleno_visitante,
                        "fecha": fecha,
                        "hora": "--:--",
                        "resultado": "Pendiente",
                        "signo_oficial": "Pendiente",
                        "signo_nuestro": "No jugada",
                    })
                    break

    if len([p for p in items if p["num"] <= 14]) < 14:
        return None
    return {
        "jornada": numero,
        "fecha_texto": fecha,
        "fuente": url,
        "items": items,
    }


def jornadas_existentes():
    numeros = []
    for path in JORNADAS.glob("jornada_*.json"):
        m = re.search(r"jornada_(\d+)", path.stem)
        if m:
            numeros.append(int(m.group(1)))
    return sorted(numeros)


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


def es_placeholder_equipo(nombre):
    texto = normalizar(nombre)
    return (
        not texto
        or texto == "pendiente"
        or "hypermotion" in texto
        or re.search(r"\bf[12]\b", texto) is not None
        or "por determinar" in texto
    )


def extraer_jornadas():
    lineas = descargar_lineas()
    jornadas = []
    actual = None

    for linea in lineas:
        cabecera = re.search(r"JORNADA[^0-9]{0,30}(\d{1,3})\s+(.+)$", linea, re.I)
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
        if es_placeholder_equipo(fusionado.get("local")) and not es_placeholder_equipo(anterior.get("local")):
            fusionado["local"] = anterior.get("local")
            fusionado["fuente_equipos"] = anterior.get("fuente_equipos", fusionado.get("fuente_equipos", "jornada_previa_resuelta"))
        if es_placeholder_equipo(fusionado.get("visitante")) and not es_placeholder_equipo(anterior.get("visitante")):
            fusionado["visitante"] = anterior.get("visitante")
            fusionado["fuente_equipos"] = anterior.get("fuente_equipos", fusionado.get("fuente_equipos", "jornada_previa_resuelta"))
        for campo in ("resultado", "signo_oficial", "signo_nuestro", "actualizado_en"):
            valor = anterior.get(campo)
            if valor and str(valor).lower() not in {"pendiente", "no jugada"}:
                fusionado[campo] = valor
        partidos.append(fusionado)
    nuevo["partidos"] = partidos

    pleno_anterior = existente.get("pleno15") or {}
    pleno = dict(nuevo.get("pleno15") or {})
    if es_placeholder_equipo(pleno.get("local")) and not es_placeholder_equipo(pleno_anterior.get("local")):
        pleno["local"] = pleno_anterior.get("local")
        pleno["fuente_equipos"] = pleno_anterior.get("fuente_equipos", pleno.get("fuente_equipos", "jornada_previa_resuelta"))
    if es_placeholder_equipo(pleno.get("visitante")) and not es_placeholder_equipo(pleno_anterior.get("visitante")):
        pleno["visitante"] = pleno_anterior.get("visitante")
        pleno["fuente_equipos"] = pleno_anterior.get("fuente_equipos", pleno.get("fuente_equipos", "jornada_previa_resuelta"))
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
        "fuente": jornada.get("fuente", FUENTE_PROXIMAS),
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
    try:
        jornadas = extraer_jornadas()
    except Exception as exc:
        print(f"No se pudo leer la fuente de proximas jornadas: {exc}")
        jornadas = []

    existentes_nums = jornadas_existentes()
    proxima = (max(existentes_nums) + 1) if existentes_nums else 1
    vistas = {j["jornada"] for j in jornadas}
    for numero in range(proxima, proxima + 3):
        if numero in vistas:
            continue
        try:
            respaldo = extraer_jornada_libertad(numero)
        except Exception as exc:
            print(f"No se pudo leer respaldo Libertad Digital jornada {numero}: {exc}")
            respaldo = None
        if respaldo:
            jornadas.append(respaldo)
            vistas.add(numero)
            print(f"Jornada {numero} incorporada desde respaldo Libertad Digital.")

    if not jornadas:
        existentes = sorted(JORNADAS.glob("jornada_*.json"))
        print(
            "No se encontraron nuevas jornadas en la fuente; "
            f"se conservan las {len(existentes)} jornadas ya publicadas."
        )
        return

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
