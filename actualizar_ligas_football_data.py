import csv
import io
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

try:
    import requests
except Exception:
    requests = None


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

LIGAS = {
    "primera": {
        "csv": "SP1.csv",
        "calendario": DATA / "calendario_primera.json",
        "equipos_esperados": 20,
        "min_partidos": 300,
    },
    "segunda": {
        "csv": "SP2.csv",
        "calendario": DATA / "calendario_segunda.json",
        "equipos_esperados": 22,
        "min_partidos": 350,
    },
}

ALIAS = {
    # Primera
    "alaves": "Deportivo Alaves",
    "deportivo alaves": "Deportivo Alaves",
    "ath bilbao": "Athletic Club",
    "athletic bilbao": "Athletic Club",
    "athletic club": "Athletic Club",
    "atletico madrid": "Club Atletico de Madrid",
    "ath madrid": "Club Atletico de Madrid",
    "club atletico de madrid": "Club Atletico de Madrid",
    "barcelona": "FC Barcelona",
    "fc barcelona": "FC Barcelona",
    "betis": "Real Betis Balompie",
    "real betis": "Real Betis Balompie",
    "real betis balompie": "Real Betis Balompie",
    "celta": "RC Celta de Vigo",
    "celta vigo": "RC Celta de Vigo",
    "rc celta de vigo": "RC Celta de Vigo",
    "elche": "Elche CF",
    "elche cf": "Elche CF",
    "espanol": "RCD Espanyol de Barcelona",
    "espanyol": "RCD Espanyol de Barcelona",
    "rcd espanyol": "RCD Espanyol de Barcelona",
    "rcd espanyol de barcelona": "RCD Espanyol de Barcelona",
    "getafe": "Getafe CF",
    "getafe cf": "Getafe CF",
    "girona": "Girona FC",
    "girona fc": "Girona FC",
    "levante": "Levante UD",
    "levante ud": "Levante UD",
    "mallorca": "RCD Mallorca",
    "rcd mallorca": "RCD Mallorca",
    "osasuna": "CA Osasuna",
    "ca osasuna": "CA Osasuna",
    "oviedo": "Real Oviedo",
    "real oviedo": "Real Oviedo",
    "real madrid": "Real Madrid CF",
    "real madrid cf": "Real Madrid CF",
    "sociedad": "Real Sociedad de Futbol",
    "real sociedad": "Real Sociedad de Futbol",
    "real sociedad de futbol": "Real Sociedad de Futbol",
    "sevilla": "Sevilla FC",
    "sevilla fc": "Sevilla FC",
    "valencia": "Valencia CF",
    "valencia cf": "Valencia CF",
    "vallecano": "Rayo Vallecano de Madrid",
    "rayo vallecano": "Rayo Vallecano de Madrid",
    "rayo vallecano de madrid": "Rayo Vallecano de Madrid",
    "villarreal": "Villarreal CF",
    "villarreal cf": "Villarreal CF",
    # Segunda
    "albacete": "Albacete Balompie",
    "albacete balompie": "Albacete Balompie",
    "almeria": "UD Almeria",
    "ud almeria": "UD Almeria",
    "andorra": "FC Andorra",
    "fc andorra": "FC Andorra",
    "burgos": "Burgos CF",
    "burgos cf": "Burgos CF",
    "cadiz": "Cadiz CF",
    "cadiz cf": "Cadiz CF",
    "castellon": "CD Castellon",
    "cd castellon": "CD Castellon",
    "ceuta": "AD Ceuta FC",
    "ad ceuta": "AD Ceuta FC",
    "ad ceuta fc": "AD Ceuta FC",
    "cordoba": "Cordoba CF",
    "cordoba cf": "Cordoba CF",
    "deportivo": "RC Deportivo de La Coruna",
    "la coruna": "RC Deportivo de La Coruna",
    "dep la coruna": "RC Deportivo de La Coruna",
    "deportivo la coruna": "RC Deportivo de La Coruna",
    "rc deportivo de la coruna": "RC Deportivo de La Coruna",
    "eibar": "SD Eibar",
    "sd eibar": "SD Eibar",
    "granada": "Granada CF",
    "granada cf": "Granada CF",
    "huesca": "SD Huesca",
    "sd huesca": "SD Huesca",
    "las palmas": "UD Las Palmas",
    "ud las palmas": "UD Las Palmas",
    "leganes": "CD Leganes",
    "cd leganes": "CD Leganes",
    "malaga": "Malaga CF",
    "malaga cf": "Malaga CF",
    "mirandes": "CD Mirandes",
    "cd mirandes": "CD Mirandes",
    "racing santander": "Real Racing Club de Santander",
    "real racing club de santander": "Real Racing Club de Santander",
    "racing club santander": "Real Racing Club de Santander",
    "sociedad b": "Real Sociedad B",
    "real sociedad b": "Real Sociedad B",
    "sp gijon": "Real Sporting de Gijon",
    "sporting gijon": "Real Sporting de Gijon",
    "sporting g treal": "Real Sporting de Gijon",
    "real sporting de gijon": "Real Sporting de Gijon",
    "valladolid": "Real Valladolid CF",
    "real valladolid": "Real Valladolid CF",
    "real valladolid cf": "Real Valladolid CF",
    "zaragoza": "Real Zaragoza",
    "real zaragoza": "Real Zaragoza",
    "cultural leonesa": "Cultural Leonesa",
    "cultural leon": "Cultural Leonesa",
    "leonesa": "Cultural Leonesa",
}


