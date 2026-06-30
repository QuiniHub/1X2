"""
Actualiza el cuadro eliminatorio del Mundial 2026.
Fuentes en orden de prioridad:
  1. API-Football (api-football.com) — más fiable para resultados en tiempo real
  2. Football-Data.org — segunda fuente de verificación
  3. BallDontLie — tercera opción
  4. Tavily — SOLO para partidos donde las 3 APIs no tienen datos, y SOLO
               para encontrar el marcador exacto (no acepta respuestas ambiguas)
Si ninguna fuente confirma un resultado, el partido queda como pendiente.
NUNCA se escribe un resultado no confirmado por al menos una API real.
"""
import json, os, re, requests, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
CUADRO = DATA / "mundial_2026_cuadro_eliminatorio.json"
ELIMINATORIAS = DATA / "mundial_2026_eliminatorias.json"
CLASIFICACIONES = DATA / "memoria_ia" / "clasificaciones_mundial_2026.json"

BALLDONTLIE_KEY  = os.environ.get("BALLDONTLIE_API_KEY", "")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "")
FOOTBALL_DATA_KEY = os.environ.get("FOOTBALL_DATA_KEY", "")
TAVILY_KEY       = os.environ.get("TAVILY_API_KEY", "")

# TheSportsDB no necesita key — usa el endpoint público gratuito
THESPORTSDB_KEY = "3"
# IDs conocidos de FIFA World Cup en TheSportsDB (se prueban en orden)
THESPORTSDB_WC_IDS = ["600614", "4480", "4479"]

# ID de la competición Mundial 2026 en cada API
API_FOOTBALL_LEAGUE = 1  # FIFA World Cup en api-football.com
API_FOOTBALL_SEASON = 2026
FOOTBALL_DATA_COMPETITION = "WC"  # World Cup en football-data.org

ALIAS = {
    "iran": "irán", "turkey": "turquía", "turkiye": "turquía",
    "belgium": "bélgica", "new zealand": "nueva zelanda",
    "netherlands": "países bajos", "usa": "estados unidos",
    "united states": "estados unidos", "south korea": "corea del sur",
    "ivory coast": "costa de marfil", "cape verde": "cabo verde",
    "saudi arabia": "arabia saudí", "morocco": "marruecos",
    "germany": "alemania", "france": "francia", "spain": "españa",
    "england": "inglaterra", "croatia": "croacia", "switzerland": "suiza",
    "sweden": "suecia", "norway": "noruega", "portugal": "portugal",
    "argentina": "argentina", "brazil": "brasil", "mexico": "méxico",
    "colombia": "colombia", "ecuador": "ecuador", "uruguay": "uruguay",
    "paraguay": "paraguay", "senegal": "senegal", "ghana": "ghana",
    "egypt": "egipto", "algeria": "argelia", "tunisia": "túnez",
    "australia": "australia", "japan": "japón", "south africa": "sudáfrica",
    "panama": "panamá", "iraq": "irak", "jordan": "jordania",
    "canada": "canadá", "scotland": "escocia", "haiti": "haití",
    "uzbekistan": "uzbekistán", "austria": "austria", "curacao": "curazao",
    "rd congo": "congo dr", "democratic republic of congo": "congo dr",
    "costa rica": "costa rica", "serbia": "serbia",
    "cote d'ivoire": "costa de marfil", "côte d'ivoire": "costa de marfil",
    "bosnia and herzegovina": "bosnia-herzegovina",
    "bosnia & herzegovina": "bosnia-herzegovina",
    "dr congo": "rd congo", "congo, dr": "rd congo",
    "cabo verde": "cabo verde",
}

def norm(nombre):
    n = str(nombre or "").strip().lower()
    return ALIAS.get(n, n)

def norm_titulo(nombre):
    n = norm(nombre)
    return n.title() if n else ""

# ─── FUENTE 0: TheSportsDB (sin key, gratuito) ────────────────────────────────

