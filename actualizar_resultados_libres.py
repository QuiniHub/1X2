"""
Obtiene resultados de fútbol de fuentes GRATUITAS sin API key ni registro:
  1. ESPN API  — live scores + recientes, todos los grandes campeonatos
  2. TheSportsDB — histórico y próximos partidos por liga
  3. OpenFootball — datos estáticos en GitHub (La Liga, Champions, etc.)

Los resultados se guardan en data/resultados_libres.json para que
el resto del sistema (motor predictivo, IA chat) los consuma.
"""
import json
import re
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT  = DATA / "resultados_libres.json"

# ─── Ligas a consultar ────────────────────────────────────────────────────────

ESPN_LIGAS = {
    "La Liga":            "esp.1",
    "Segunda División":   "esp.2",
    "Champions League":   "UEFA.CHAMPIONS",
    "Europa League":      "UEFA.EUROPA",
    "Conference League":  "UEFA.EUROPA.CONFERENCE",
    "Premier League":     "eng.1",
    "Bundesliga":         "ger.1",
    "Serie A":            "ita.1",
    "Ligue 1":            "fra.1",
    "Eredivisie":         "ned.1",
    "Primeira Liga":      "por.1",
    "Copa del Rey":       "esp.copa_del_rey",
    "Copa del Mundo":     "FIFA.WORLD",
}

THESPORTSDB_LIGAS = {
    "La Liga":            "4335",
    "Segunda División":   "4336",
    "Premier League":     "4328",
    "Bundesliga":         "4331",
    "Serie A":            "4332",
    "Ligue 1":            "4334",
    "Champions League":   "4346",
    "Europa League":      "4347",
    "Conference League":  "4348",
    "Mundial 2026":       "600614",
}

OPENFOOTBALL_URLS = {
    "La Liga 2025-26": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/es.1.json",
    "Champions 2025-26": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/cl.json",
    "Premier 2025-26": "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/en.1.json",
    "Mundial 2026": "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (QuiniHub/1X2 bot)"}

ALIAS = {
    "atletico madrid": "Club Atletico de Madrid",
    "atlético de madrid": "Club Atletico de Madrid",
    "atletico de madrid": "Club Atletico de Madrid",
    "barcelona": "FC Barcelona",
    "fc barcelona": "FC Barcelona",
    "real madrid": "Real Madrid CF",
    "sevilla": "Sevilla FC",
    "valencia": "Valencia CF",
    "villarreal": "Villarreal CF",
    "real betis": "Real Betis Balompie",
    "athletic club": "Athletic Club",
    "athletic bilbao": "Athletic Club",
    "real sociedad": "Real Sociedad de Futbol",
    "osasuna": "CA Osasuna",
    "getafe": "Getafe CF",
    "girona": "Girona FC",
    "rayo vallecano": "Rayo Vallecano de Madrid",
    "celta vigo": "RC Celta de Vigo",
    "rc celta": "RC Celta de Vigo",
    "espanyol": "RCD Espanyol de Barcelona",
    "rcd espanyol": "RCD Espanyol de Barcelona",
    "mallorca": "RCD Mallorca",
    "las palmas": "UD Las Palmas",
    "alaves": "Deportivo Alaves",
    "leganes": "CD Leganes",
    "valladolid": "Real Valladolid CF",
    "netherlands": "Países Bajos",
    "holland": "Países Bajos",
    "germany": "Alemania",
    "france": "Francia",
    "spain": "España",
    "england": "Inglaterra",
    "brazil": "Brasil",
    "argentina": "Argentina",
    "portugal": "Portugal",
    "usa": "EE.UU.",
    "united states": "EE.UU.",
    "mexico": "México",
    "canada": "Canadá",
    "south africa": "Sudáfrica",
    "morocco": "Marruecos",
    "ivory coast": "Costa de Marfil",
    "cote d'ivoire": "Costa de Marfil",
    "côte d'ivoire": "Costa de Marfil",
}

def norm(nombre):
    n = str(nombre or "").strip().lower()
    return ALIAS.get(n, nombre.strip() if nombre else "")