def ahora_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cargar_json(path, defecto):
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalizar(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split())


def canonico(nombre):
    clave = normalizar(nombre)
    if clave in ALIAS:
        return ALIAS[clave]
    for alias, oficial in ALIAS.items():
        if alias and (clave == alias or clave.endswith(" " + alias) or alias in clave):
            return oficial
    return str(nombre or "").strip()


def temporada_codigo(fecha=None):
    fecha = fecha or datetime.now()
    inicio = fecha.year if fecha.month >= 8 else fecha.year - 1
    return f"{inicio % 100:02d}{(inicio + 1) % 100:02d}"


def fecha_iso(valor):
    texto = str(valor or "").strip()
    if not texto:
        return ""
    for formato in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            pass
    return texto


def descargar_partidos_csv(liga):
    codigo = temporada_codigo()
    url = f"https://www.football-data.co.uk/mmz4281/{codigo}/{LIGAS[liga]['csv']}"
    if requests is not None:
        respuesta = requests.get(url, timeout=25)
        respuesta.raise_for_status()
        contenido = respuesta.content.decode("utf-8-sig", errors="replace")
    else:
        peticion = Request(url, headers={"User-Agent": "QuinielaIAPro/1.0"})
        with urlopen(peticion, timeout=25) as respuesta:
            contenido = respuesta.read().decode("utf-8-sig", errors="replace")
    filas = []
    for fila in csv.DictReader(io.StringIO(contenido)):
        local = canonico(fila.get("HomeTeam"))
        visitante = canonico(fila.get("AwayTeam"))
        gl = fila.get("FTHG")
        gv = fila.get("FTAG")
        if not local or not visitante or gl in (None, "") or gv in (None, ""):
            continue
        try:
            gl_int = int(float(gl))
            gv_int = int(float(gv))
        except ValueError:
            continue
        filas.append(
            {
                "fecha": fecha_iso(fila.get("Date")),
                "local": local,
                "visitante": visitante,
                "resultado": f"{gl_int}-{gv_int}",
                "gl": gl_int,
                "gv": gv_int,
                "fuente": url,
            }
        )
    return url, filas


def clave_partido(local, visitante):
    return normalizar(canonico(local)), normalizar(canonico(visitante))


def actualizar_calendario(liga, resultados):
    calendario_path = LIGAS[liga]["calendario"]
    calendario = cargar_json(calendario_path, {"competicion": liga, "jornadas": []})
    indice = {}
    for jornada in calendario.get("jornadas", []):
        for partido in jornada.get("partidos", []):
            indice[clave_partido(partido.get("local"), partido.get("visitante"))] = partido

    cambios = 0
    sin_emparejar = []
    for resultado in resultados:
        partido = indice.get(clave_partido(resultado["local"], resultado["visitante"]))
        if not partido:
            sin_emparejar.append(f"{resultado['local']} - {resultado['visitante']}")
            continue
        previo = (partido.get("resultado") or "").strip()
        if previo != resultado["resultado"] or partido.get("estado") != "Jugado":
            partido["resultado"] = resultado["resultado"]
            partido["estado"] = "Jugado"
            if resultado.get("fecha"):
                partido["fecha"] = resultado["fecha"]
            partido["actualizado_en"] = ahora_iso()
            cambios += 1

    calendario["fuente"] = "football-data.co.uk + calendario interno"
    calendario["actualizado_en"] = ahora_iso()
    guardar_json(calendario_path, calendario)
    return calendario, cambios, sin_emparejar