def obtener_thesportsdb():
    """Obtiene partidos del Mundial 2026 desde TheSportsDB — sin API key."""
    for league_id in THESPORTSDB_WC_IDS:
        try:
            r = requests.get(
                "https://www.thesportsdb.com/api/v1/json/3/eventsseason.php",
                params={"id": league_id, "s": "2026"},
                timeout=20,
            )
            if r.status_code != 200:
                continue
            events = r.json().get("events") or []
            if not events:
                continue
            print(f"TheSportsDB: {len(events)} eventos (league {league_id})")
            resultados = []
            for e in events:
                stage = str(e.get("strRound") or e.get("intRound") or "")
                if "group" in stage.lower() or "fase de grupos" in stage.lower():
                    continue
                home = norm(e.get("strHomeTeam", ""))
                away = norm(e.get("strAwayTeam", ""))
                hg = e.get("intHomeScore")
                ag = e.get("intAwayScore")
                status = str(e.get("strStatus") or e.get("strProgress") or "")
                terminado = status in ("Match Finished", "FT", "finished", "AOT", "AP")
                resultado = None
                ganador = None
                if terminado and hg is not None and ag is not None:
                    try:
                        hg_i, ag_i = int(hg), int(ag)
                        resultado = f"{hg_i}-{ag_i}"
                        if hg_i > ag_i:
                            ganador = home
                        elif ag_i > hg_i:
                            ganador = away
                    except (ValueError, TypeError):
                        pass
                fecha = e.get("dateEvent") or ""
                resultados.append({
                    "local": home, "visitante": away,
                    "resultado": resultado, "ganador": ganador,
                    "fecha": fecha, "ronda": stage, "fuente": "thesportsdb",
                })
            return resultados
        except Exception as e:
            print(f"TheSportsDB excepción (league {league_id}): {e}")
    print("TheSportsDB: sin datos")
    return []


# ─── FUENTE 1: API-Football ────────────────────────────────────────────────────

def obtener_api_football():
    """Obtiene partidos eliminatorios del Mundial 2026 desde api-football.com o RapidAPI."""
    if not API_FOOTBALL_KEY:
        print("Sin API_FOOTBALL_KEY")
        return []
    try:
        # Detectar si es key de RapidAPI (contiene 'jsn') o key directa de api-sports.io
        is_rapidapi = "jsn" in API_FOOTBALL_KEY
        if is_rapidapi:
            headers = {
                "X-RapidAPI-Key": API_FOOTBALL_KEY,
                "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com",
            }
            base_url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        else:
            headers = {"x-apisports-key": API_FOOTBALL_KEY}
            base_url = "https://v3.football.api-sports.io/fixtures"
        r = requests.get(
            base_url,
            headers=headers,
            params={
                "league": API_FOOTBALL_LEAGUE,
                "season": API_FOOTBALL_SEASON,
            },
            timeout=20,
        )
        if r.status_code != 200:
            print(f"API-Football error {r.status_code}")
            return []
        fixtures = r.json().get("response", [])
        print(f"API-Football: {len(fixtures)} partidos obtenidos")
        resultados = []
        for f in fixtures:
            ronda = (f.get("league") or {}).get("round", "")
            # Solo fases eliminatorias
            if any(x in ronda.lower() for x in ["group", "grupo"]):
                continue
            equipos = f.get("teams", {})
            goles = f.get("goals", {})
            fixture = f.get("fixture", {})
            status = (fixture.get("status") or {}).get("short", "")
            home = norm(equipos.get("home", {}).get("name", ""))
            away = norm(equipos.get("away", {}).get("name", ""))
            home_g = goles.get("home")
            away_g = goles.get("away")
            fecha = (fixture.get("date") or "")[:10]
            terminado = status in ("FT", "AET", "PEN")
            resultado = f"{home_g}-{away_g}" if terminado and home_g is not None and away_g is not None else None
            ganador = None
            if resultado:
                if home_g > away_g:
                    ganador = home
                elif away_g > home_g:
                    ganador = away
                # empate en tiempo normal → puede haber penaltis
                elif status == "PEN":
                    pen = f.get("score", {}).get("penalty", {})
                    ph = pen.get("home")
                    pa = pen.get("away")
                    if ph is not None and pa is not None:
                        ganador = home if ph > pa else away
            resultados.append({
                "local": home, "visitante": away,
                "resultado": resultado, "ganador": ganador,
                "fecha": fecha, "ronda": ronda, "fuente": "api-football",
            })
        return resultados
    except Exception as e:
        print(f"API-Football excepción: {e}")
        return []