# ─── FUENTE 1: ESPN API ───────────────────────────────────────────────────────

def obtener_espn_liga(nombre_liga, codigo_liga):
    resultados = []
    # Consultar los últimos 3 días + hoy
    hoy = datetime.now(timezone.utc)
    fechas = [(hoy - timedelta(days=i)).strftime("%Y%m%d") for i in range(3, -1, -1)]

    for fecha in fechas:
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{codigo_liga}/scoreboard"
            r = requests.get(url, params={"dates": fecha}, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            events = r.json().get("events", [])
            for ev in events:
                competiciones = ev.get("competitions", [])
                for comp in competiciones:
                    status = (comp.get("status") or {})
                    tipo_status = (status.get("type") or {}).get("name", "")
                    terminado = tipo_status in ("STATUS_FINAL", "STATUS_FULL_TIME", "STATUS_EXTRA_TIME", "STATUS_PENALTIES")
                    competidores = comp.get("competitors", [])
                    if len(competidores) < 2:
                        continue
                    home = next((c for c in competidores if c.get("homeAway") == "home"), competidores[0])
                    away = next((c for c in competidores if c.get("homeAway") == "away"), competidores[1])
                    local = norm((home.get("team") or {}).get("displayName", ""))
                    visitante = norm((away.get("team") or {}).get("displayName", ""))
                    score_h = home.get("score")
                    score_a = away.get("score")
                    resultado = None
                    ganador = None
                    if terminado and score_h is not None and score_a is not None:
                        try:
                            gh, ga = int(score_h), int(score_a)
                            resultado = f"{gh}-{ga}"
                            if gh > ga:
                                ganador = local
                            elif ga > gh:
                                ganador = visitante
                        except (ValueError, TypeError):
                            pass
                    fecha_partido = (ev.get("date") or "")[:10]
                    resultados.append({
                        "liga": nombre_liga,
                        "local": local,
                        "visitante": visitante,
                        "resultado": resultado,
                        "ganador": ganador,
                        "fecha": fecha_partido,
                        "en_juego": tipo_status in ("STATUS_IN_PROGRESS", "STATUS_HALFTIME"),
                        "minuto": status.get("displayClock", ""),
                        "fuente": "espn",
                    })
        except Exception as e:
            print(f"  ESPN {nombre_liga} {fecha}: {e}")
    return resultados

def obtener_espn():
    print("ESPN: consultando ligas...")
    todos = []
    for nombre, codigo in ESPN_LIGAS.items():
        partidos = obtener_espn_liga(nombre, codigo)
        print(f"  {nombre}: {len(partidos)} partidos")
        todos.extend(partidos)
    return todos


# ─── FUENTE 2: TheSportsDB ────────────────────────────────────────────────────

def obtener_thesportsdb_liga(nombre_liga, league_id):
    resultados = []
    try:
        r = requests.get(
            "https://www.thesportsdb.com/api/v1/json/3/eventspastleague.php",
            params={"id": league_id},
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            events = r.json().get("events") or []
            for e in events:
                status = str(e.get("strStatus") or "")
                terminado = status in ("Match Finished", "FT", "AOT", "AP", "finished")
                local = norm(e.get("strHomeTeam", ""))
                visitante = norm(e.get("strAwayTeam", ""))
                hg = e.get("intHomeScore")
                ag = e.get("intAwayScore")
                resultado = None
                ganador = None
                if terminado and hg is not None and ag is not None:
                    try:
                        gh, ga = int(hg), int(ag)
                        resultado = f"{gh}-{ga}"
                        ganador = local if gh > ga else (visitante if ga > gh else None)
                    except (ValueError, TypeError):
                        pass
                resultados.append({
                    "liga": nombre_liga,
                    "local": local,
                    "visitante": visitante,
                    "resultado": resultado,
                    "ganador": ganador,
                    "fecha": e.get("dateEvent", ""),
                    "en_juego": False,
                    "fuente": "thesportsdb",
                })
    except Exception as e:
        print(f"  TheSportsDB {nombre_liga}: {e}")
    return resultados

def obtener_thesportsdb():
    print("TheSportsDB: consultando ligas...")
    todos = []
    for nombre, lid in THESPORTSDB_LIGAS.items():
        partidos = obtener_thesportsdb_liga(nombre, lid)
        print(f"  {nombre}: {len(partidos)} partidos")
        todos.extend(partidos)
    return todos


# ─── FUENTE 3: OpenFootball (GitHub, estático) ───────────────────────────────

def obtener_openfootball():
    print("OpenFootball: consultando...")
    todos = []
    for nombre, url in OPENFOOTBALL_URLS.items():
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()
            # Formato worldcup.json
            for ronda in data.get("rounds", []):
                for m in ronda.get("matches", []):
                    score = m.get("score", {})
                    ft = score.get("ft", [])
                    if not ft or len(ft) < 2:
                        continue
                    local = norm(m.get("team1", {}).get("name", ""))
                    visitante = norm(m.get("team2", {}).get("name", ""))
                    gh, ga = int(ft[0]), int(ft[1])
                    resultado = f"{gh}-{ga}"
                    ganador = local if gh > ga else (visitante if ga > gh else None)
                    todos.append({
                        "liga": nombre,
                        "local": local, "visitante": visitante,
                        "resultado": resultado, "ganador": ganador,
                        "fecha": m.get("date", ""), "en_juego": False,
                        "fuente": "openfootball",
                    })
            # Formato football.json (matchdays)
            for md in data.get("matchdays", []):
                for m in md.get("matches", []):
                    score = m.get("score")
                    if not score:
                        continue
                    local = norm(m.get("team1", ""))
                    visitante = norm(m.get("team2", ""))
                    gh = score.get("ft", [None, None])[0]
                    ga = score.get("ft", [None, None])[1]
                    if gh is None or ga is None:
                        continue
                    resultado = f"{int(gh)}-{int(ga)}"
                    ganador = local if gh > ga else (visitante if ga > gh else None)
                    todos.append({
                        "liga": nombre,
                        "local": local, "visitante": visitante,
                        "resultado": resultado, "ganador": ganador,
                        "fecha": m.get("date", ""), "en_juego": False,
                        "fuente": "openfootball",
                    })
            print(f"  {nombre}: OK")
        except Exception as e:
            print(f"  OpenFootball {nombre}: {e}")
    return todos


# ─── GUARDAR Y COMBINAR ───────────────────────────────────────────────────────

def guardar(partidos):
    # Eliminar duplicados: misma liga+local+visitante+fecha → quedarse con el más fiable
    prioridad = {"espn": 0, "thesportsdb": 1, "openfootball": 2}
    index = {}
    for p in partidos:
        clave = (
            p.get("liga", ""),
            str(p.get("local", "")).lower(),
            str(p.get("visitante", "")).lower(),
            p.get("fecha", ""),
        )
        prio = prioridad.get(p.get("fuente", ""), 9)
        tiene_res = bool(p.get("resultado"))
        if clave not in index:
            index[clave] = dict(p, _prio=prio)
        else:
            prev = index[clave]
            prev_res = bool(prev.get("resultado"))
            if tiene_res and (not prev_res or prio < prev.get("_prio", 9)):
                index[clave] = dict(p, _prio=prio)

    resultado_final = [
        {k: v for k, v in p.items() if k != "_prio"}
        for p in index.values()
    ]
    resultado_final.sort(key=lambda x: x.get("fecha", ""), reverse=True)

    data = {
        "actualizado_en": datetime.now(timezone.utc).isoformat(),
        "total": len(resultado_final),
        "partidos": resultado_final,
    }
    DATA.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Guardados {len(resultado_final)} partidos en {OUT.name}")


if __name__ == "__main__":
    print("=== Actualizando resultados desde fuentes libres ===")
    todos = []
    todos.extend(obtener_espn())
    todos.extend(obtener_thesportsdb())
    todos.extend(obtener_openfootball())
    print(f"Total bruto: {len(todos)} partidos")
    guardar(todos)
    print("=== Completado ===")
