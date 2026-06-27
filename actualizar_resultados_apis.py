import json, os, re, requests, time
from datetime import datetime, timezone, timedelta, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
RESULTADOS_MUNDIAL = DATA / "mundial_2026_resultados.json"

TZ = ZoneInfo("Europe/Madrid")
MARGEN = timedelta(minutes=105)

BALLDONTLIE_KEY = os.environ.get("BALLDONTLIE_API_KEY", "")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "")
FOOTBALL_DATA_KEY = os.environ.get("FOOTBALL_DATA_KEY", "")

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
    "bosnia and herzegovina": "bosnia", "bosnia herzegovina": "bosnia",
    "czechia": "chequia", "czech republic": "chequia",
    "republic of ireland": "irlanda", "northern ireland": "irlanda del norte",
    "türkiye": "turquía", "côte d'ivoire": "costa de marfil",
    "islamic republic of iran": "irán", "ir iran": "irán",
    "dem. rep. congo": "congo dr", "congo, dr": "congo dr",
}

def norm(nombre):
    n = str(nombre or "").strip().lower()
    return ALIAS.get(n, n)

def signo(resultado):
    try:
        g1, g2 = [int(x) for x in resultado.split("-")]
        return "1" if g1 > g2 else "X" if g1 == g2 else "2"
    except:
        return ""

def partido_terminado(fecha_txt, hora_txt):
    try:
        fecha = datetime.fromisoformat(str(fecha_txt)).date()
        m = re.match(r"^(\d{1,2}):(\d{2})$", str(hora_txt or ""))
        if not m:
            return fecha < datetime.now(TZ).date()
        hora = dt_time(int(m.group(1)), int(m.group(2)))
        inicio = datetime.combine(fecha, hora, TZ)
        return inicio + MARGEN <= datetime.now(TZ)
    except:
        return False

# ═══════════════════════════════════════
# FUENTE 1: BallDontLie
# ═══════════════════════════════════════
def obtener_balldontlie():
    if not BALLDONTLIE_KEY:
        print("BallDontLie: sin key")
        return []
    try:
        headers = {"Authorization": BALLDONTLIE_KEY}
        r = requests.get(
            "https://api.balldontlie.io/fifa/worldcup/v1/matches",
            headers=headers, timeout=20
        )
        if r.status_code != 200:
            print(f"BallDontLie error: {r.status_code}")
            return []
        partidos = r.json().get("data", [])
        resultados = []
        for p in partidos:
            home_score = p.get("home_score")
            away_score = p.get("away_score")
            if home_score is None or away_score is None:
                continue
            status = p.get("status", "")
            if status not in ("completed", "FT", "AET", "PEN", "finished", "FINISHED"):
                continue
            resultado = f"{int(home_score)}-{int(away_score)}"
            home = p.get("home_team") or {}
            away = p.get("away_team") or {}
            local = norm(home.get("name", ""))
            visitante = norm(away.get("name", ""))
            grupo = (p.get("group") or {}).get("name", "").replace("Group ", "")
            if not local or not visitante:
                continue
            resultados.append({
                "local": local, "visitante": visitante,
                "resultado": resultado, "grupo": grupo,
                "fuente": "balldontlie", "confianza": "confirmado",
                "actualizado_en": datetime.now(timezone.utc).isoformat()
            })
        print(f"BallDontLie: {len(resultados)} resultados")
        return resultados
    except Exception as e:
        print(f"BallDontLie error: {e}")
        return []

# ═══════════════════════════════════════
# FUENTE 2: football-data.org
# ═══════════════════════════════════════
def obtener_football_data():
    if not FOOTBALL_DATA_KEY:
        print("football-data.org: sin key")
        return []
    try:
        headers = {"X-Auth-Token": FOOTBALL_DATA_KEY}
        r = requests.get(
            "https://api.football-data.org/v4/competitions/WC/matches?season=2026",
            headers=headers, timeout=20
        )
        if r.status_code != 200:
            print(f"football-data.org error: {r.status_code}")
            return []
        matches = r.json().get("matches", [])
        resultados = []
        for m in matches:
            status = m.get("status", "")
            if status != "FINISHED":
                continue
            score = m.get("score", {})
            ft = score.get("fullTime", {})
            home_goals = ft.get("home")
            away_goals = ft.get("away")
            if home_goals is None or away_goals is None:
                continue
            resultado = f"{int(home_goals)}-{int(away_goals)}"
            home = m.get("homeTeam", {})
            away = m.get("awayTeam", {})
            local = norm(home.get("name", "") or home.get("shortName", ""))
            visitante = norm(away.get("name", "") or away.get("shortName", ""))
            grupo = str(m.get("group", "") or "").replace("GROUP_", "")
            if not local or not visitante:
                continue
            resultados.append({
                "local": local, "visitante": visitante,
                "resultado": resultado, "grupo": grupo,
                "fuente": "football-data.org", "confianza": "confirmado",
                "actualizado_en": datetime.now(timezone.utc).isoformat()
            })
        print(f"football-data.org: {len(resultados)} resultados")
        return resultados
    except Exception as e:
        print(f"football-data.org error: {e}")
        return []

