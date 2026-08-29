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
import unicodedata
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
    "Segunda División":   "4400",
    "Premier League":     "4328",
    "Bundesliga":         "4331",
    "Serie A":            "4332",
    "Ligue 1":            "4334",
    "Champions League":   "4346",
    "Europa League":      "4347",
    "Conference League":  "4348",
    "Mundial 2026":       "600614",
}

# eventspastleague.php (usado abajo) solo devuelve el ULTIMO partido de la
# liga -util para "que paso mas reciente" pero inutil para "dame todos los
# partidos de esta jornada", que es lo que necesita el calendario oficial
# (ej. Real Sociedad B 0-1 Castellon, o cualquier partido que la Quiniela
# no eligiera esa semana, se quedaba siempre sin resultado). eventsround.php
# si da la jornada completa, y solo tiene sentido para ligas con jornadas
# de liguilla normales (no copas ni fases de grupos/eliminatorias).
LIGAS_CON_JORNADAS = {"La Liga": "4335", "Segunda División": "4400"}
TEMPORADA_THESPORTSDB = "2026-2027"

# Calendario oficial ESTATICO (distinto de CALENDARIO_SEMBRADO mas abajo,
# que no lleva fecha por jornada) -se usa solo para saber que ronda de
# LaLiga/Segunda toca consultar cada dia.
CALENDARIO_OFICIAL_ESTATICO = {
    "La Liga": DATA / "calendario_1a_2627.json",
    "Segunda División": DATA / "calendario_2a_2627.json",
}


