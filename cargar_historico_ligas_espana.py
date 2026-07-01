"""Descarga y consolida el historial completo de LaLiga 1a y 2a de las ultimas 3 temporadas.

Fuente: football-data.co.uk (CSV libres, sin API key)
Temporadas: 2023/24 (2324), 2024/25 (2425), 2025/26 (2526)
Salida: data/memoria_ia/historico_ligas_espana.json
"""

import os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import csv
import io
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

try:
    import requests
except ImportError:
    requests = None

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SALIDA = DATA / "memoria_ia" / "historico_ligas_espana.json"

TEMPORADAS = ["2324", "2425", "2526"]

LIGAS = {
    "primera": {"csv": "SP1.csv", "nombre": "LaLiga EA Sports"},
    "segunda": {"csv": "SP2.csv", "nombre": "LaLiga Hypermotion"},
}

ALIAS = {
    "alaves": "Alaves", "deportivo alaves": "Alaves",
    "ath bilbao": "Athletic Club", "athletic bilbao": "Athletic Club", "athletic club": "Athletic Club",
    "atletico madrid": "Atletico Madrid", "ath madrid": "Atletico Madrid", "atl. madrid": "Atletico Madrid",
    "barcelona": "Barcelona", "fc barcelona": "Barcelona",
    "betis": "Real Betis", "real betis": "Real Betis",
    "celta": "Celta Vigo", "celta vigo": "Celta Vigo", "rc celta": "Celta Vigo",
    "elche": "Elche", "elche cf": "Elche",
    "espanol": "Espanyol", "espanyol": "Espanyol", "rcd espanyol": "Espanyol",
    "getafe": "Getafe", "getafe cf": "Getafe",
    "girona": "Girona", "girona fc": "Girona",
    "granada": "Granada", "granada cf": "Granada",
    "las palmas": "Las Palmas", "ud las palmas": "Las Palmas",
    "leganes": "Leganes", "cd leganes": "Leganes",
    "levante": "Levante", "levante ud": "Levante",
    "mallorca": "Mallorca", "rcd mallorca": "Mallorca",
    "osasuna": "Osasuna", "ca osasuna": "Osasuna",
    "rayo vallecano": "Rayo Vallecano", "rayo": "Rayo Vallecano",
    "real madrid": "Real Madrid", "r. madrid": "Real Madrid",
    "real sociedad": "Real Sociedad",
    "sevilla": "Sevilla", "sevilla fc": "Sevilla",
    "valencia": "Valencia", "valencia cf": "Valencia",
    "valladolid": "Valladolid", "real valladolid": "Valladolid",
    "villarreal": "Villarreal", "villarreal cf": "Villarreal",
    "almeria": "Almeria", "ud almeria": "Almeria",
    "cadiz": "Cadiz", "cadiz cf": "Cadiz",
    "malaga": "Malaga", "malaga cf": "Malaga",
    "racing santander": "Racing Santander", "racing": "Racing Santander",
    "sporting gijon": "Sporting Gijon", "sporting": "Sporting Gijon",
    "huesca": "Huesca", "sd huesca": "Huesca",
    "lugo": "Lugo", "cd lugo": "Lugo",
    "ponferradina": "Ponferradina",
    "burgos": "Burgos CF", "burgos cf": "Burgos CF",
    "eibar": "Eibar", "sd eibar": "Eibar",
    "tenerife": "Tenerife", "cd tenerife": "Tenerife",
    "mirandes": "Mirandes", "cd mirandes": "Mirandes",
    "andorra": "Andorra", "fc andorra": "Andorra",
    "zaragoza": "Zaragoza", "real zaragoza": "Zaragoza",
    "oviedo": "Oviedo", "real oviedo": "Oviedo",
    "ferrol": "Racing Ferrol", "racing ferrol": "Racing Ferrol",
    "eldense": "Eldense", "cd eldense": "Eldense",
    "cartagena": "Cartagena", "fc cartagena": "Cartagena",
    "toledo": "Toledo",
    "alcorcon": "Alcorcon", "ad alcorcon": "Alcorcon",
    "fuenlabrada": "Fuenlabrada", "cf fuenlabrada": "Fuenlabrada",
    "ibiza": "Ibiza",
    "amorebieta": "Amorebieta",
    "santander": "Racing Santander",
    "castellon": "Castellon", "cd castellon": "Castellon",
    "cordoba": "Cordoba", "cordoba cf": "Cordoba",
    "ferroviaria": "Ferroviaria",
    "ceuta": "AD Ceuta",
}


