"""Memoria universal de ligas externas para La Quiniela.

Detecta equipos que no son espanoles ni selecciones del Mundial, intenta
obtener clasificacion y forma, y acumula aprendizaje permanente por equipo y liga.
"""

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

try:
    import requests
except Exception:
    requests = None

import os

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

try:
    from actualizar_clasificaciones_mundial_2026 import EQUIPO_A_GRUPO, normalizar_nombre as normalizar_mundial
except Exception:
    EQUIPO_A_GRUPO = {}
    normalizar_mundial = None

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
PREDICCIONES = DATA / "predicciones"
MEMORIA = DATA / "memoria_ia"
FUENTE_LOSILLA = MEMORIA / "fuente_losilla.json"
SALIDA_LIGAS = MEMORIA / "ligas_externas.json"
SALIDA_APRENDIZAJE = MEMORIA / "aprendizaje_ligas_externas.json"

URL_LOSILLA = "https://www.eduardolosilla.es/quiniela/ayudas/clasificacion"
URL_RF = "https://www.resultados-futbol.com/{liga}"
TIMEOUT = 12
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept-Language": "es-ES,es;q=0.9"}

ESPANOLES_BASE = {
    "alaves", "albacete", "alcorcon", "almeria", "athletic", "atletico madrid", "barcelona", "betis",
    "burgos", "cadiz", "cartagena", "castellon", "celta", "cordoba", "deportivo", "eibar", "elche",
    "eldense", "espanyol", "getafe", "girona", "granada", "huesca", "las palmas", "leganes", "levante",
    "malaga", "mallorca", "mirandes", "osasuna", "oviedo", "racing", "rayo vallecano", "real madrid",
    "real sociedad", "sevilla", "sporting", "tenerife", "valencia", "valladolid", "villarreal", "zaragoza",
}
RUIDO = {"fc", "cf", "cd", "sd", "ud", "rcd", "rc", "sad", "club", "real", "de", "del", "la", "el", "ac", "bk", "if"}