def parse_resultado(partido):
    resultado = str(partido.get("resultado") or "").strip()
    match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", resultado)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def puntos_de(gl, gv):
    if gl > gv:
        return 3, 0
    if gl < gv:
        return 0, 3
    return 1, 1


def nuevo_equipo(nombre):
    return {
        "equipo": canonico(nombre),
        "pj": 0,
        "g": 0,
        "e": 0,
        "p": 0,
        "gf": 0,
        "gc": 0,
        "dg": 0,
        "puntos": 0,
        "pts": 0,
        "_ultimos": [],
    }


def aplicar_partido(tabla, local, visitante, gl, gv):
    local = canonico(local)
    visitante = canonico(visitante)
    tabla.setdefault(local, nuevo_equipo(local))
    tabla.setdefault(visitante, nuevo_equipo(visitante))
    pts_l, pts_v = puntos_de(gl, gv)
    for equipo, gf, gc, pts in ((tabla[local], gl, gv, pts_l), (tabla[visitante], gv, gl, pts_v)):
        equipo["pj"] += 1
        equipo["gf"] += gf
        equipo["gc"] += gc
        equipo["dg"] = equipo["gf"] - equipo["gc"]
        equipo["puntos"] += pts
        equipo["pts"] = equipo["puntos"]
        if pts == 3:
            equipo["g"] += 1
            equipo["_ultimos"].append("G")
        elif pts == 1:
            equipo["e"] += 1
            equipo["_ultimos"].append("E")
        else:
            equipo["p"] += 1
            equipo["_ultimos"].append("P")


def racha_actual(ultimos):
    if not ultimos:
        return {"victorias": 0, "empates": 0, "derrotas": 0, "sin_ganar": 0, "sin_perder": 0}
    ultimo = ultimos[-1]
    actual = 0
    for signo in reversed(ultimos):
        if signo == ultimo:
            actual += 1
        else:
            break
    sin_ganar = 0
    for signo in reversed(ultimos):
        if signo != "G":
            sin_ganar += 1
        else:
            break
    sin_perder = 0
    for signo in reversed(ultimos):
        if signo != "P":
            sin_perder += 1
        else:
            break
    return {
        "victorias": actual if ultimo == "G" else 0,
        "empates": actual if ultimo == "E" else 0,
        "derrotas": actual if ultimo == "P" else 0,
        "sin_ganar": sin_ganar,
        "sin_perder": sin_perder,
    }


def puntos_ultimos(ultimos, limite):
    valor = {"G": 3, "E": 1, "P": 0}
    return sum(valor.get(signo, 0) for signo in ultimos[-limite:])


def construir_clasificacion(calendario):
    tabla = {}
    jugados = 0
    jornadas = sorted(calendario.get("jornadas", []), key=lambda j: int(j.get("jornada", 0) or 0))
    for jornada in jornadas:
        for partido in jornada.get("partidos", []):
            marcador = parse_resultado(partido)
            if not marcador:
                continue
            gl, gv = marcador
            aplicar_partido(tabla, partido.get("local"), partido.get("visitante"), gl, gv)
            jugados += 1

    equipos = list(tabla.values())
    equipos.sort(key=lambda e: (-e["puntos"], -e["dg"], -e["gf"], e["equipo"]))
    for posicion, equipo in enumerate(equipos, start=1):
        equipo["posicion"] = posicion
        equipo["dg"] = equipo["gf"] - equipo["gc"]
        pj = max(equipo["pj"], 1)
        ultimos = equipo.pop("_ultimos", [])
        equipo["racha_actual"] = racha_actual(ultimos)
        equipo["tendencias"] = {
            "puntos_por_partido": round(equipo["puntos"] / pj, 3),
            "goles_favor_por_partido": round(equipo["gf"] / pj, 3),
            "goles_contra_por_partido": round(equipo["gc"] / pj, 3),
            "empates_pct": round((equipo["e"] / pj) * 100, 1),
            "forma_5_pts": puntos_ultimos(ultimos, 5),
            "forma_10_pts": puntos_ultimos(ultimos, 10),
        }
    return equipos, jugados