def normalizar(texto):
    if not texto:
        return ""
    t = unicodedata.normalize("NFD", texto.lower().strip())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def canonico(nombre):
    if not nombre:
        return ""
    key = normalizar(nombre)
    return ALIAS.get(key, nombre.strip())


def signo(gl, gv):
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def descargar_csv(liga, temporada):
    url = f"https://www.football-data.co.uk/mmz4281/{temporada}/{LIGAS[liga]['csv']}"
    try:
        if requests is not None:
            r = requests.get(url, timeout=25)
            r.raise_for_status()
            contenido = r.content.decode("utf-8-sig", errors="replace")
        else:
            req = Request(url, headers={"User-Agent": "QuinielaIAPro/1.0"})
            with urlopen(req, timeout=25) as r:
                contenido = r.read().decode("utf-8-sig", errors="replace")
        return url, contenido
    except Exception as exc:
        print(f"  AVISO: no se pudo descargar {url}: {exc}")
        return url, None


def parsear_csv(contenido, url, temporada):
    partidos = []
    for fila in csv.DictReader(io.StringIO(contenido)):
        local = canonico(fila.get("HomeTeam", ""))
        visitante = canonico(fila.get("AwayTeam", ""))
        gl = fila.get("FTHG", "")
        gv = fila.get("FTAG", "")
        fecha = fila.get("Date", "")
        if not local or not visitante or gl in (None, "") or gv in (None, ""):
            continue
        try:
            gl_int = int(float(gl))
            gv_int = int(float(gv))
        except ValueError:
            continue
        # Parsear fecha
        fecha_iso = ""
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
            try:
                fecha_iso = datetime.strptime(fecha.strip(), fmt).date().isoformat()
                break
            except ValueError:
                pass
        # Cuotas de mercado si las hay
        cuota_1 = fila.get("B365H") or fila.get("WHH") or fila.get("PSH") or ""
        cuota_x = fila.get("B365D") or fila.get("WHD") or fila.get("PSD") or ""
        cuota_2 = fila.get("B365A") or fila.get("WHA") or fila.get("PSA") or ""
        partido = {
            "fecha": fecha_iso,
            "local": local,
            "visitante": visitante,
            "gl": gl_int,
            "gv": gv_int,
            "resultado": f"{gl_int}-{gv_int}",
            "signo": signo(gl_int, gv_int),
            "temporada": temporada,
            "fuente": url,
        }
        # Añadir cuotas solo si existen
        for k, v in [("cuota_1", cuota_1), ("cuota_x", cuota_x), ("cuota_2", cuota_2)]:
            try:
                partido[k] = round(float(v), 2)
            except (ValueError, TypeError):
                pass
        partidos.append(partido)
    return partidos