def ahora():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cargar(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalizar(texto):
    texto = str(texto or "").lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def clave_equipo(nombre):
    base = normalizar(nombre)
    limpio = " ".join(t for t in base.split() if t not in RUIDO)
    return limpio or base


def numero(valor, defecto=None):
    txt = re.sub(r"[^0-9,.-]", "", str(valor or ""))
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    try:
        return int(float(txt))
    except Exception:
        return defecto


def descargar(url):
    if not requests:
        raise RuntimeError("requests no disponible")
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def nombres_en_objeto(obj):
    out = set()
    if isinstance(obj, dict):
        nombre = obj.get("equipo") or obj.get("nombre") or obj.get("name")
        if nombre:
            out.add(clave_equipo(nombre))
        for value in obj.values():
            if isinstance(value, (dict, list)):
                out.update(nombres_en_objeto(value))
    elif isinstance(obj, list):
        for item in obj:
            out.update(nombres_en_objeto(item))
    return out


def equipos_espanoles():
    equipos = {clave_equipo(x) for x in ESPANOLES_BASE}
    for path in (DATA / "clasificaciones_oficiales.json", MEMORIA / "contexto_competitivo.json", MEMORIA / "aprendizaje_global.json"):
        equipos.update(nombres_en_objeto(cargar(path, {})))
    return {x for x in equipos if x}


def es_mundial(nombre):
    if normalizar_mundial and normalizar_mundial(nombre) in EQUIPO_A_GRUPO:
        return True
    return clave_equipo(nombre) in {clave_equipo(x) for x in EQUIPO_A_GRUPO}


def es_espanol(nombre, espanoles):
    clave = clave_equipo(nombre)
    return clave in espanoles or any(clave and (clave in e or e in clave) for e in espanoles)


def jornada_activa():
    nums = []
    for path in list(JORNADAS.glob("jornada_*.json")) + list(PREDICCIONES.glob("jornada_*.json")):
        data = cargar(path, {})
        n = data.get("jornada")
        if not isinstance(n, int):
            m = re.search(r"(\d+)", path.stem)
            n = int(m.group(1)) if m else 0
        if n:
            nums.append(n)
    return max(nums) if nums else None


def partidos_de_jornada(jornada):
    data = cargar(JORNADAS / f"jornada_{jornada}.json", {}) or cargar(PREDICCIONES / f"jornada_{jornada}.json", {})
    return [p for p in data.get("partidos", []) if int(p.get("num") or p.get("numero") or 0) <= 14]


def detectar_externos():
    jornada = jornada_activa()
    espanoles = equipos_espanoles()
    detectados = {}
    for p in partidos_de_jornada(jornada):
        for campo, condicion in (("local", "local"), ("visitante", "visitante")):
            nombre = p.get(campo) or ""
            clave = clave_equipo(nombre)
            if clave and not es_espanol(nombre, espanoles) and not es_mundial(nombre):
                detectados[clave] = {"equipo": nombre, "clave": clave, "jornada": jornada, "condicion": condicion, "partido": f"{p.get('local','')} - {p.get('visitante','')}"}
    return detectados


def ligas_losilla_local():
    data = cargar(FUENTE_LOSILLA, {})
    ligas = (((data.get("clasificaciones") or {}).get("ligas") or {}) if isinstance(data, dict) else {})
    return ligas if isinstance(ligas, dict) else {}


def ligas_losilla_web():
    if not BeautifulSoup:
        return {}
    try:
        soup = BeautifulSoup(descargar(URL_LOSILLA), "html.parser")
    except Exception:
        return {}
    ligas = {}
    for tabla in soup.find_all("table"):
        titulo = tabla.find_previous(["h1", "h2", "h3", "h4"])
        liga = " ".join(titulo.get_text(" ").split()) if titulo else f"Liga {len(ligas)+1}"
        filas = []
        for tr in tabla.find_all("tr"):
            c = [" ".join(td.get_text(" ").split()) for td in tr.find_all(["td", "th"])]
            if len(c) < 2:
                continue
            pos = numero(c[0])
            equipo = c[1] if pos else c[0]
            pts = next((numero(x) for x in reversed(c) if numero(x) is not None), None)
            if equipo and pos:
                filas.append({"equipo": equipo, "posicion": pos, "Pts": pts})
        if filas:
            ligas[liga] = filas
    return ligas


def score_nombre(a, b):
    a, b = clave_equipo(a), clave_equipo(b)
    if a == b and a:
        return 1000
    comunes = set(a.split()) & set(b.split())
    return len(comunes) * 40 + (30 if a in b or b in a else 0)


def buscar_losilla(nombre, ligas):
    mejor, mejor_liga, score = None, "", 0
    for liga, tabla in ligas.items():
        for idx, fila in enumerate(tabla if isinstance(tabla, list) else [], start=1):
            s = score_nombre(fila.get("equipo") or "", nombre)
            if s > score:
                mejor = {**fila, "posicion": fila.get("posicion") or idx}
                mejor_liga, score = liga, s
    return (mejor, mejor_liga) if score >= 55 else (None, "")


def signo_resultado(resultado):
    m = re.match(r"^\s*(\d{1,2})\s*-\s*(\d{1,2})\s*$", str(resultado or ""))
    if not m:
        return ""
    gl, gv = int(m.group(1)), int(m.group(2))
    return "1" if gl > gv else "X" if gl == gv else "2"


def resultado_equipo(partido, clave):
    local, visitante = clave_equipo(partido.get("local")), clave_equipo(partido.get("visitante"))
    m = re.match(r"^\s*(\d{1,2})\s*-\s*(\d{1,2})\s*$", str(partido.get("resultado") or ""))
    if not m or clave not in {local, visitante}:
        return None
    gl, gv = int(m.group(1)), int(m.group(2))
    gf, gc, cond = (gl, gv, "local") if clave == local else (gv, gl, "visitante")
    return {"fecha": partido.get("fecha") or "", "condicion": cond, "r": "G" if gf > gc else "E" if gf == gc else "P", "gf": gf, "gc": gc}


def forma_equipo(clave):
    hist = []
    for path in sorted(JORNADAS.glob("jornada_*.json")):
        for p in cargar(path, {}).get("partidos", []):
            r = resultado_equipo(p, clave)
            if r:
                hist.append(r)
    hist = sorted(hist, key=lambda x: x.get("fecha") or "9999-99-99")
    return {
        "ultimos_5_local": [x["r"] for x in hist if x["condicion"] == "local"][-5:],
        "ultimos_5_visitante": [x["r"] for x in hist if x["condicion"] == "visitante"][-5:],
        "goles_favor": sum(x["gf"] for x in hist),
        "goles_contra": sum(x["gc"] for x in hist),
        "partidos_historicos_detectados": len(hist),
    }


def slug_liga(liga):
    return normalizar(liga).replace(" ", "-")


def buscar_info_tavily(equipo, contexto=""):
    """Busca info de un equipo/liga usando Tavily cuando las fuentes locales fallan."""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key or not requests:
        return {}
    nombre = equipo.strip()
    query = f"{nombre} football league 2026 classification standings table"
    if contexto:
        query = f"{nombre} {contexto} football 2026 standings"
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            json={"api_key": api_key, "query": query, "max_results": 5, "search_depth": "basic"},
            timeout=15,
        )
        resp.raise_for_status()
        resultados = resp.json().get("results") or []
        textos = []
        liga_detectada = ""
        pos_detectada = None
        for r in resultados:
            contenido = (r.get("content") or "") + " " + (r.get("title") or "")
            textos.append(contenido[:300])
            # Intentar detectar liga en el texto
            if not liga_detectada:
                for liga_cand in ["Allsvenskan", "Veikkausliiga", "Eliteserien", "Superligaen",
                                   "Scottish Premiership", "Eredivisie", "Bundesliga", "Ligue 1",
                                   "Serie A", "Premier League", "La Liga", "Primeira Liga",
                                   "Ekstraklasa", "Czech Liga", "Slovak Super Liga", "Swiss Super League",
                                   "Austrian Bundesliga", "Belgian Pro League"]:
                    if liga_cand.lower() in contenido.lower():
                        liga_detectada = liga_cand
                        break
            # Intentar extraer posición
            if pos_detectada is None:
                m = re.search(rf"(?:position|pos\.?|puesto|rank)[^\d]{{0,10}}(\d{{1,2}})", contenido, re.I)
                if not m:
                    m = re.search(rf"(\d{{1,2}})[^\d]{{0,5}}{re.escape(normalizar(nombre)[:8])}", normalizar(contenido), re.I)
                if m:
                    pos_detectada = int(m.group(1))
        return {
            "fuente_tavily": True,
            "liga_tavily": liga_detectada or "",
            "posicion_tavily": pos_detectada,
            "extracto_tavily": " | ".join(textos[:3])[:500],
        }
    except Exception as exc:
        return {"aviso_tavily": str(exc)[:120]}


