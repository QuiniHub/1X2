import json
import os
import re
import requests
import time
from datetime import datetime, timezone, timedelta, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
RESULTADOS_MUNDIAL = DATA / "mundial_2026_resultados.json"
CLASIFICACIONES = DATA / "memoria_ia" / "clasificaciones_mundial_2026.json"

TZ = ZoneInfo("Europe/Madrid")
MARGEN = timedelta(minutes=105)

BALLDONTLIE_KEY = os.environ.get("BALLDONTLIE_API_KEY", "")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "")

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
    "uzbekistan": "uzbekistán", "congo dr": "congo dr", "austria": "austria",
    "curacao": "curazao", "new zealand": "nueva zelanda",
    "costa rica": "costa rica", "serbia": "serbia",
    "rd congo": "congo dr", "democratic republic of congo": "congo dr",
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

# ═══════════════════════════════════════════
# FUENTE 1: BallDontLie
# ═══════════════════════════════════════════
def obtener_balldontlie():
    if not BALLDONTLIE_KEY:
        print("Sin BALLDONTLIE_API_KEY")
        return []
    resultados = []
    try:
        url = "https://api.balldontlie.io/fifa/worldcup/v1/matches"
        headers = {"Authorization": BALLDONTLIE_KEY}
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            print(f"BallDontLie error: {r.status_code}")
            return []
        data = r.json()
        partidos = data.get("data", [])
        print(f"BallDontLie: {len(partidos)} partidos")
        for p in partidos:
            home_score = p.get("home_score")
            away_score = p.get("away_score")
            if home_score is None or away_score is None:
                continue
            resultado = f"{int(home_score)}-{int(away_score)}"
            home = p.get("home_team", {}) or {}
            away = p.get("away_team", {}) or {}
            local = norm(home.get("name", ""))
            visitante = norm(away.get("name", ""))
            if not local or not visitante:
                continue
            status = p.get("status", "")
            if status not in ("FT", "AET", "PEN", "finished", "FINISHED"):
                continue
            resultados.append({
                "local": local, "visitante": visitante,
                "resultado": resultado,
                "fuente": "balldontlie", "confianza": "confirmado",
                "actualizado_en": datetime.now(timezone.utc).isoformat()
            })
        print(f"BallDontLie: {len(resultados)} resultados confirmados")
    except Exception as e:
        print(f"BallDontLie error: {e}")
    return resultados

# ═══════════════════════════════════════════
# FUENTE 2: API-Football
# ═══════════════════════════════════════════
def obtener_api_football():
    if not API_FOOTBALL_KEY:
        print("Sin API_FOOTBALL_KEY")
        return []
    resultados = []
    try:
        url = "https://v3.football.api-sports.io/fixtures"
        headers = {"x-apisports-key": API_FOOTBALL_KEY}
        params = {"league": "1", "season": "2026", "status": "FT"}
        r = requests.get(url, headers=headers, params=params, timeout=20)
        if r.status_code != 200:
            print(f"API-Football error: {r.status_code}")
            return []
        data = r.json()
        fixtures = data.get("response", [])
        print(f"API-Football: {len(fixtures)} partidos terminados")
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
            if not local or not visitante:
                continue
            resultados.append({
                "local": local, "visitante": visitante,
                "resultado": resultado,
                "fuente": "api-football", "confianza": "confirmado",
                "actualizado_en": datetime.now(timezone.utc).isoformat()
            })
        print(f"API-Football: {len(resultados)} resultados")
    except Exception as e:
        print(f"API-Football error: {e}")
    return resultados

# ═══════════════════════════════════════════
# FUENTE 3: openfootball GitHub (sin key)
# ═══════════════════════════════════════════
def obtener_openfootball():
    resultados = []
    try:
        url = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            print(f"openfootball error: {r.status_code}")
            return []
        data = r.json()
        for ronda in data.get("rounds", []):
            for match in ronda.get("matches", []):
                score = match.get("score", {})
                ft = score.get("ft", [])
                if not ft or len(ft) < 2:
                    continue
                resultado = f"{ft[0]}-{ft[1]}"
                local = norm(match.get("team1", {}).get("name", ""))
                visitante = norm(match.get("team2", {}).get("name", ""))
                if not local or not visitante:
                    continue
                resultados.append({
                    "local": local, "visitante": visitante,
                    "resultado": resultado,
                    "fuente": "openfootball", "confianza": "confirmado",
                    "actualizado_en": datetime.now(timezone.utc).isoformat()
                })
        print(f"openfootball: {len(resultados)} resultados")
    except Exception as e:
        print(f"openfootball error: {e}")
    return resultados