# ─── FUENTE 2: Football-Data.org ──────────────────────────────────────────────

def obtener_football_data():
    """Obtiene partidos eliminatorios del Mundial 2026 desde football-data.org."""
    if not FOOTBALL_DATA_KEY:
        print("Sin FOOTBALL_DATA_KEY")
        return []
    try:
        headers = {"X-Auth-Token": FOOTBALL_DATA_KEY}
        r = requests.get(
            f"https://api.football-data.org/v4/competitions/{FOOTBALL_DATA_COMPETITION}/matches",
            headers=headers,
            params={"season": API_FOOTBALL_SEASON},
            timeout=20,
        )
        if r.status_code != 200:
            print(f"Football-Data error {r.status_code}")
            return []
        matches = r.json().get("matches", [])
        print(f"Football-Data: {len(matches)} partidos obtenidos")
        resultados = []
        for m in matches:
            stage = m.get("stage", "")
            if stage in ("GROUP_STAGE", "PRELIMINARY_ROUND"):
                continue
            home = norm((m.get("homeTeam") or {}).get("name", ""))
            away = norm((m.get("awayTeam") or {}).get("name", ""))
            score = m.get("score", {})
            full = score.get("fullTime", {})
            hg = full.get("home")
            ag = full.get("away")
            status = m.get("status", "")
            terminado = status in ("FINISHED",)
            resultado = f"{hg}-{ag}" if terminado and hg is not None and ag is not None else None
            ganador = None
            if resultado:
                winner = score.get("winner")
                if winner == "HOME_TEAM":
                    ganador = home
                elif winner == "AWAY_TEAM":
                    ganador = away
            fecha = (m.get("utcDate") or "")[:10]
            resultados.append({
                "local": home, "visitante": away,
                "resultado": resultado, "ganador": ganador,
                "fecha": fecha, "ronda": stage, "fuente": "football-data",
            })
        return resultados
    except Exception as e:
        print(f"Football-Data excepción: {e}")
        return []


# ─── FUENTE 3: BallDontLie ────────────────────────────────────────────────────

STAGE_MAP = {
    "Round of 32": "dieciseisavos",
    "Round of 16": "octavos",
    "Quarter-finals": "cuartos",
    "Semi-finals": "semifinales",
    "Final": "final",
}

def traducir_source(source):
    if not source:
        return None
    tipo = source.get("type", "")
    desc = source.get("description", "") or source.get("label", "")
    grupo = (source.get("group") or {}).get("name", "")
    letra = grupo.replace("Group ", "").strip() if grupo else ""
    if tipo in ("group_winner", "winner"):
        return f"1º Grupo {letra}" if letra else None
    elif tipo in ("group_runner_up", "runner_up"):
        return f"2º Grupo {letra}" if letra else None
    return None

def resolver_equipo_bdl(partido, campo):
    equipo = partido.get(campo)
    if equipo and equipo.get("name"):
        return norm(equipo["name"])
    source = partido.get(f"{campo}_source")
    return traducir_source(source)