def consultar_resultados_futbol(equipo, liga):
    if not liga or liga == "desconocida":
        return {}
    url = URL_RF.format(liga=quote_plus(slug_liga(liga)))
    info = {"fuente_resultados_futbol": url}
    try:
        info["equipo_detectado_resultados_futbol"] = clave_equipo(equipo) in normalizar(descargar(url))
    except Exception as exc:
        info["aviso_resultados_futbol"] = str(exc)[:140]
    return info


def actualizar_ligas():
    detectados = detectar_externos()
    data = cargar(SALIDA_LIGAS, {"version": "1.0", "equipos": {}})
    equipos = data.setdefault("equipos", {})
    ligas = ligas_losilla_local() or ligas_losilla_web()
    avisos = []
    for clave, det in detectados.items():
        previo = equipos.get(clave, {}) if isinstance(equipos.get(clave), dict) else {}
        fila, liga = buscar_losilla(det["equipo"], ligas)
        liga = liga or previo.get("liga") or "desconocida"
        forma = forma_equipo(clave)
        extra = consultar_resultados_futbol(det["equipo"], liga)
        tavily_info = {}
        if not fila or liga == "desconocida":
            tavily_info = buscar_info_tavily(det["equipo"])
            liga_tv = tavily_info.get("liga_tavily") or ""
            if liga_tv and liga == "desconocida":
                liga = liga_tv
            pos_tv = tavily_info.get("posicion_tavily")
            if pos_tv and not (fila or {}).get("posicion"):
                if not fila:
                    fila = {}
                fila["posicion"] = fila.get("posicion") or pos_tv
        if not fila:
            avisos.append(f"{det['equipo']}: sin clasificacion fiable en Losilla; se consulto Tavily ({tavily_info.get('liga_tavily') or 'sin resultado'}).")
        fuente = "eduardolosilla.es" if fila and not tavily_info else ("tavily" if tavily_info.get("liga_tavily") else "pendiente")
        equipos[clave] = {**previo, **det, "liga": liga, "posicion": numero((fila or {}).get("posicion"), previo.get("posicion")), "puntos": numero((fila or {}).get("Pts") if fila else None, previo.get("puntos")), **forma, "fuente_principal": fuente, "fuentes_consultadas": [URL_LOSILLA, extra.get("fuente_resultados_futbol"), "tavily" if tavily_info else None], "actualizado_en": ahora(), **extra, **tavily_info}
    data.update({"version": "1.0", "actualizado_en": ahora(), "total_equipos": len(equipos), "equipos_detectados_ultima_jornada": sorted(detectados), "avisos": avisos[-50:]})
    guardar(SALIDA_LIGAS, data)
    return data, detectados


def tipo_signo(signo, tipo=""):
    if tipo:
        return str(tipo).upper()
    n = len("".join(s for s in "1X2" if s in str(signo or "").upper()))
    return "TRIPLE" if n >= 3 else "DOBLE" if n == 2 else "FIJO"


