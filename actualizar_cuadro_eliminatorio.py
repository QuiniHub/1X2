"""
Obtiene el cuadro eliminatorio del Mundial 2026 desde BallDontLie API
y resuelve los nombres de equipos en las jornadas de la Quiniela.
"""
import json, os, re, requests, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
CUADRO = DATA / "mundial_2026_cuadro_eliminatorio.json"
CLASIFICACIONES = DATA / "memoria_ia" / "clasificaciones_mundial_2026.json"

BALLDONTLIE_KEY = os.environ.get("BALLDONTLIE_API_KEY", "")

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
        print(f"✅ Cuadro guardado en {CUADRO}")
        resolver_nombres_jornadas(eliminatorias)
    print("=== Completado ===")
