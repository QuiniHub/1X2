import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ARCHIVOS_CLASIFICACION = [
    ROOT / "clasificaciones.json",
    DATA / "clasificaciones_oficiales.json",
]
CALENDARIOS = {
    "primera": DATA / "calendario_primera.json",
    "segunda": DATA / "calendario_segunda.json",
}

ALIASES = {
    "atletico madrid": "club atletico de madrid",
    "racing santander": "real racing club de santander",
    "deportivo la coruna": "rc deportivo de la coruna",
    "deportivo la Coruña": "rc deportivo de la coruna",
    "malaga": "malaga cf",
    "castellon": "cd castellon",
    "cadiz": "cadiz cf",
    "leganes": "cd leganes",
    "albacete": "albacete balompie",
    "valladolid": "real valladolid cf",
    "real valladolid": "real valladolid cf",
    "sporting gijon": "real sporting de gijon",
    "sporting": "real sporting de gijon",
    "ceuta": "ad ceuta fc",
    "andorra": "fc andorra",
    "las palmas": "ud las palmas",
    "cultural": "cultural leonesa",
    "real sociedad": "real sociedad de futbol",
    "r sociedad": "real sociedad de futbol",
}


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalizar(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(cf|fc|rcd|rc|cd|ud|sd|sad|club|real|de|del|la|el|balompie|futbol)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def clave_equipo(nombre):
    base = str(nombre or "").strip()
    alias = ALIASES.get(base.lower(), base)
    alias_norm = normalizar(alias)
    return alias_norm


def parse_resultado(resultado):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(resultado or ""))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def puntos_partido(gf, gc):
    if gf > gc:
        return 3
    if gf == gc:
        return 1
    return 0


def crear_indice_tabla(tabla):
    indice = {}
    for equipo in tabla:
        indice[clave_equipo(equipo.get("equipo"))] = equipo.get("equipo")
    return indice


def resolver_clave(nombre, indice_tabla):
    clave = clave_equipo(nombre)
    if clave in indice_tabla:
        return clave
    piezas = set(clave.split())
    mejor = None
    mejor_score = 0
    for candidato in indice_tabla:
        cand_piezas = set(candidato.split())
        score = len(piezas & cand_piezas)
        if clave and (clave in candidato or candidato in clave):
            score += 3
        if score > mejor_score:
            mejor = candidato
            mejor_score = score
    return mejor if mejor_score >= 1 else clave


def historial_liga(liga, tabla):
    calendario = cargar_json(CALENDARIOS[liga], {"jornadas": []})
    indice_tabla = crear_indice_tabla(tabla)
    historial = {clave: [] for clave in indice_tabla}

    for jornada in calendario.get("jornadas", []):
        num_jornada = jornada.get("jornada")
        for partido in jornada.get("partidos", []):
            resultado = parse_resultado(partido.get("resultado"))
            if not resultado:
                continue
            gl, gv = resultado
            local = resolver_clave(partido.get("local"), indice_tabla)
            visitante = resolver_clave(partido.get("visitante"), indice_tabla)
            historial.setdefault(local, []).append({
                "jornada": num_jornada,
                "pts": puntos_partido(gl, gv),
                "gf": gl,
                "gc": gv,
            })
            historial.setdefault(visitante, []).append({
                "jornada": num_jornada,
                "pts": puntos_partido(gv, gl),
                "gf": gv,
                "gc": gl,
            })
    for clave in historial:
        historial[clave].sort(key=lambda item: int(item.get("jornada") or 0))
    return historial


def racha_actual(partidos):
    racha = {"victorias": 0, "empates": 0, "derrotas": 0, "sin_ganar": 0, "sin_perder": 0}
    if not partidos:
        return racha
    ultimo = partidos[-1]
    if ultimo["pts"] == 3:
        for p in reversed(partidos):
            if p["pts"] == 3:
                racha["victorias"] += 1
            else:
                break
    elif ultimo["pts"] == 1:
        for p in reversed(partidos):
            if p["pts"] == 1:
                racha["empates"] += 1
            else:
                break
    else:
        for p in reversed(partidos):
            if p["pts"] == 0:
                racha["derrotas"] += 1
            else:
                break

    for p in reversed(partidos):
        if p["pts"] < 3:
            racha["sin_ganar"] += 1
        else:
            break
    for p in reversed(partidos):
        if p["pts"] > 0:
            racha["sin_perder"] += 1
        else:
            break
    return racha


def actualizar_equipo(equipo, partidos):
    if not partidos:
        tendencias = equipo.setdefault("tendencias", {})
        tendencias.setdefault("forma_5_pts", 0)
        tendencias.setdefault("forma_10_pts", 0)
        equipo.setdefault("racha_actual", racha_actual([]))
        return False

    ultimos_5 = partidos[-5:]
    ultimos_10 = partidos[-10:]
    pj = max(int(equipo.get("pj") or len(partidos) or 1), 1)
    gf = int(equipo.get("gf") or sum(p["gf"] for p in partidos))
    gc = int(equipo.get("gc") or sum(p["gc"] for p in partidos))
    e = int(equipo.get("e") or 0)

    tendencias = equipo.setdefault("tendencias", {})
    tendencias["puntos_por_partido"] = round(float(equipo.get("puntos", equipo.get("pts", 0)) or 0) / pj, 3)
    tendencias["goles_favor_por_partido"] = round(gf / pj, 3)
    tendencias["goles_contra_por_partido"] = round(gc / pj, 3)
    tendencias["empates_pct"] = round(e / pj * 100, 2)
    tendencias["forma_5_pts"] = sum(p["pts"] for p in ultimos_5)
    tendencias["forma_10_pts"] = sum(p["pts"] for p in ultimos_10)
    equipo["racha_actual"] = racha_actual(partidos)
    equipo["pts"] = int(equipo.get("puntos", equipo.get("pts", 0)) or 0)
    return True


def actualizar_data(data):
    cambios = []
    for liga in ("primera", "segunda"):
        tabla = data.get(liga, [])
        if not tabla:
            continue
        historial = historial_liga(liga, tabla)
        for equipo in tabla:
            clave = clave_equipo(equipo.get("equipo"))
            if actualizar_equipo(equipo, historial.get(clave, [])):
                cambios.append(f"{liga}:{equipo.get('equipo')}")
    data["dinamicas_recalculadas_en"] = datetime.now(timezone.utc).isoformat()
    data.setdefault("fuentes", {})
    if isinstance(data["fuentes"], dict):
        data["fuentes"]["dinamicas"] = "data/calendario_primera.json y data/calendario_segunda.json"
    return cambios


def main():
    total_cambios = []
    for path in ARCHIVOS_CLASIFICACION:
        data = cargar_json(path, {})
        if not data:
            continue
        cambios = actualizar_data(data)
        guardar_json(path, data)
        total_cambios.extend(cambios)
    print(f"Dinamicas recalculadas desde calendarios: {len(total_cambios)} equipos actualizados.")


if __name__ == "__main__":
    main()