def obtener_balldontlie():
    if not BALLDONTLIE_KEY:
        print("Sin BALLDONTLIE_API_KEY")
        return []
    try:
        headers = {"Authorization": BALLDONTLIE_KEY}
        r = requests.get(
            "https://api.balldontlie.io/fifa/worldcup/v1/matches",
            headers=headers, timeout=20,
        )
        if r.status_code != 200:
            print(f"BallDontLie error {r.status_code}")
            return []
        partidos = r.json().get("data", [])
        print(f"BallDontLie: {len(partidos)} partidos obtenidos")
        resultados = []
        for p in partidos:
            stage_en = (p.get("stage") or {}).get("name", "")
            if "Group" in stage_en:
                continue
            local = resolver_equipo_bdl(p, "home_team")
            visitante = resolver_equipo_bdl(p, "away_team")
            hg = p.get("home_score")
            ag = p.get("away_score")
            terminado = p.get("status", "") in ("finished", "completed", "FT")
            resultado = f"{hg}-{ag}" if terminado and hg is not None and ag is not None else None
            ganador = None
            if resultado and hg is not None and ag is not None:
                if hg > ag:
                    ganador = local
                elif ag > hg:
                    ganador = visitante
            dt = (p.get("datetime") or "")[:10]
            resultados.append({
                "local": local, "visitante": visitante,
                "resultado": resultado, "ganador": ganador,
                "fecha": dt, "ronda": stage_en,
                "match_number": p.get("match_number"),
                "fuente": "balldontlie",
            })
        return resultados
    except Exception as e:
        print(f"BallDontLie excepción: {e}")
        return []


# ─── FUSIÓN DE FUENTES ────────────────────────────────────────────────────────

def fusionar_resultados(listas):
    """
    Combina resultados de varias APIs. Para cada partido (local+visitante),
    acepta el resultado SOLO si al menos una API lo confirma como terminado.
    Si dos APIs difieren en el marcador, prevalece API-Football > Football-Data > BallDontLie.
    """
    index = {}  # clave: (norm(local), norm(visitante)) → mejor resultado
    prioridad = {"api-football": 0, "football-data": 1, "thesportsdb": 2, "balldontlie": 3}

    for lista in listas:
        for r in lista:
            local = norm(r.get("local") or "")
            visitante = norm(r.get("visitante") or "")
            if not local or not visitante:
                continue
            if "grupo" in local or "grupo" in visitante:
                continue  # placeholder, no es equipo real
            clave = (local, visitante)
            clave_inv = (visitante, local)
            # Normalizar al orden canónico
            k = clave if clave in index or clave_inv not in index else clave_inv
            if k == clave_inv:
                # Invertir local/visitante
                local, visitante = visitante, local
                r = dict(r, local=local, visitante=visitante)
                if r.get("resultado"):
                    g, v = r["resultado"].split("-")
                    r["resultado"] = f"{v}-{g}"
                    if r.get("ganador"):
                        pass  # ganador ya está normalizado
            fuente_prio = prioridad.get(r.get("fuente", ""), 99)
            if k not in index:
                index[k] = dict(r, _prio=fuente_prio)
            else:
                prev = index[k]
                # Actualizar si tenemos resultado y el anterior no, o somos más prioritarios
                tiene_res = bool(r.get("resultado"))
                prev_res = bool(prev.get("resultado"))
                if tiene_res and (not prev_res or fuente_prio < prev.get("_prio", 99)):
                    index[k] = dict(r, _prio=fuente_prio)
                elif tiene_res and prev_res and fuente_prio == prev.get("_prio", 99):
                    pass  # mismo prioridad, mantener
    return list(index.values())


# ─── ACTUALIZAR JSON ELIMINATORIAS ────────────────────────────────────────────

