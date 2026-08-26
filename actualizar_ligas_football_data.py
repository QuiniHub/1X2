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
        "calendario_oficial": DATA / "calendario_1a_2627.json",
        "equipos_esperados": 20,
        "min_partidos": 300,
    },
    "segunda": {
        "csv": "SP2.csv",
        "calendario": DATA / "calendario_segunda.json",
        "calendario_oficial": DATA / "calendario_2a_2627.json",
        "equipos_esperados": 22,
        "min_partidos": 350,
    },
}

# Nombres exactos que usa el calendario oficial 26/27 (data/calendario_1a_2627.json
# y calendario_2a_2627.json, la lista completa de 38/42 jornadas con fecha y
# emparejamientos, sin resultado) -> nombre canonico que ya usan calendario_primera.json/
# segunda.json en su lista "equipos". Es un mapeo cerrado y explicito (no por
# regex/substring como el resto de este archivo) porque son solo 20+22 equipos
# conocidos de antemano, y varios de ellos NO resuelven bien con las heuristicas
# de canonico() (ej. "Atletico de Madrid" con "de" en medio no coincide con
# ningun alias existente ahi tampoco -mismo tipo de gap que este script ya
# tenia para nombres del CSV, ver ALIAS mas abajo).
NOMBRES_CALENDARIO_OFICIAL = {
    "primera": {
        "Alavés": "Deportivo Alaves",
        "Athletic Club": "Athletic Club",
        "Atlético de Madrid": "Club Atletico de Madrid",
        "Celta de Vigo": "RC Celta de Vigo",
        "Deportivo de La Coruña": "RC Deportivo de La Coruna",
        "Elche": "Elche CF",
        "Espanyol": "RCD Espanyol de Barcelona",
        "FC Barcelona": "FC Barcelona",
        "Getafe": "Getafe CF",
        "Levante": "Levante UD",
        "Málaga CF": "Malaga CF",
        "Osasuna": "CA Osasuna",
        "Racing de Santander": "Real Racing Club de Santander",
        "Rayo Vallecano": "Rayo Vallecano de Madrid",
        "Real Betis": "Real Betis Balompie",
        "Real Madrid": "Real Madrid CF",
        "Real Sociedad": "Real Sociedad de Futbol",
        "Sevilla": "Sevilla FC",
        "Valencia": "Valencia CF",
        "Villarreal": "Villarreal CF",
    },
    "segunda": {
        "AD Ceuta FC": "AD Ceuta FC",
        "Albacete Balompié": "Albacete Balompie",
        "Burgos CF": "Burgos CF",
        "CD Castellón": "CD Castellon",
        "CD Eldense": "CD Eldense",
        "CD Leganés": "CD Leganes",
        "CD Tenerife": "CD Tenerife",
        "CE Sabadell FC": "CE Sabadell",
        "Cádiz CF": "Cadiz CF",
        "Córdoba CF": "Cordoba CF",
        "FC Andorra": "FC Andorra",
        "Girona FC": "Girona FC",
        "Granada CF": "Granada CF",
        "RC Celta Fortuna": "RC Celta Fortuna",
        "RCD Mallorca": "RCD Mallorca",
        "Real Oviedo": "Real Oviedo",
        "Real Sociedad de Fútbol B": "Real Sociedad B",
        "Real Sporting de Gijón": "Real Sporting de Gijon",
        "Real Valladolid CF": "Real Valladolid CF",
        "SD Eibar": "SD Eibar",
        "UD Almería": "UD Almeria",
        "UD Las Palmas": "UD Las Palmas",
    },
}

