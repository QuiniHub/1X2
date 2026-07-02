"""Descarga detalles H2H y rachas de la jornada actual desde api.eduardolosilla.es.

Estructura real de la API (inspeccionada julio 2026):
  - veces1/vecesX/veces2: H2H directo histórico
  - local_casa / visitante_fuera: rendimiento como local/visitante
  - anosAnteriores: resultados jornada por año (últimos 10)
  - comparativa.vuelta1.partidos_local / .partidos_visitante: forma reciente
  - datosDestacados: datos quinielísticos por casilla
  - comentario: análisis editorial
  - tecnico1/tecnicoX/tecnico2: probabilidades LAE

Salida: data/jornadas/detalles_j{N}.json
Inyectado en Chat IA via construirContextoIA() en index.html.
"""

import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCION = DATA / "predicciones" / "ultima_prediccion.json"
JORNADAS_DIR = DATA / "jornadas"

URL_BASE = "https://www.eduardolosilla.es"
URL_API = "https://api.eduardolosilla.es/detallePartido"

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

HEADERS_API = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Origin": URL_BASE,
    "Pragma": "no-cache",
    "Referer": URL_BASE + "/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0",
}


def cargar_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def guardar_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def iniciar_sesion():
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    req = urllib.request.Request(URL_BASE, headers=HEADERS_BASE)
    with opener.open(req, timeout=15) as r:
        r.read()
    return opener


def obtener_detalles_raw(opener, jornada, temporada):
    ts = int(time.time() * 1000)
    params = urllib.parse.urlencode({"jornada": jornada, "temporada": temporada, "uts": ts})
    req = urllib.request.Request(f"{URL_API}?{params}", headers=HEADERS_API)
    with opener.open(req, timeout=20) as r:
        raw = r.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    return data.get("detallePartidos", [])


def signo_de_resultado(resultado_str, equipo_es_local):
    """Convierte 'goles_local-goles_vis' en signo 1/X/2 desde perspectiva del equipo."""
    try:
        partes = str(resultado_str).strip().split("-")
        if len(partes) != 2:
            return ""
        gl, gv = int(partes[0]), int(partes[1])
        if gl > gv:
            return "1" if equipo_es_local else "2"
        if gl < gv:
            return "2" if equipo_es_local else "1"
        return "X"
    except Exception:
        return ""


def rachas_de_comparativa(comparativa, vuelta_key, partidos_key):
    """Extrae lista de signos (1/X/2) de los últimos partidos de un equipo."""
    vuelta = (comparativa or {}).get(vuelta_key) or {}
    partidos = vuelta.get(partidos_key) or []
    rachas = []
    es_local = (partidos_key == "partidos_local")
    for p in partidos:
        if not isinstance(p, dict):
            continue
        res = p.get("resultado") or p.get("resultado_real") or ""
        s = signo_de_resultado(res, es_local)
        if s:
            rachas.append(s)
    return rachas[:5]


