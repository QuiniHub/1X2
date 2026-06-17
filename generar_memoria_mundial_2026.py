import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
FUENTE = DATA / "mundial_2026_resultados.json"
SALIDA = DATA / "memoria_ia" / "mundial_2026_forma.json"

ALIAS = {
    "eeuu": "estados unidos",
    "usa": "estados unidos",
    "estados unidos": "estados unidos",
    "paises bajos": "paises bajos",
    "japon": "japon",
    "costa marfil": "costa de marfil",
    "costa de marfil": "costa de marfil",
    "cote divoire": "costa de marfil",
    "ivory coast": "costa de marfil",
    "curacao": "curazao",
    "arabia saudi": "arabia saudi",
    "turkiye": "turquia",
    "turkey": "turquia",
    "belgica": "belgica",
    "tunez": "tunez",
    "espana": "espana",
}


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalizar_nombre(nombre):
    texto = str(nombre or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto).strip()
    return ALIAS.get(texto, texto)


def crear_registro(equipo):
    return {"equipo": equipo, "pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0, "dg": 0, "pts": 0, "partidos": [], "fuentes": []}


def anadir_partido(tabla, equipo, rival, gf, gc, fecha, grupo, fuente, condicion):
    registro = tabla[equipo]
    registro["equipo"] = equipo
    registro["pj"] += 1
    registro["gf"] += gf
    registro["gc"] += gc
    registro["dg"] = registro["gf"] - registro["gc"]
    if gf > gc:
        registro["g"] += 1
        puntos = 3
        signo_equipo = "G"
    elif gf == gc:
        registro["e"] += 1
        puntos = 1
        signo_equipo = "E"
    else:
        registro["p"] += 1
        puntos = 0
        signo_equipo = "P"
    registro["pts"] += puntos
    if fuente and fuente not in registro["fuentes"]:
        registro["fuentes"].append(fuente)
    registro["partidos"].append({"fecha": fecha, "grupo": grupo, "rival": rival, "condicion": condicion, "resultado": f"{gf}-{gc}", "signo_equipo": signo_equipo, "puntos": puntos})


def construir_memoria(data):
    tabla = defaultdict(lambda: crear_registro(""))
    descartados = []
    for partido in data.get("resultados", []):
        local = normalizar_nombre(partido.get("local"))
        visitante = normalizar_nombre(partido.get("visitante"))
        match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(partido.get("resultado") or ""))
        if not local or not visitante or not match:
            descartados.append(partido)
            continue
        gl, gv = int(match.group(1)), int(match.group(2))
        fecha = partido.get("fecha") or ""
        grupo = partido.get("grupo") or ""
        fuente = partido.get("fuente") or ""
        anadir_partido(tabla, local, visitante, gl, gv, fecha, grupo, fuente, "neutral_local")
        anadir_partido(tabla, visitante, local, gv, gl, fecha, grupo, fuente, "neutral_visitante")
    equipos = {}
    for clave, registro in sorted(tabla.items()):
        pj = max(int(registro["pj"]), 1)
        registro["tendencias"] = {
            "forma_5_pts": sum(p.get("puntos", 0) for p in registro["partidos"][-5:]),
            "forma_10_pts": sum(p.get("puntos", 0) for p in registro["partidos"][-10:]),
            "empates_pct": round(registro["e"] / pj * 100, 2),
            "goles_favor_por_partido": round(registro["gf"] / pj, 2),
            "goles_contra_por_partido": round(registro["gc"] / pj, 2),
            "puntos_por_partido": round(registro["pts"] / pj, 2),
        }
        registro["local"] = {"pj": pj, "pts": registro["pts"]}
        registro["visitante"] = {"pj": pj, "pts": registro["pts"]}
        registro["calidad"] = "media" if pj == 1 else "alta"
        registro["muestra_partidos"] = pj
        equipos[clave] = registro
    return {"version": "1.0", "generado_en": datetime.now(timezone.utc).isoformat(), "total_resultados": len(data.get("resultados", [])), "total_equipos": len(equipos), "equipos": equipos, "descartados": descartados, "criterio_critico": "Sin memoria del Mundial 2026 no se deben presentar porcentajes como plenamente estudiados."}


def main():
    memoria = construir_memoria(cargar_json(FUENTE, {"resultados": []}))
    guardar_json(SALIDA, memoria)
    print(f"Memoria Mundial 2026 generada: {SALIDA} ({memoria['total_equipos']} equipos)")


if __name__ == "__main__":
    main()