# football-data.co.uk usa para Segunda el nombre largo "RC Celta de Vigo" para
# el filial (Celta Fortuna, recien ascendido) en vez de un codigo propio -el
# alias global "celta de vigo" -> "RC Celta de Vigo" mas abajo es correcto
# para Primera (el primer equipo), asi que esta correccion solo se aplica al
# procesar la liga "segunda", sin tocar el alias compartido.
ALIAS_POR_LIGA = {
    "segunda": {
        "rc celta de vigo": "RC Celta Fortuna",
        "celta de vigo": "RC Celta Fortuna",
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
    "atl madrid": "Club Atletico de Madrid",
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
    "dep a coruna": "RC Deportivo de La Coruna",
    "deportivo la coruna": "RC Deportivo de La Coruna",
    "rc deportivo de la coruna": "RC Deportivo de La Coruna",
    "eibar": "SD Eibar",
    "sd eibar": "SD Eibar",
    "eldense": "CD Eldense",
    "cd eldense": "CD Eldense",
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
    "sabadell": "CE Sabadell",
    "ce sabadell": "CE Sabadell",
    "tenerife": "CD Tenerife",
    "cd tenerife": "CD Tenerife",
    "santander": "Real Racing Club de Santander",
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


def canonico(nombre, liga=None):
    clave = normalizar(nombre)
    especifico = ALIAS_POR_LIGA.get(liga, {})
    if clave in especifico:
        return especifico[clave]
    if clave in ALIAS:
        return ALIAS[clave]
    for alias, oficial in ALIAS.items():
        if alias and (clave == alias or clave.endswith(" " + alias) or alias in clave):
            return oficial
    return str(nombre or "").strip()


def temporada_inicio(fecha=None):
    fecha = fecha or datetime.now()
    return fecha.year if fecha.month >= 8 else fecha.year - 1


def temporada_codigo_desde_inicio(inicio):
    return f"{inicio % 100:02d}{(inicio + 1) % 100:02d}"


def temporada_codigo(fecha=None):
    return temporada_codigo_desde_inicio(temporada_inicio(fecha))


def codigos_temporada_candidatos(fecha=None):
    fecha = fecha or datetime.now()
    inicio = temporada_inicio(fecha)
    candidatos = []
    if fecha.month >= 6:
        candidatos.append(inicio + 1)
    candidatos.append(inicio)
    return [temporada_codigo_desde_inicio(i) for i in dict.fromkeys(candidatos)]


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
    errores = []
    for codigo in codigos_temporada_candidatos():
        url = f"https://www.football-data.co.uk/mmz4281/{codigo}/{LIGAS[liga]['csv']}"
        try:
            if requests is not None:
                respuesta = requests.get(url, timeout=25)
                respuesta.raise_for_status()
                contenido = respuesta.content.decode("utf-8-sig", errors="replace")
            else:
                peticion = Request(url, headers={"User-Agent": "QuinielaIAPro/1.0"})
                with urlopen(peticion, timeout=25) as respuesta:
                    contenido = respuesta.read().decode("utf-8-sig", errors="replace")
        except Exception as exc:
            errores.append(f"{codigo}: {exc}")
            continue

        filas = []
        for fila in csv.DictReader(io.StringIO(contenido)):
            local = canonico(fila.get("HomeTeam"), liga)
            visitante = canonico(fila.get("AwayTeam"), liga)
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
                    "temporada_codigo": codigo,
                }
            )
        if filas:
            return url, filas

    raise RuntimeError("; ".join(errores) or "sin resultados publicados")


def clave_partido(local, visitante):
    return normalizar(canonico(local)), normalizar(canonico(visitante))


def sembrar_jornadas_desde_oficial(liga):
    """Asegura que calendario_primera.json/segunda.json tengan el fixture
    completo (local/visitante/fecha, sin resultado todavia) de las 38/42
    jornadas oficiales de data/calendario_1a_2627.json/2a_2627.json.

    Bug real (21/08/2026): sin esto, calendario_primera.json/segunda.json
    se quedaban con la lista de equipos pero CERO partidos dentro de cada
    jornada -asi que actualizar_calendario() no tenia ningun "hueco" contra
    el que emparejar los resultados reales del CSV de football-data.co.uk, y
    los descartaba todos en silencio como "sin emparejar". Consecuencia real
    en el motor: fuerza() da un 76% del peso a estos datos, y de esa formula,
    ~55% depende de forma reciente (ultimos 5/10 partidos) y rendimiento
    casa/fuera -ambos se quedaban a 0 para los 42 equipos durante toda la
    temporada, aunque los partidos ya estuvieran jugados y con resultado
    conocido en otras fuentes (AS.com, TheSportsDB). Idempotente: solo añade
    los partidos que todavia no esten, no reescribe resultados ya guardados."""
    oficial = cargar_json(LIGAS[liga]["calendario_oficial"], {})
    jornadas_oficiales = oficial.get("jornadas") or []
    if not jornadas_oficiales:
        return 0

    nombres = NOMBRES_CALENDARIO_OFICIAL[liga]
    calendario_path = LIGAS[liga]["calendario"]
    calendario = cargar_json(calendario_path, {"competicion": liga, "jornadas": []})
    por_numero = {int(j.get("jornada", 0)): j for j in calendario.get("jornadas", [])}

    cambios = 0
    for jornada_oficial in jornadas_oficiales:
        num = int(jornada_oficial.get("num", 0))
        jornada = por_numero.get(num)
        if jornada is None:
            jornada = {"jornada": num, "partidos": []}
            calendario.setdefault("jornadas", []).append(jornada)
            por_numero[num] = jornada
        jornada.pop("estado", None)  # ya no aplica "pendiente_calendario_oficial" una vez sembrada
        ya_presentes = {
            clave_partido(p.get("local"), p.get("visitante")) for p in jornada.get("partidos", [])
        }
        for partido in jornada_oficial.get("partidos", []):
            local = nombres.get(partido.get("local"), partido.get("local"))
            visitante = nombres.get(partido.get("visitante"), partido.get("visitante"))
            clave = clave_partido(local, visitante)
            if clave in ya_presentes:
                continue
            jornada.setdefault("partidos", []).append({
                "local": local,
                "visitante": visitante,
                "fecha": jornada_oficial.get("fecha", ""),
                "resultado": "",
                "estado": "Pendiente",
            })
            ya_presentes.add(clave)
            cambios += 1

    if cambios:
        calendario["jornadas"] = sorted(por_numero.values(), key=lambda j: int(j.get("jornada", 0)))
        guardar_json(calendario_path, calendario)
    return cambios


