"""
Obtiene el cuadro eliminatorio del Mundial 2026 desde BallDontLie API (o Tavily como fallback)
y resuelve los nombres de equipos en las jornadas de la Quiniela.
Produce data/mundial_2026_eliminatorias.json con estructura de bracket para la UI.
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

BALLDONTLIE_KEY = os.environ.get("BALLDONTLIE_API_KEY", "")
TAVILY_KEY = os.environ.get("TAVILY_API_KEY", "")

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
}

def norm(nombre):
    n = str(nombre or "").strip().lower()
    return ALIAS.get(n, n)

def traducir_source(source):
    """Convierte home_team_source a texto legible en español."""
    if not source:
        return "Por determinar"
    tipo = source.get("type", "")
    desc = source.get("description", "") or source.get("label", "")
    grupo = (source.get("group") or {}).get("name", "")
    letra = grupo.replace("Group ", "").strip() if grupo else ""
    
    if tipo in ("group_winner", "winner"):
        return f"1º Grupo {letra}" if letra else desc
    elif tipo in ("group_runner_up", "runner_up"):
        return f"2º Grupo {letra}" if letra else desc
    elif tipo == "third_place":
        grupos = source.get("groups", []) or []
        letras = "".join(g.get("name","").replace("Group","").strip() for g in grupos)
        return f"3º Grupo {letras}" if letras else desc
    elif desc:
        # Traducir descripciones en inglés
        desc = desc.replace("Winner of Group ", "1º Grupo ")
        desc = desc.replace("Runner-up of Group ", "2º Grupo ")
        desc = desc.replace("Best third-place from Groups ", "3º Grupo ")
        return desc
    return "Por determinar"

def resolver_equipo(partido, campo):
    """Resuelve el nombre real o placeholder de un equipo."""
    equipo = partido.get(campo)
    if equipo and equipo.get("name"):
        return norm(equipo["name"])
    source = partido.get(f"{campo}_source")
    return traducir_source(source)

def obtener_partidos():
    if not BALLDONTLIE_KEY:
        print("Sin BALLDONTLIE_API_KEY")
        return []
    try:
        headers = {"Authorization": BALLDONTLIE_KEY}
        r = requests.get(
            "https://api.balldontlie.io/fifa/worldcup/v1/matches",
            headers=headers, timeout=20
        )
        if r.status_code != 200:
            print(f"Error API: {r.status_code}")
            return []
        partidos = r.json().get("data", [])
        print(f"BallDontLie: {len(partidos)} partidos obtenidos")
        return partidos
    except Exception as e:
        print(f"Error: {e}")
        return []

def construir_cuadro(partidos):
    eliminatorias = []
    for p in partidos:
        stage = (p.get("stage") or {}).get("name", "")
        if "Group" in stage:
            continue
        
        local = resolver_equipo(p, "home_team")
        visitante = resolver_equipo(p, "away_team")
        home_score = p.get("home_score")
        away_score = p.get("away_score")
        resultado = f"{home_score}-{away_score}" if home_score is not None and away_score is not None else "Pendiente"
        
        dt_str = p.get("datetime", "") or ""
        fecha = dt_str[:10] if dt_str else ""
        hora = dt_str[11:16] if len(dt_str) > 10 else ""
        
        eliminatorias.append({
            "num": p.get("match_number"),
            "stage": stage,
            "local": local,
            "visitante": visitante,
            "fecha": fecha,
            "hora": hora,
            "resultado": resultado,
            "status": p.get("status", ""),
        })
    
    eliminatorias.sort(key=lambda x: x.get("num") or 999)
    print(f"Cuadro eliminatorio: {len(eliminatorias)} partidos")
    return eliminatorias

def resolver_nombres_jornadas(eliminatorias):
    """
    Para cada partido de jornada con placeholder tipo '2º Grupo K',
    busca si ya hay equipo real en el cuadro y actualiza.
    """
    # Índice: placeholder → nombre real
    indice = {}
    for p in eliminatorias:
        local = p["local"]
        visitante = p["visitante"]
        # Si tiene nombre real (no placeholder), guardarlo
        # Los placeholders contienen "Grupo" o "Por determinar"
        if "Grupo" not in local and local != "Por determinar":
            # Este es un nombre real - pero necesitamos saber 
            # qué placeholder representa
            pass
    
    # Construir índice desde clasificaciones
    try:
        with open(CLASIFICACIONES, encoding="utf-8") as f:
            clasif = json.load(f)
        grupos = clasif.get("grupos", {})
        for g_nombre, g_data in grupos.items():
            letra = g_nombre.replace("Grupo ", "").strip()
            equipos = g_data.get("clasificacion", [])
            if len(equipos) >= 1:
                indice[f"1º Grupo {letra}"] = norm(equipos[0].get("equipo", ""))
            if len(equipos) >= 2:
                indice[f"2º Grupo {letra}"] = norm(equipos[1].get("equipo", ""))
    except Exception as e:
        print(f"Error leyendo clasificaciones: {e}")
    
    print(f"Índice de resolución: {len(indice)} entradas")
    
    cambios_total = 0
    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data = json.load(open(path, encoding="utf-8"))
        partidos = data.get("partidos", [])
        cambios = 0
        
        for p in partidos:
            local = p.get("local", "")
            visitante = p.get("visitante", "")
            
            # Resolver local si es placeholder
            if ("Grupo" in local or "º" in local) and local in indice and indice[local]:
                nuevo_local = indice[local]
                if nuevo_local != local.lower():
                    p["local"] = nuevo_local.title()
                    cambios += 1
                    print(f"  [{p.get('num')}] Local: {local} → {nuevo_local}")
            
            # Resolver visitante si es placeholder
            if ("Grupo" in visitante or "º" in visitante) and visitante in indice and indice[visitante]:
                nuevo_vis = indice[visitante]
                if nuevo_vis != visitante.lower():
                    p["visitante"] = nuevo_vis.title()
                    cambios += 1
                    print(f"  [{p.get('num')}] Visitante: {visitante} → {nuevo_vis}")
        
        if cambios:
            data["actualizado_en"] = datetime.now(timezone.utc).isoformat()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Jornada {data.get('jornada')}: {cambios} nombres resueltos")
            cambios_total += cambios
    
    print(f"Total nombres resueltos: {cambios_total}")

STAGE_MAP = {
    "Round of 32": "dieciseisavos",
    "Round of 16": "octavos",
    "Quarter-finals": "cuartos",
    "Semi-finals": "semifinales",
    "Final": "final",
}

MATCH_NUM_TO_SLOT = {
    73: 0, 75: 1, 74: 2, 77: 3,
    76: 4, 78: 5, 79: 6, 80: 7,
    81: 8, 82: 9, 83: 10, 84: 11,
    85: 12, 87: 13, 86: 14, 88: 15,
}


def cargar_eliminatorias():
    if ELIMINATORIAS.exists():
        try:
            return json.loads(ELIMINATORIAS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def guardar_eliminatorias(data):
    data["actualizado_en"] = datetime.now(timezone.utc).isoformat()
    ELIMINATORIAS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def actualizar_desde_balldontlie(partidos, elim):
    """Actualiza el JSON de eliminatorias con datos de la API BallDontLie."""
    cambios = 0
    rondas = elim.get("rondas", {})

    for p in partidos:
        stage_en = (p.get("stage") or {}).get("name", "")
        ronda_es = STAGE_MAP.get(stage_en)
        if not ronda_es or ronda_es not in rondas:
            continue

        num = p.get("match_number")
        local = resolver_equipo(p, "home_team")
        visitante = resolver_equipo(p, "away_team")
        home_score = p.get("home_score")
        away_score = p.get("away_score")
        resultado = f"{home_score}-{away_score}" if home_score is not None and away_score is not None else None
        dt_str = p.get("datetime", "") or ""
        fecha = dt_str[:10] if dt_str else None

        ganador = None
        if resultado and home_score is not None and away_score is not None:
            if home_score > away_score:
                ganador = local
            elif away_score > home_score:
                ganador = visitante

        partidos_ronda = rondas[ronda_es].get("partidos", [])
        for m in partidos_ronda:
            match_id = m.get("id")
            # Match by num for dieciseisavos, by slot order for later rounds
            if ronda_es == "dieciseisavos" and match_id != num:
                continue
            if ronda_es != "dieciseisavos" and not (local and local != "Por determinar" and m.get("local") == local):
                continue

            if local and local != "Por determinar":
                if m.get("local") != local:
                    m["local"] = local
                    cambios += 1
            if visitante and visitante != "Por determinar":
                if m.get("visitante") != visitante:
                    m["visitante"] = visitante
                    cambios += 1
            if resultado and m.get("resultado") != resultado:
                m["resultado"] = resultado
                m["ganador"] = ganador
                cambios += 1
            if fecha and not m.get("fecha"):
                m["fecha"] = fecha
                cambios += 1
            break

    return cambios


def buscar_resultados_tavily():
    """Usa Tavily para buscar resultados recientes del Mundial 2026."""
    if not TAVILY_KEY:
        return []
    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_KEY,
                "query": "Mundial 2026 eliminatorias resultados dieciseisavos octavos hoy",
                "search_depth": "basic",
                "max_results": 5,
                "include_answer": True,
            },
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            answer = data.get("answer", "") or ""
            content = " ".join(r.get("content", "") for r in data.get("results", []))
            return [answer + " " + content]
    except Exception as e:
        print(f"Tavily eliminatorias: {e}")
    return []


def parse_resultado_texto(texto, local, visitante):
    """Busca 'Local X-Y Visitante' en texto."""
    variantes = [local.lower(), visitante.lower()]
    for pat in [
        r"(\d{1,2})\s*[-–]\s*(\d{1,2})",
    ]:
        for m in re.finditer(pat, texto, re.I):
            frag = texto[max(0, m.start()-200): m.end()+200].lower()
            if all(v.split()[0] in frag for v in variantes):
                if not re.search(r"\b(minuto|min\.|en juego|descanso)\b", frag):
                    return f"{m.group(1)}-{m.group(2)}"
    return None


def actualizar_desde_tavily(elim):
    """Intenta completar resultados pendientes via Tavily."""
    textos = buscar_resultados_tavily()
    if not textos:
        return 0
    texto = " ".join(textos)
    cambios = 0
    for ronda_key, ronda in elim.get("rondas", {}).items():
        for m in ronda.get("partidos", []):
            if m.get("resultado") or not m.get("local") or not m.get("visitante"):
                continue
            res = parse_resultado_texto(texto, m["local"], m["visitante"])
            if res:
                m["resultado"] = res
                gl, gv = (int(x) for x in res.split("-"))
                m["ganador"] = m["local"] if gl > gv else (m["visitante"] if gv > gl else None)
                cambios += 1
                print(f"  Tavily: {m['local']} {res} {m['visitante']}")
    return cambios


def propagar_ganadores(elim):
    """Rellena equipos en rondas posteriores a partir de los ganadores."""
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


if __name__ == "__main__":
    print("=== Actualizando cuadro eliminatorio Mundial 2026 ===")
    partidos = obtener_partidos()
    if partidos:
        eliminatorias = construir_cuadro(partidos)
        cuadro = {
            "actualizado_en": datetime.now(timezone.utc).isoformat(),
            "partidos": eliminatorias
        }
        with open(CUADRO, "w", encoding="utf-8") as f:
            json.dump(cuadro, f, ensure_ascii=False, indent=2)
        print(f"Cuadro guardado: {len(eliminatorias)} partidos")
        resolver_nombres_jornadas(eliminatorias)

        # Actualizar JSON estructurado de eliminatorias
        elim = cargar_eliminatorias()
        if elim:
            c = actualizar_desde_balldontlie(partidos, elim)
            c += propagar_ganadores(elim)
            if c:
                guardar_eliminatorias(elim)
                print(f"Eliminatorias actualizadas desde API: {c} cambio(s)")
    else:
        print("API sin datos - intentando Tavily + clasificaciones locales")
        resolver_nombres_jornadas([])
        elim = cargar_eliminatorias()
        if elim:
            c = actualizar_desde_tavily(elim)
            c += propagar_ganadores(elim)
            if c:
                guardar_eliminatorias(elim)
                print(f"Eliminatorias actualizadas desde Tavily: {c} cambio(s)")

    print("=== Completado ===")