def rondas_a_consultar(nombre_liga, hoy=None, ventana_dias=9, minimo_rondas=(1, 2)):
    """Que rondas de LaLiga/Segunda pedirle a TheSportsDB hoy.

    Bug real confirmado el 29/08/2026: esto era una tupla fija (1, 2) desde
    el arranque de la temporada. En cuanto empezo a jugarse la Jornada 3
    (Alaves 1-0 Villarreal, viernes 28/08 -ya reflejado en la clasificacion
    oficial de AS.com, pero invisible para nuestro propio pipeline de
    resultados) dejo de cubrir nada nuevo: ni el fetch normal ni el propio
    backfill de huecos miraban mas alla de la ronda 2, pasase lo que pasase
    en el calendario real. Con una temporada de 38/42 jornadas, una
    constante fija se queda obsoleta la primera semana que avanza la liga.

    Se calcula a partir de la fecha OFICIAL de cada jornada en el
    calendario estatico (calendario_1a_2627.json/2a_2627.json, que si trae
    fecha por jornada -CALENDARIO_SEMBRADO mas abajo no) -devuelve las
    rondas cuya fecha cae entre "hoy - ventana_dias" y "hoy + 2" (para
    cubrir la ronda que se esta jugando ahora mismo aunque se reparta entre
    viernes y lunes). Si no hay dato de fecha (fallo de red, archivo vacio),
    cae al respaldo minimo original para no romper el pipeline."""
    if hoy is None:
        hoy = datetime.now(timezone.utc).date()
    path = CALENDARIO_OFICIAL_ESTATICO.get(nombre_liga)
    data = _cargar_json_local(path, {}) if path else {}
    rondas = set()
    for jornada in data.get("jornadas", []):
        try:
            num = int(jornada.get("num") or jornada.get("jornada") or 0)
            fecha = datetime.strptime(str(jornada.get("fecha") or "")[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        if hoy - timedelta(days=ventana_dias) <= fecha <= hoy + timedelta(days=2):
            rondas.add(num)
    return tuple(sorted(rondas)) if rondas else minimo_rondas

# calendario_primera.json/segunda.json ya vienen sembrados con el fixture
# oficial completo (sembrar_jornadas_desde_oficial() en
# actualizar_ligas_football_data.py) -se usan aqui solo para saber que
# partidos DEBERIAN existir en cada ronda, y asi detectar huecos reales de
# TheSportsDB sin tener que mantener una lista de casos conocidos a mano.
CALENDARIO_SEMBRADO = {
    "La Liga": DATA / "calendario_primera.json",
    "Segunda División": DATA / "calendario_segunda.json",
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

def _parsear_eventos_thesportsdb(nombre_liga, events):
    resultados = []
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
    return resultados


def obtener_thesportsdb_liga(nombre_liga, league_id):
    try:
        r = requests.get(
            "https://www.thesportsdb.com/api/v1/json/3/eventspastleague.php",
            params={"id": league_id},
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            return _parsear_eventos_thesportsdb(nombre_liga, r.json().get("events") or [])
    except Exception as e:
        print(f"  TheSportsDB {nombre_liga}: {e}")
    return []


def obtener_thesportsdb_por_rondas(nombre_liga, league_id, rondas):
    """Trae la jornada COMPLETA (todos los partidos, no solo el ultimo)
    via eventsround.php -necesario para el calendario oficial, que tiene
    que poder pintar el marcador de cualquier partido de la semana, no
    solo de los que eligio La Quiniela para su boleto."""
    resultados = []
    for ronda in rondas:
        try:
            r = requests.get(
                "https://www.thesportsdb.com/api/v1/json/3/eventsround.php",
                params={"id": league_id, "r": ronda, "s": TEMPORADA_THESPORTSDB},
                headers=HEADERS,
                timeout=15,
            )
            if r.status_code == 200:
                resultados.extend(_parsear_eventos_thesportsdb(nombre_liga, r.json().get("events") or []))
        except Exception as e:
            print(f"  TheSportsDB {nombre_liga} ronda {ronda}: {e}")
    return resultados

def _cargar_json_local(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not Path(path).exists():
        return defecto
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return defecto


def _clave_equipo(nombre):
    # Bug real confirmado el 29/08/2026: sin quitar acentos, "Alavés"
    # (nombre que devuelve TheSportsDB) y "Alaves" (nombre sin acento que
    # ya usa nuestro calendario sembrado) generaban claves DISTINTAS
    # ("alav s" vs "alaves", la é se sustituia por un espacio en vez de
    # desaparecer) -el partido recien encontrado por eventsround.php se
    # trataba como "hueco" igualmente, disparando una busqueda de backfill
    # innecesaria que ademas trajo un resultado de OTRA temporada (ver
    # obtener_thesportsdb_backfill). Todas las demas funciones de
    # normalizacion de nombres del proyecto ya quitan acentos (NFD); esta
    # se habia quedado atras.
    texto = unicodedata.normalize("NFD", str(nombre or "").strip().lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


# Mapa explicito nombre canonico -> nombre corto de busqueda para los 42
# equipos de Primera/Segunda 26/27. Sustituye al primer intento (quitar
# solo siglas de 2-3 letras al principio, "UD "/"CD "/etc.) -ese primer
# intento solo cubria casos como "UD Almeria" -> "Almeria", pero se
# rompio con "Club Atletico de Madrid" (empieza por "Club ", no estaba en
# la lista de siglas) -bug real confirmado en produccion el 22/08/2026,
# Atletico-Malaga desaparecio del calendario aunque el partido ya estaba
# jugado y cerrado. Con nombres tan variados (siglas al principio, "Club "
# al principio, "de <ciudad>" en medio, sufijos "CF"/"UD"...) un mapa
# cerrado y explicito es mas fiable que seguir afinando una regla generica.
NOMBRES_BUSQUEDA_CORTA = {
    # Primera
    "Deportivo Alaves": "Alaves",
    "Club Atletico de Madrid": "Atletico Madrid",
    "CA Osasuna": "Osasuna",
    "Elche CF": "Elche",
    "FC Barcelona": "Barcelona",
    "Getafe CF": "Getafe",
    "Levante UD": "Levante",
    "Malaga CF": "Malaga",
    "RC Celta de Vigo": "Celta Vigo",
    "RC Deportivo de La Coruna": "Deportivo La Coruna",
    "RCD Espanyol de Barcelona": "Espanyol",
    "Rayo Vallecano de Madrid": "Rayo Vallecano",
    "Real Betis Balompie": "Real Betis",
    "Real Madrid CF": "Real Madrid",
    "Real Racing Club de Santander": "Racing Santander",
    "Real Sociedad de Futbol": "Real Sociedad",
    "Sevilla FC": "Sevilla",
    "Valencia CF": "Valencia",
    "Villarreal CF": "Villarreal",
    # Segunda
    "AD Ceuta FC": "Ceuta",
    "Albacete Balompie": "Albacete",
    "Burgos CF": "Burgos",
    "CD Castellon": "Castellon",
    "CD Eldense": "Eldense",
    "CD Leganes": "Leganes",
    "CD Tenerife": "Tenerife",
    "CE Sabadell": "Sabadell",
    "Cadiz CF": "Cadiz",
    "Cordoba CF": "Cordoba",
    "FC Andorra": "Andorra",
    "Girona FC": "Girona",
    "Granada CF": "Granada",
    "RC Celta Fortuna": "Celta Fortuna",
    "RCD Mallorca": "Mallorca",
    "Real Sporting de Gijon": "Sporting de Gijon",
    "Real Valladolid CF": "Real Valladolid",
    "SD Eibar": "Eibar",
    "UD Almeria": "Almeria",
    "UD Las Palmas": "Las Palmas",
}

# Respaldo generico por si aparece un equipo nuevo (ascenso/descenso de
# temporada futura) que todavia no este en NOMBRES_BUSQUEDA_CORTA -mismo
# criterio de siglas al principio que el primer intento, mejor que nada.
_PREFIJOS_CLUB_BUSQUEDA = ("UD ", "CD ", "CF ", "RCD ", "RC ", "SD ", "AD ", "FC ")


def _nombre_busqueda_corto(nombre):
    texto = str(nombre or "").strip()
    if texto in NOMBRES_BUSQUEDA_CORTA:
        return NOMBRES_BUSQUEDA_CORTA[texto]
    for prefijo in _PREFIJOS_CLUB_BUSQUEDA:
        if texto.startswith(prefijo):
            return texto[len(prefijo):].strip()
    return texto


def pares_esperados_calendario(nombre_liga, rondas):
    """Partidos que DEBERIAN existir en las rondas indicadas, segun el
    calendario oficial ya sembrado (ver CALENDARIO_SEMBRADO)."""
    path = CALENDARIO_SEMBRADO.get(nombre_liga)
    if not path:
        return []
    data = _cargar_json_local(path, {})
    pares = []
    for jornada in data.get("jornadas", []):
        try:
            num = int(jornada.get("jornada", 0))
        except (TypeError, ValueError):
            continue
        if num not in rondas:
            continue
        for p in jornada.get("partidos", []):
            local, visitante = p.get("local"), p.get("visitante")
            if local and visitante:
                pares.append((local, visitante))
    return pares


def obtener_thesportsdb_backfill(nombre_liga, rondas, ya_obtenidos):
    """Respaldo puntual via searchevents.php para partidos que
    eventsround.php no devuelve en absoluto, aunque el calendario oficial
    diga que existen en esa ronda. Confirmado en vivo (22/08/2026) que esto
    no es solo cosa de aplazamientos (el caso original, Atletico-Malaga
    19/08): 6 de los 11 partidos de la Jornada 1 de Segunda tambien faltan
    en eventsround.php sin haberse aplazado nunca -TheSportsDB simplemente
    no devuelve la ronda completa, sin patron claro. Por eso esto compara
    contra el calendario oficial YA SEMBRADO en vez de mantener una lista
    de casos concretos a mano (el enfoque anterior, que no habria cubierto
    este caso de Segunda). Solo se pregunta por pares que eventsround.php
    NO MENCIONO en absoluto -los que si aparecen pero siguen sin jugarse
    (resultado null) no se repiten, para no gastar llamadas de mas cada
    ciclo en partidos que de verdad estan pendientes."""
    esperados = pares_esperados_calendario(nombre_liga, rondas)
    if not esperados:
        return []
    ya_claves = {
        (_clave_equipo(r["local"]), _clave_equipo(r["visitante"]))
        for r in ya_obtenidos
    }
    faltantes = [
        (local, visitante) for local, visitante in esperados
        if (_clave_equipo(local), _clave_equipo(visitante)) not in ya_claves
    ]
    resultados = []
    for local, visitante in faltantes:
        # searchevents.php es muy literal: "UD Almeria vs CD Eldense" (los
        # nombres canonicos, con siglas de club delante) no encuentra nada,
        # pero "Almeria vs Eldense" (sin siglas) si -confirmado en vivo
        # (22/08/2026). Se prueba primero la version corta (la que
        # funciona), y si no hay nada se reintenta con el nombre completo
        # por si algun otro par necesita justo lo contrario.
        for consulta in (
            f"{_nombre_busqueda_corto(local)} vs {_nombre_busqueda_corto(visitante)}",
            f"{local} vs {visitante}",
        ):
            try:
                r = requests.get(
                    "https://www.thesportsdb.com/api/v1/json/3/searchevents.php",
                    params={"e": consulta},
                    headers=HEADERS,
                    timeout=15,
                )
                if r.status_code == 200:
                    eventos = r.json().get("event") or []
                    # searchevents.php busca por nombre de equipo SIN
                    # acotar temporada -dos equipos que llevan años
                    # enfrentandose devuelven varios partidos historicos a
                    # la vez. Bug real confirmado el 29/08/2026: "Alaves vs
                    # Villarreal" trajo (ademas del partido real de esta
                    # temporada) uno de 2024 con marcador distinto, y al
                    # extender sin filtrar los dos quedaron mezclados en
                    # resultados_libres.json. Quedarse solo con la
                    # temporada actual antes de aceptar el evento.
                    eventos = [e for e in eventos if e.get("strSeason") == TEMPORADA_THESPORTSDB]
                    if eventos:
                        resultados.extend(_parsear_eventos_thesportsdb(nombre_liga, eventos))
                        break
            except Exception as e:
                print(f"  TheSportsDB backfill {nombre_liga} {local}-{visitante}: {e}")
    return resultados


def obtener_thesportsdb():
    print("TheSportsDB: consultando ligas...")
    todos = []
    por_ronda = {}
    rondas_por_liga = {nombre: rondas_a_consultar(nombre) for nombre in LIGAS_CON_JORNADAS}
    for nombre, lid in THESPORTSDB_LIGAS.items():
        if nombre in LIGAS_CON_JORNADAS:
            partidos = obtener_thesportsdb_por_rondas(nombre, lid, rondas_por_liga[nombre])
            por_ronda[nombre] = partidos
        else:
            partidos = obtener_thesportsdb_liga(nombre, lid)
        print(f"  {nombre}: {len(partidos)} partidos")
        todos.extend(partidos)
    for nombre in LIGAS_CON_JORNADAS:
        print(f"  {nombre}: rondas consultadas {rondas_por_liga[nombre]}")
        backfill = obtener_thesportsdb_backfill(nombre, rondas_por_liga[nombre], por_ronda.get(nombre, []))
        if backfill:
            print(f"  {nombre} (backfill huecos de ronda): {len(backfill)} partidos")
        todos.extend(backfill)
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