def calcular_estadisticas(partidos):
    equipos = {}
    total = len(partidos)
    signos = {"1": 0, "X": 0, "2": 0}
    for p in partidos:
        signos[p["signo"]] = signos.get(p["signo"], 0) + 1
        for rol, eq in [("local", p["local"]), ("visitante", p["visitante"])]:
            if eq not in equipos:
                equipos[eq] = {
                    "equipo": eq, "pj": 0, "g": 0, "e": 0, "p": 0,
                    "gf": 0, "gc": 0, "pts": 0,
                    "local": {"pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0},
                    "visitante": {"pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0},
                }
            e = equipos[eq]
            gl, gv = p["gl"], p["gv"]
            gf = gl if rol == "local" else gv
            gc = gv if rol == "local" else gl
            ganó = gf > gc
            empató = gf == gc
            e["pj"] += 1
            e["gf"] += gf
            e["gc"] += gc
            if ganó:
                e["g"] += 1; e["pts"] += 3
            elif empató:
                e["e"] += 1; e["pts"] += 1
            else:
                e["p"] += 1
            sub = e[rol]
            sub["pj"] += 1; sub["gf"] += gf; sub["gc"] += gc
            if ganó:
                sub["g"] += 1
            elif empató:
                sub["e"] += 1
            else:
                sub["p"] += 1
    # Añadir % factores
    for e in equipos.values():
        e["dg"] = e["gf"] - e["gc"]
        if e["pj"] > 0:
            e["pct_victorias"] = round(e["g"] / e["pj"] * 100, 1)
            e["pct_empates"] = round(e["e"] / e["pj"] * 100, 1)
        if e["local"]["pj"] > 0:
            e["local"]["pct_victorias"] = round(e["local"]["g"] / e["local"]["pj"] * 100, 1)
        if e["visitante"]["pj"] > 0:
            e["visitante"]["pct_victorias"] = round(e["visitante"]["g"] / e["visitante"]["pj"] * 100, 1)
    frecuencias = {}
    for s in ("1", "X", "2"):
        frecuencias[s] = round(signos[s] / total * 100, 1) if total > 0 else 0
    return {
        "total_partidos": total,
        "frecuencias_signos": frecuencias,
        "equipos": sorted(equipos.values(), key=lambda x: (-x["pts"], -x["dg"])),
    }


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    print("=== Cargando historial completo LaLiga 1a y 2a (ultimas 3 temporadas) ===\n")
    historico = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "fuente": "football-data.co.uk",
        "temporadas_cargadas": [],
        "ligas": {},
    }

    for liga, info in LIGAS.items():
        print(f"\n--- {info['nombre']} ---")
        historico["ligas"][liga] = {
            "nombre": info["nombre"],
            "temporadas": {},
            "consolidado": {"partidos": [], "estadisticas": {}},
        }
        todos_partidos = []

        for temporada in TEMPORADAS:
            anio_ini = int("20" + temporada[:2])
            anio_fin = int("20" + temporada[2:])
            nombre_temp = f"{anio_ini}/{anio_fin}"
            print(f"  Descargando temporada {nombre_temp}...", end=" ", flush=True)

            url, contenido = descargar_csv(liga, temporada)
            if not contenido:
                print("SIN DATOS")
                continue

            partidos = parsear_csv(contenido, url, nombre_temp)
            if not partidos:
                print("CSV vacío o sin resultados cerrados")
                continue

            stats = calcular_estadisticas(partidos)
            historico["ligas"][liga]["temporadas"][nombre_temp] = {
                "temporada": nombre_temp,
                "partidos": partidos,
                "estadisticas": stats,
            }
            todos_partidos.extend(partidos)
            print(f"{len(partidos)} partidos | 1={stats['frecuencias_signos']['1']}% X={stats['frecuencias_signos']['X']}% 2={stats['frecuencias_signos']['2']}%")

            if nombre_temp not in historico["temporadas_cargadas"]:
                historico["temporadas_cargadas"].append(nombre_temp)

        if todos_partidos:
            stats_total = calcular_estadisticas(todos_partidos)
            historico["ligas"][liga]["consolidado"] = {
                "partidos": todos_partidos,
                "estadisticas": stats_total,
            }
            print(f"  TOTAL {info['nombre']}: {len(todos_partidos)} partidos consolidados")

    guardar_json(SALIDA, historico)
    total = sum(
        len(historico["ligas"][l]["consolidado"]["partidos"])
        for l in historico["ligas"]
    )
    print(f"\nGuardado en {SALIDA}")
    print(f"Total partidos historicos cargados: {total}")
    print(f"Temporadas: {', '.join(historico['temporadas_cargadas'])}")


if __name__ == "__main__":
    main()