def resumir_partido(dt, idx):
    """Extrae campos útiles del partido de la API con la estructura real (julio 2026)."""
    local = (dt.get("local") or "").strip()
    visitante = (dt.get("visitante") or "").strip()

    # H2H directo (quinielas en que se han enfrentado)
    v1 = int(dt.get("veces1") or 0)
    vX = int(dt.get("vecesX") or 0)
    v2 = int(dt.get("veces2") or 0)

    # H2H en años anteriores (array de {ano, resultado})
    anos = dt.get("anosAnteriores") or []
    h2h_anos = []
    for a in anos:
        if not isinstance(a, dict):
            continue
        res = str(a.get("resultado") or "").strip()
        if res and res != "-":
            s = signo_de_resultado(res, equipo_es_local=True)
            h2h_anos.append({"ano": a.get("ano"), "resultado": res, "signo": s})

    # Rendimiento como local y visitante
    local_casa = dt.get("local_casa") or {}
    visitante_fuera = dt.get("visitante_fuera") or {}

    # Rachas recientes de comparativa
    comp = dt.get("comparativa") or {}
    racha_local = rachas_de_comparativa(comp, "vuelta1", "partidos_local")
    racha_visitante = rachas_de_comparativa(comp, "vuelta2", "partidos_visitante")

    # Probabilidades LAE de los técnicos
    prob1 = int(dt.get("tecnico1") or 0)
    probX = int(dt.get("tecnicoX") or 0)
    prob2 = int(dt.get("tecnico2") or 0)

    # Datos destacados quinielísticos
    datos_destacados = []
    for d in (dt.get("datosDestacados") or []):
        txt = str(d).strip() if not isinstance(d, dict) else (d.get("texto") or d.get("dato") or "").strip()
        if txt:
            datos_destacados.append(txt)

    # Comentario editorial (primeros 400 chars)
    comentario = (dt.get("comentario") or "").strip()[:400]

    return {
        "num": int(dt.get("orden") or idx),
        "local": local,
        "visitante": visitante,
        "division": dt.get("division"),
        "clasificacion_local": str(dt.get("clasificacionLocal") or "").strip(),
        "clasificacion_visitante": str(dt.get("clasificacionVisitante") or "").strip(),
        "prob_lae": {"1": prob1, "X": probX, "2": prob2},
        "h2h_quiniela": {"v1": v1, "vX": vX, "v2": v2, "total": v1 + vX + v2},
        "h2h_anos": h2h_anos,
        "local_como_local": {
            "v1": int(local_casa.get("veces1") or 0),
            "vX": int(local_casa.get("vecesX") or 0),
            "v2": int(local_casa.get("veces2") or 0),
        },
        "visitante_como_visitante": {
            "v1": int(visitante_fuera.get("veces1") or 0),
            "vX": int(visitante_fuera.get("vecesX") or 0),
            "v2": int(visitante_fuera.get("veces2") or 0),
        },
        "racha_reciente_local": racha_local,
        "racha_reciente_visitante": racha_visitante,
        "datos_destacados": datos_destacados[:5],
        "comentario_editorial": comentario,
        "recomendado_losilla": (dt.get("recomendado") or "").strip(),
    }


def main():
    print("=== Detalles partidos eduardolosilla.es ===\n")

    pred = cargar_json(PREDICCION)
    if not pred:
        print("ERROR: no se puede leer ultima_prediccion.json")
        return

    jornada = int(pred.get("jornada") or 0)
    if not jornada:
        print("ERROR: jornada no disponible en prediccion")
        return

    # eduardolosilla usa año de FIN de temporada (2025/26 = 2026)
    temporada = 2026
    salida = JORNADAS_DIR / f"detalles_j{jornada}.json"

    print(f"Jornada {jornada} | Temporada {temporada}")

    try:
        print("Iniciando sesion en eduardolosilla.es...")
        opener = iniciar_sesion()
    except Exception as e:
        print(f"ERROR abriendo sesion: {e}")
        return

    try:
        print(f"Descargando detalles...")
        detalles_raw = obtener_detalles_raw(opener, jornada, temporada)
    except Exception as e:
        print(f"ERROR descargando detalles: {e}")
        return

    if not detalles_raw:
        guardar_json(salida, {
            "jornada": jornada, "temporada": temporada,
            "generado_en": datetime.now(timezone.utc).isoformat(),
            "fuente": URL_API, "partidos": [], "nota": "sin_datos",
        })
        print("API devolvio lista vacia — guardado marcador vacio")
        return

    partidos = []
    for i, dt in enumerate(detalles_raw, 1):
        if not isinstance(dt, dict):
            dt = {}
        try:
            p = resumir_partido(dt, i)
            partidos.append(p)
            h = p["h2h_quiniela"]
            pr = p["prob_lae"]
            racha_l = "".join(p["racha_reciente_local"]) or "—"
            racha_v = "".join(p["racha_reciente_visitante"]) or "—"
            print(f"  P{p['num']:>2} {p['local'][:13]:<13} vs {p['visitante'][:13]:<13} "
                  f"| LAE {pr['1']}%/{pr['X']}%/{pr['2']}% "
                  f"| H2H {h['v1']}V{h['vX']}E{h['v2']}D "
                  f"| loc:{racha_l} vis:{racha_v}")
        except Exception as e:
            print(f"  P{i}: error — {e}")

    resultado = {
        "jornada": jornada,
        "temporada": temporada,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "fuente": URL_API,
        "partidos": partidos,
    }
    guardar_json(salida, resultado)
    print(f"\nGuardado en {salida} ({len(partidos)} partidos)")


if __name__ == "__main__":
    main()