# ═══════════════════════════════════════
# FUENTE 3: openfootball (sin key, GitHub)
# ═══════════════════════════════════════
def obtener_openfootball():
    try:
        url = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            print(f"openfootball error: {r.status_code}")
            return []
        data = r.json()
        resultados = []
        for ronda in data.get("rounds", []):
            for match in ronda.get("matches", []):
                score = match.get("score", {})
                ft = score.get("ft", [])
                if not ft or len(ft) < 2:
                    continue
                resultado = f"{ft[0]}-{ft[1]}"
                local = norm(match.get("team1", {}).get("name", ""))
                visitante = norm(match.get("team2", {}).get("name", ""))
                grupo = str(match.get("group", "")).replace("Group ", "")
                if not local or not visitante:
                    continue
                resultados.append({
                    "local": local, "visitante": visitante,
                    "resultado": resultado, "grupo": grupo,
                    "fuente": "openfootball", "confianza": "confirmado",
                    "actualizado_en": datetime.now(timezone.utc).isoformat()
                })
        print(f"openfootball: {len(resultados)} resultados")
        return resultados
    except Exception as e:
        print(f"openfootball error: {e}")
        return []

# ═══════════════════════════════════════
# FUENTE 4: API-Football
# ═══════════════════════════════════════
def obtener_api_football():
    if not API_FOOTBALL_KEY:
        print("API-Football: sin key")
        return []
    try:
        headers = {"x-apisports-key": API_FOOTBALL_KEY}
        r = requests.get(
            "https://v3.football.api-sports.io/fixtures",
            headers=headers,
            params={"league": "1", "season": "2026", "status": "FT"},
            timeout=20
        )
        if r.status_code != 200:
            print(f"API-Football error: {r.status_code}")
            return []
        fixtures = r.json().get("response", [])
        resultados = []
        for f in fixtures:
            goals = f.get("goals", {})
            home_goals = goals.get("home")
            away_goals = goals.get("away")
            if home_goals is None or away_goals is None:
                continue
            resultado = f"{int(home_goals)}-{int(away_goals)}"
            teams = f.get("teams", {})
            local = norm(teams.get("home", {}).get("name", ""))
            visitante = norm(teams.get("away", {}).get("name", ""))
            liga = f.get("league", {})
            grupo = str(liga.get("round", "") or "").replace("Group Stage - ", "")
            if not local or not visitante:
                continue
            resultados.append({
                "local": local, "visitante": visitante,
                "resultado": resultado, "grupo": grupo,
                "fuente": "api-football", "confianza": "confirmado",
                "actualizado_en": datetime.now(timezone.utc).isoformat()
            })
        print(f"API-Football: {len(resultados)} resultados")
        return resultados
    except Exception as e:
        print(f"API-Football error: {e}")
        return []

def actualizar():
    # Cargar existentes
    try:
        with open(RESULTADOS_MUNDIAL, encoding="utf-8") as f:
            data_mundial = json.load(f)
    except:
        data_mundial = {"version": "1.0", "resultados": [], "actualizado_en": ""}

    indice = {
        (r.get("local","").lower(), r.get("visitante","").lower()): r
        for r in data_mundial.get("resultados", [])
    }

    # Recoger de TODAS las fuentes y combinar
    todas_fuentes = [
        obtener_balldontlie,
        obtener_football_data,
        obtener_openfootball,
        obtener_api_football,
    ]
    
    cambios = 0
    for fuente_fn in todas_fuentes:
        try:
            resultados = fuente_fn()
            for r in resultados:
                clave = (r["local"], r["visitante"])
                if clave not in indice:
                    indice[clave] = r
                    cambios += 1
                    print(f"  Nuevo: {r['local']} vs {r['visitante']} → {r['resultado']} ({r['fuente']})")
                elif indice[clave].get("resultado") != r["resultado"]:
                    # Actualizar si el resultado cambió
                    indice[clave] = r
                    cambios += 1
                    print(f"  Actualizado: {r['local']} vs {r['visitante']} → {r['resultado']} ({r['fuente']})")
        except Exception as e:
            print(f"Error en fuente {fuente_fn.__name__}: {e}")
        time.sleep(0.5)

    # Actualizar jornadas pendientes
    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data = json.load(open(path, encoding="utf-8"))
        partidos = data.get("partidos", [])
        cambios_j = 0
        for p in partidos:
            resultado_actual = p.get("resultado", "Pendiente")
            if resultado_actual != "Pendiente" and re.match(r"^\d+-\d+$", str(resultado_actual)):
                continue
            if not partido_terminado(p.get("fecha"), p.get("hora")):
                continue
            local = p.get("local", "")
            visitante = p.get("visitante", "")
            if not local or not visitante:
                continue
            if "grupo" in local.lower() or "º" in local:
                continue
            clave = (norm(local), norm(visitante))
            if clave in indice:
                r = indice[clave]
                p["resultado"] = r["resultado"]
                p["signo_oficial"] = signo(r["resultado"])
                p["fuente_resultado"] = r.get("fuente", "api")
                cambios_j += 1
                cambios += 1
                print(f"  J{data.get('jornada')} [{p['num']}] {local} vs {visitante}: {r['resultado']}")
        if cambios_j:
            todos = all(
                re.match(r"^\d+-\d+$", str(p.get("resultado","")))
                for p in partidos
            )
            data["estado"] = "cerrada" if todos else "en_juego"
            data["actualizado_en"] = datetime.now(timezone.utc).isoformat()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    # Guardar mundial actualizado
    data_mundial["resultados"] = list(indice.values())
    data_mundial["actualizado_en"] = datetime.now(timezone.utc).isoformat()
    with open(RESULTADOS_MUNDIAL, "w", encoding="utf-8") as f:
        json.dump(data_mundial, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Total cambios: {cambios}")
    return cambios

if __name__ == "__main__":
    actualizar()