def inc(dic, key):
    dic[key] = int(dic.get(key) or 0) + 1


def patrones(info, condicion):
    out = []
    pos = info.get("posicion")
    forma = info.get("ultimos_5_local" if condicion == "local" else "ultimos_5_visitante") or []
    if isinstance(pos, int) and pos <= 4:
        out.append(f"{condicion}_fuerte")
    if isinstance(pos, int) and pos >= 14:
        out.append(f"{condicion}_debil")
    if forma[-3:].count("G") >= 2:
        out.append("racha_positiva")
    if forma[-3:].count("P") >= 2:
        out.append("racha_negativa")
    return out or ["sin_patron_claro"]


def actualizar_aprendizaje(mem_ligas):
    apr = cargar(SALIDA_APRENDIZAJE, {"version": "1.0", "equipos": {}, "ligas": {}, "partidos_procesados": []})
    apr.setdefault("equipos", {}); apr.setdefault("ligas", {})
    procesados = set(apr.get("partidos_procesados") or [])
    equipos_info = mem_ligas.get("equipos") or {}
    nuevos = 0
    for pred_path in sorted(PREDICCIONES.glob("jornada_*.json")):
        pred = cargar(pred_path, {})
        jornada = pred.get("jornada") or numero(pred_path.stem)
        oficiales = {int(p.get("num") or 0): p for p in cargar(JORNADAS / f"jornada_{jornada}.json", {}).get("partidos", []) if p.get("num")}
        for p in pred.get("partidos", []):
            num = int(p.get("num") or 0)
            oficial = oficiales.get(num, {})
            signo_of = str(oficial.get("signo_oficial") or "").upper() or signo_resultado(oficial.get("resultado") or p.get("resultado"))
            if signo_of not in {"1", "X", "2"}:
                continue
            jugado = "".join(s for s in "1X2" if s in str(p.get("signo_final") or p.get("signo_base") or "").upper())
            if not jugado:
                continue
            acertado = signo_of in jugado
            tipo = tipo_signo(jugado, p.get("tipo"))
            for campo, condicion in (("local", "local"), ("visitante", "visitante")):
                clave = clave_equipo(p.get(campo))
                if clave not in equipos_info:
                    continue
                marca = f"{jornada}:{num}:{clave}"
                if marca in procesados:
                    continue
                info = equipos_info[clave]
                liga = info.get("liga") or "desconocida"
                eq = apr["equipos"].setdefault(clave, {"equipo": info.get("equipo") or p.get(campo), "liga": liga, "apariciones": 0, "aciertos": 0, "fallos": 0, "aciertos_por_tipo": {}, "fallos_por_tipo": {}, "patrones_acierto": {}, "patrones_fallo": {}, "historial": []})
                eq["liga"] = liga; inc(eq, "apariciones"); inc(eq, "aciertos" if acertado else "fallos")
                inc(eq.setdefault("aciertos_por_tipo" if acertado else "fallos_por_tipo", {}), tipo)
                dest = eq.setdefault("patrones_acierto" if acertado else "patrones_fallo", {})
                pats = patrones(info, condicion)
                for pat in pats:
                    inc(dest, pat)
                eq.setdefault("historial", []).append({"jornada": jornada, "num": num, "partido": f"{p.get('local','')} - {p.get('visitante','')}", "condicion": condicion, "tipo": tipo, "signo_jugado": jugado, "signo_oficial": signo_of, "acertado": acertado, "patrones": pats, "registrado_en": ahora()})
                lg = apr["ligas"].setdefault(liga, {"apariciones": 0, "aciertos": 0, "fallos": 0})
                inc(lg, "apariciones"); inc(lg, "aciertos" if acertado else "fallos")
                procesados.add(marca); nuevos += 1
    for bloque in (apr["equipos"], apr["ligas"]):
        for item in bloque.values():
            total = max(int(item.get("apariciones") or 0), 1)
            item["precision"] = round(float(item.get("aciertos") or 0) / total, 4)
    apr["partidos_procesados"] = sorted(procesados)[-5000:]
    apr["actualizado_en"] = ahora(); apr["nuevos_registros_ultimo_ciclo"] = nuevos
    guardar(SALIDA_APRENDIZAJE, apr)
    return apr, nuevos


def main():
    ligas, detectados = actualizar_ligas()
    _, nuevos = actualizar_aprendizaje(ligas)
    print(f"Ligas externas actualizadas: {len(detectados)} equipo(s) detectado(s), {ligas.get('total_equipos', 0)} equipo(s) en memoria, {nuevos} aprendizaje(s) nuevo(s).")


if __name__ == "__main__":
    main()