def _fecha_es_futura(fecha_iso_str, hoy):
    try:
        return datetime.strptime(fecha_iso_str[:10], "%Y-%m-%d").date() > hoy
    except ValueError:
        return False


def actualizar_calendario(liga, resultados):
    calendario_path = LIGAS[liga]["calendario"]
    calendario = cargar_json(calendario_path, {"competicion": liga, "jornadas": []})
    indice = {}
    for jornada in calendario.get("jornadas", []):
        for partido in jornada.get("partidos", []):
            indice[clave_partido(partido.get("local"), partido.get("visitante"))] = partido

    # Bug real (25/08/2026): calendario_primera.json quedo con "Sevilla FC -
    # Club Atletico de Madrid" (Jornada 3, fecha 2026-08-30) marcado "Jugado"
    # con marcador 2-1 CINCO DIAS antes de jugarse -football-data.co.uk (o
    # una respuesta transitoria suya) trajo un resultado con la fecha del
    # partido todavia sin llegar, y actualizar_calendario() lo escribio sin
    # comprobar la fecha contra "hoy". Guardia minima: nunca marcar "Jugado"
    # un partido cuya fecha (la del resultado entrante, o si no la trae la
    # que ya tenia el partido) sea posterior a hoy.
    hoy = datetime.now(timezone.utc).date()
    cambios = 0
    sin_emparejar = []
    ignorados_fecha_futura = []
    for resultado in resultados:
        partido = indice.get(clave_partido(resultado["local"], resultado["visitante"]))
        if not partido:
            sin_emparejar.append(f"{resultado['local']} - {resultado['visitante']}")
            continue
        fecha_referencia = resultado.get("fecha") or partido.get("fecha")
        if fecha_referencia and _fecha_es_futura(fecha_referencia, hoy):
            ignorados_fecha_futura.append(f"{resultado['local']} - {resultado['visitante']} ({fecha_referencia})")
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
    return calendario, cambios, sin_emparejar, ignorados_fecha_futura


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


def codigo_temporada_desde_url(url):
    coincidencia = re.search(r"/mmz4281/(\d{4})/", str(url or ""))
    return coincidencia.group(1) if coincidencia else None


def es_retroceso_de_temporada(data, liga, fuentes):
    """No dejar que el fallback a la temporada anterior de football-data.co.uk
    pise el roster de 2026/2027 ya confirmado por actualizar_clasificaciones_oficiales.py
    (via el "Racing de Santander" en Primera) cuando football-data.co.uk todavia
    no tiene partidos reales de 2026/2027 y cae al CSV de 2025/2026."""
    if data.get("temporada_detectada") != "2026/2027":
        return False
    codigo = codigo_temporada_desde_url(fuentes.get(liga, {}).get("url"))
    return codigo is not None and codigo != "2627"


def actualizar_clasificaciones(tablas, fuentes):
    ahora = ahora_iso()
    rutas = [ROOT / "clasificaciones.json", DATA / "clasificaciones_oficiales.json"]
    for ruta in rutas:
        data = cargar_json(ruta, {})
        cambiado = False
        for liga, tabla in tablas.items():
            if es_retroceso_de_temporada(data, liga, fuentes):
                print(f"{liga}: se conserva el roster 2026/2027 ya confirmado; football-data.co.uk solo tiene datos de una temporada anterior.")
                continue
            data[liga] = tabla
            cambiado = True
        if not cambiado:
            continue
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
        sembrados = sembrar_jornadas_desde_oficial(liga)
        if sembrados:
            print(f"{liga}: {sembrados} partidos sembrados desde el calendario oficial 26/27.")
        try:
            fuente, resultados = descargar_partidos_csv(liga)
        except Exception as exc:
            print(f"{liga}: no se pudo leer football-data ({exc}); se conserva la tabla actual.")
            continue
        _, cambios, sin_emparejar, ignorados_fecha_futura = actualizar_calendario(liga, resultados)
        equipos, jugados = construir_clasificacion_desde_resultados(resultados)
        fuentes[liga] = {"url": fuente, "resultados_leidos": len(resultados), "cambios_calendario": cambios}
        print(f"{liga}: {len(resultados)} resultados fuente, {cambios} cambios calendario, {jugados} partidos jugados.")
        if sin_emparejar:
            print(f"{liga}: {len(sin_emparejar)} partidos de fuente sin emparejar con calendario.")
        if ignorados_fecha_futura:
            print(f"{liga}: {len(ignorados_fecha_futura)} resultados ignorados por tener fecha futura: {ignorados_fecha_futura}")
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