def cargar_eliminatorias():
    if ELIMINATORIAS.exists():
        try:
            return json.loads(ELIMINATORIAS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def guardar_eliminatorias(data):
    data["actualizado_en"] = datetime.now(timezone.utc).isoformat()
    ELIMINATORIAS.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

def actualizar_desde_fusionados(fusionados, elim):
    """Actualiza el JSON de eliminatorias con los resultados fusionados de las APIs."""
    cambios = 0
    rondas = elim.get("rondas", {})

    for r in fusionados:
        if not r.get("resultado"):
            continue  # solo partidos terminados
        local_api = norm(r["local"])
        visitante_api = norm(r["visitante"])
        resultado = r["resultado"]
        ganador = r.get("ganador")

        for ronda_key, ronda_data in rondas.items():
            for m in ronda_data.get("partidos", []):
                local_json = norm(m.get("local") or "")
                visitante_json = norm(m.get("visitante") or "")
                if not local_json or not visitante_json:
                    continue
                if local_json == local_api and visitante_json == visitante_api:
                    if m.get("resultado") != resultado:
                        m["resultado"] = resultado
                        m["ganador"] = ganador
                        print(f"  ✓ {m['local']} {resultado} {m['visitante']} (fuente: {r.get('fuente')})")
                        cambios += 1
                    break
    return cambios


# ─── TAVILY: SOLO PARA PARTIDOS SIN RESULTADO CONFIRMADO ──────────────────────

def parse_marcador_estricto(texto, local, visitante):
    """
    Busca un marcador SOLO si aparece exactamente junto al nombre del equipo.
    Rechaza resultados ambiguos. Devuelve (goles_local, goles_visitante) o None.
    """
    local_n = norm(local).split()[0]   # primera palabra del equipo
    visit_n = norm(visitante).split()[0]
    texto_n = texto.lower()

    # Buscar patrón "equipo X-Y equipo" o "equipo X equipo Y"
    patrones = [
        rf"{re.escape(local_n)}\s+(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})\s+{re.escape(visit_n)}",
        rf"{re.escape(visit_n)}\s+(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})\s+{re.escape(local_n)}",
    ]
    for i, pat in enumerate(patrones):
        m = re.search(pat, texto_n)
        if m:
            g1, g2 = int(m.group(1)), int(m.group(2))
            if i == 0:
                return g1, g2
            else:
                return g2, g1  # invertir si visitante aparece primero
    return None

def buscar_tavily_partido(local, visitante, fecha):
    """Busca el resultado de UN partido concreto en Tavily."""
    if not TAVILY_KEY:
        return None
    query = f"{local} vs {visitante} resultado Mundial 2026 {fecha}"
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 5,
                "include_answer": True,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        texto = (data.get("answer") or "") + " " + " ".join(
            r.get("content", "") for r in data.get("results", [])
        )
        marcador = parse_marcador_estricto(texto, local, visitante)
        if marcador:
            gl, gv = marcador
            ganador = local if gl > gv else (visitante if gv > gl else None)
            print(f"  Tavily (verificado): {local} {gl}-{gv} {visitante}")
            return {"resultado": f"{gl}-{gv}", "ganador": ganador}
        else:
            print(f"  Tavily: no encontró marcador claro para {local} vs {visitante}")
            return None
    except Exception as e:
        print(f"  Tavily excepción: {e}")
        return None

def completar_con_tavily(elim):
    """Solo usa Tavily para partidos cuya fecha ya pasó y no tienen resultado."""
    hoy = datetime.now(timezone.utc).date()
    cambios = 0
    for ronda_key, ronda_data in elim.get("rondas", {}).items():
        for m in ronda_data.get("partidos", []):
            if m.get("resultado"):
                continue  # ya tiene resultado, no tocar
            if not m.get("local") or not m.get("visitante"):
                continue  # equipos no conocidos aún
            fecha_str = m.get("fecha", "")
            if not fecha_str:
                continue
            try:
                fecha_partido = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except ValueError:
                continue
            # Solo buscar si el partido fue hace más de 2 horas (margen de seguridad)
            if fecha_partido >= hoy:
                continue
            resultado = buscar_tavily_partido(m["local"], m["visitante"], fecha_str)
            if resultado:
                m["resultado"] = resultado["resultado"]
                m["ganador"] = resultado["ganador"]
                cambios += 1
            time.sleep(1)  # respetar rate limit de Tavily
    return cambios


# ─── PROPAGAR GANADORES AL SIGUIENTE ROUND ────────────────────────────────────

def propagar_ganadores(elim):
    rondas = elim.get("rondas", {})
    pairings = elim.get("bracket_pairings", {})
    match_by_id = {}
    for ronda in rondas.values():
        for m in ronda.get("partidos", []):
            match_by_id[str(m["id"])] = m

    cambios = 0
    for ronda_key in ["octavos", "cuartos", "semifinales", "final"]:
        for pair in pairings.get(ronda_key, []):
            dest_id = pair["id"]
            src_ids = [str(x) for x in pair["de"]]
            dest = match_by_id.get(dest_id)
            if not dest:
                continue
            src0 = match_by_id.get(src_ids[0])
            src1 = match_by_id.get(src_ids[1])
            if src0 and src0.get("ganador") and dest.get("local") != src0["ganador"]:
                dest["local"] = src0["ganador"]
                cambios += 1
            if src1 and src1.get("ganador") and dest.get("visitante") != src1["ganador"]:
                dest["visitante"] = src1["ganador"]
                cambios += 1
    return cambios


# ─── RESOLVER NOMBRES EN JORNADAS ─────────────────────────────────────────────

def resolver_nombres_jornadas():
    try:
        with open(CLASIFICACIONES, encoding="utf-8") as f:
            clasif = json.load(f)
        grupos = clasif.get("grupos", {})
        indice = {}
        for g_nombre, g_data in grupos.items():
            letra = g_nombre.replace("Grupo ", "").strip()
            equipos = g_data.get("clasificacion", [])
            if len(equipos) >= 1:
                indice[f"1º Grupo {letra}"] = norm(equipos[0].get("equipo", ""))
            if len(equipos) >= 2:
                indice[f"2º Grupo {letra}"] = norm(equipos[1].get("equipo", ""))
    except Exception as e:
        print(f"Error leyendo clasificaciones: {e}")
        return

    cambios_total = 0
    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data = json.load(open(path, encoding="utf-8"))
        partidos = data.get("partidos", [])
        cambios = 0
        for p in partidos:
            for campo in ("local", "visitante"):
                val = p.get(campo, "")
                if ("Grupo" in val or "º" in val) and val in indice and indice[val]:
                    p[campo] = indice[val].title()
                    cambios += 1
        if cambios:
            data["actualizado_en"] = datetime.now(timezone.utc).isoformat()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            cambios_total += cambios
    print(f"Nombres resueltos en jornadas: {cambios_total}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Actualizando cuadro eliminatorio Mundial 2026 ===")

    elim = cargar_eliminatorias()
    if not elim:
        print("ERROR: no se puede cargar mundial_2026_eliminatorias.json")
        exit(1)

    # 1. Obtener datos de todas las fuentes
    lista_thesportsdb = obtener_thesportsdb()
    lista_apifootball = obtener_api_football()
    lista_footballdata = obtener_football_data()
    lista_balldontlie  = obtener_balldontlie()

    total_api = len(lista_thesportsdb) + len(lista_apifootball) + len(lista_footballdata) + len(lista_balldontlie)
    print(f"Total partidos de APIs: {total_api}")

    # 2. Fusionar y priorizar (api-football > football-data > thesportsdb > balldontlie)
    fusionados = fusionar_resultados([lista_apifootball, lista_footballdata, lista_thesportsdb, lista_balldontlie])
    cambios = actualizar_desde_fusionados(fusionados, elim)
    print(f"Actualizados desde APIs reales: {cambios} partido(s)")

    # 3. Propagar ganadores al siguiente round
    cambios += propagar_ganadores(elim)

    # 4. Solo si quedan partidos sin resultado cuya fecha ya pasó → Tavily con verificación estricta
    cambios_tavily = completar_con_tavily(elim)
    if cambios_tavily:
        print(f"Completados con Tavily (verificación estricta): {cambios_tavily}")
        cambios += cambios_tavily
        propagar_ganadores(elim)

    # 5. Guardar si hubo cambios
    if cambios:
        guardar_eliminatorias(elim)
        print(f"Eliminatorias guardadas: {cambios} cambio(s) totales")
    else:
        print("Sin cambios nuevos")

    # 6. Resolver placeholders en jornadas
    resolver_nombres_jornadas()

    print("=== Completado ===")