# ═══════════════════════════════════════════
# FUENTE 4: Flashscore por partido individual
# ═══════════════════════════════════════════
def obtener_flashscore_partido(local, visitante):
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "es-ES,es;q=0.9",
    }
    try:
        query = f"{local} {visitante} flashscore resultado"
        url = f"https://www.flashscore.es/futbol/mundial/campeonato-del-mundo/resultados/"
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        html = r.text
        local_norm = local.lower().split()[0]
        vis_norm = visitante.lower().split()[0]
        pos_local = [m.start() for m in re.finditer(re.escape(local_norm), html.lower())]
        pos_vis = [m.start() for m in re.finditer(re.escape(vis_norm), html.lower())]
        for pl in pos_local[:5]:
            for pv in pos_vis[:5]:
                if abs(pl - pv) < 300:
                    inicio = max(0, min(pl, pv) - 20)
                    fin = min(len(html), max(pl, pv) + 150)
                    fragmento = html[inicio:fin]
                    m = re.search(r'(\d{1,2})\s*-\s*(\d{1,2})', fragmento)
                    if m:
                        g1, g2 = int(m.group(1)), int(m.group(2))
                        if g1 <= 20 and g2 <= 20:
                            return f"{g1}-{g2}"
    except Exception as e:
        print(f"Flashscore error: {e}")
    return None

def actualizar():
    # Cargar resultados existentes
    try:
        with open(RESULTADOS_MUNDIAL, encoding="utf-8") as f:
            data_mundial = json.load(f)
    except:
        data_mundial = {"version": "1.0", "resultados": [], "actualizado_en": ""}

    indice = {
        (r.get("local","").lower(), r.get("visitante","").lower()): r
        for r in data_mundial.get("resultados", [])
    }

    # Recoger de todas las fuentes en orden de prioridad
    nuevos = []
    for fuente_fn in [obtener_balldontlie, obtener_api_football, obtener_openfootball]:
        resultados = fuente_fn()
        if resultados:
            nuevos.extend(resultados)
            print(f"Usando {len(resultados)} resultados de fuente")
            break  # Parar en la primera fuente que funcione
        time.sleep(1)

    # Fusionar resultados
    cambios = 0
    for r in nuevos:
        clave = (r["local"], r["visitante"])
        existente = indice.get(clave, {})
        if existente.get("resultado") != r["resultado"]:
            indice[clave] = r
            cambios += 1
            print(f"  Actualizado: {r['local']} vs {r['visitante']} → {r['resultado']}")

    # Ahora buscar en jornadas los partidos que siguen pendientes
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
            if "grupo" in local.lower() or "grupo" in visitante.lower():
                continue

            # Buscar en el índice de resultados
            clave = (norm(local), norm(visitante))
            if clave in indice:
                r = indice[clave]
                p["resultado"] = r["resultado"]
                p["signo_oficial"] = signo(r["resultado"])
                p["fuente_resultado"] = r.get("fuente", "api")
                cambios_j += 1
                cambios += 1
                print(f"  J{data.get('jornada')} [{p['num']}] {local} vs {visitante}: {r['resultado']}")
            else:
                # Fallback: Flashscore
                resultado_flash = obtener_flashscore_partido(local, visitante)
                if resultado_flash:
                    p["resultado"] = resultado_flash
                    p["signo_oficial"] = signo(resultado_flash)
                    p["fuente_resultado"] = "flashscore"
                    clave_norm = (norm(local), norm(visitante))
                    indice[clave_norm] = {
                        "local": norm(local), "visitante": norm(visitante),
                        "resultado": resultado_flash, "fuente": "flashscore",
                        "confianza": "confirmado",
                        "actualizado_en": datetime.now(timezone.utc).isoformat()
                    }
                    cambios_j += 1
                    cambios += 1
                    time.sleep(1)

        if cambios_j:
            todos = all(re.match(r"^\d+-\d+$", str(p.get("resultado",""))) for p in partidos)
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