def construir_clasificacion_desde_resultados(resultados):
    tabla = {}
    jugados = 0
    ordenados = sorted(resultados, key=lambda r: r.get("fecha") or "")
    for resultado in ordenados:
        aplicar_partido(
            tabla,
            resultado.get("local"),
            resultado.get("visitante"),
            int(resultado.get("gl", 0)),
            int(resultado.get("gv", 0)),
        )
        jugados += 1

    equipos = list(tabla.values())
    equipos.sort(key=lambda e: (-e["puntos"], -e["dg"], -e["gf"], e["equipo"]))
    for posicion, equipo in enumerate(equipos, start=1):
        equipo["posicion"] = posicion
        equipo["dg"] = equipo["gf"] - equipo["gc"]
        pj = max(equipo["pj"], 1)
        ultimos = equipo.pop("_ultimos", [])
        equipo["racha_actual"] = racha_actual(ultimos)
        equipo["tendencias"] = {
            "puntos_por_partido": round(equipo["puntos"] / pj, 3),
            "goles_favor_por_partido": round(equipo["gf"] / pj, 3),
            "goles_contra_por_partido": round(equipo["gc"] / pj, 3),
            "empates_pct": round((equipo["e"] / pj) * 100, 1),
            "forma_5_pts": puntos_ultimos(ultimos, 5),
            "forma_10_pts": puntos_ultimos(ultimos, 10),
        }
    return equipos, jugados


def validar_tabla(liga, equipos, jugados):
    esperados = LIGAS[liga]["equipos_esperados"]
    minimo = LIGAS[liga]["min_partidos"]
    if len(equipos) != esperados:
        print(f"{liga}: no se sustituye la tabla; equipos {len(equipos)}/{esperados}.")
        return False
    if jugados < minimo:
        print(f"{liga}: no se sustituye la tabla; solo {jugados} partidos jugados.")
        return False
    return True


def actualizar_clasificaciones(tablas, fuentes):
    ahora = ahora_iso()
    rutas = [ROOT / "clasificaciones.json", DATA / "clasificaciones_oficiales.json"]
    for ruta in rutas:
        data = cargar_json(ruta, {})
        for liga, tabla in tablas.items():
            data[liga] = tabla
        data["actualizado_en"] = ahora
        data["validado_en"] = ahora
        data["dinamicas_recalculadas_en"] = ahora
        data.setdefault("fuentes", {})
        data["fuentes"]["football_data"] = fuentes
        data["fuente_principal"] = "football-data.co.uk + calendario interno recalculado"
        guardar_json(ruta, data)


def main():
    tablas = {}
    fuentes = {}
    for liga in ("primera", "segunda"):
        try:
            fuente, resultados = descargar_partidos_csv(liga)
        except Exception as exc:
            print(f"{liga}: no se pudo leer football-data ({exc}); se conserva la tabla actual.")
            continue
        _, cambios, sin_emparejar = actualizar_calendario(liga, resultados)
        equipos, jugados = construir_clasificacion_desde_resultados(resultados)
        fuentes[liga] = {"url": fuente, "resultados_leidos": len(resultados), "cambios_calendario": cambios}
        print(f"{liga}: {len(resultados)} resultados fuente, {cambios} cambios calendario, {jugados} partidos jugados.")
        if sin_emparejar:
            print(f"{liga}: {len(sin_emparejar)} partidos de fuente sin emparejar con calendario.")
        if validar_tabla(liga, equipos, jugados):
            tablas[liga] = equipos
            max_pj = max((e.get("pj", 0) for e in equipos), default=0)
            print(f"{liga}: clasificacion recalculada desde calendario, max PJ {max_pj}.")

    if tablas:
        actualizar_clasificaciones(tablas, fuentes)
        print("Clasificaciones reconstruidas desde resultados reales de liga.")
    else:
        print("No hay tablas nuevas validadas; no se sobrescriben clasificaciones.")


if __name__ == "__main__":
    main()
