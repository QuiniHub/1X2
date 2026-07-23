"""Prepara LaLiga 2026/2027 en modo backend.

- Define equipos oficiales esperados de Primera y Segunda 2026/2027.
- Inicializa clasificaciones a cero.
- Crea calendarios vacios listos para integrar partidos oficiales.
- En julio-agosto activa modo pretemporada y vigila fuentes habituales.
- Si football-data publica SP1/SP2 2627 con calendario, lo integra sin tocar web.
- Resetea perfiles de equipos de liga para la nueva temporada preservando historico.
"""

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
MEMORIA = DATA / "memoria_ia"
CLASIFICACIONES = DATA / "clasificaciones_oficiales.json"
CALENDARIO_PRIMERA = DATA / "calendario_primera.json"
CALENDARIO_SEGUNDA = DATA / "calendario_segunda.json"
PERFILES = MEMORIA / "perfiles_equipos.json"
ESTADO = DATA / "estado_temporada_2026_2027.json"

TEMPORADA = "2026/2027"
TEMPORADA_KEY = "2026_2027"
CODIGO_FOOTBALL_DATA = "2627"

PRIMERA_2026_2027 = [
    "Deportivo Alaves",
    "Athletic Club",
    "Club Atletico de Madrid",
    "FC Barcelona",
    "Real Betis Balompie",
    "RC Celta de Vigo",
    "RC Deportivo de La Coruna",
    "Elche CF",
    "RCD Espanyol de Barcelona",
    "Getafe CF",
    "Levante UD",
    "Malaga CF",
    "CA Osasuna",
    "Rayo Vallecano de Madrid",
    "Real Racing Club de Santander",
    "Real Madrid CF",
    "Real Sociedad de Futbol",
    "Sevilla FC",
    "Valencia CF",
    "Villarreal CF",
]

SEGUNDA_2026_2027 = [
    "Albacete Balompie",
    "UD Almeria",
    "FC Andorra",
    "Burgos CF",
    "Cadiz CF",
    "CD Castellon",
    "AD Ceuta FC",
    "RC Celta Fortuna",
    "Cordoba CF",
    "CD Eldense",
    "SD Eibar",
    "Girona FC",
    "Granada CF",
    "CD Leganes",
    "UD Las Palmas",
    "RCD Mallorca",
    "Real Oviedo",
    "Real Sociedad B",
    "CE Sabadell",
    "Real Sporting de Gijon",
    "CD Tenerife",
    "Real Valladolid CF",
]

FUENTES_EQUIPOS = {
    "primera": [
        "LaLiga EA Sports 2025/26 final: descienden Girona FC, RCD Mallorca y Real Oviedo",
        "LaLiga Hypermotion 2025/26: ascienden Racing Club, RC Deportivo de La Coruna y Malaga CF",
    ],
    "segunda": [
        "Cadena SER/AS 2026: Segunda 2026/27 con Girona, Mallorca, Oviedo, Tenerife, Eldense, Celta Fortuna y Sabadell",
    ],
}

FUENTES_CALENDARIO = {
    "primera": [
        f"https://www.football-data.co.uk/mmz4281/{CODIGO_FOOTBALL_DATA}/SP1.csv",
        "https://www.quinielafutbol.info/proximas-jornadas-de-la-quiniela.html",
    ],
    "segunda": [
        f"https://www.football-data.co.uk/mmz4281/{CODIGO_FOOTBALL_DATA}/SP2.csv",
        "https://www.quinielafutbol.info/proximas-jornadas-de-la-quiniela.html",
    ],
}

ALIAS = {
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
    "deportivo": "RC Deportivo de La Coruna",
    "deportivo la coruna": "RC Deportivo de La Coruna",
    "dep la coruna": "RC Deportivo de La Coruna",
    "rc deportivo": "RC Deportivo de La Coruna",
    "rc deportivo de la coruna": "RC Deportivo de La Coruna",
    "elche": "Elche CF",
    "elche cf": "Elche CF",
    "espanol": "RCD Espanyol de Barcelona",
    "espanyol": "RCD Espanyol de Barcelona",
    "rcd espanyol": "RCD Espanyol de Barcelona",
    "rcd espanyol de barcelona": "RCD Espanyol de Barcelona",
    "getafe": "Getafe CF",
    "getafe cf": "Getafe CF",
    "levante": "Levante UD",
    "levante ud": "Levante UD",
    "malaga": "Malaga CF",
    "malaga cf": "Malaga CF",
    "osasuna": "CA Osasuna",
    "ca osasuna": "CA Osasuna",
    "rayo vallecano": "Rayo Vallecano de Madrid",
    "vallecano": "Rayo Vallecano de Madrid",
    "rayo vallecano de madrid": "Rayo Vallecano de Madrid",
    "racing": "Real Racing Club de Santander",
    "racing santander": "Real Racing Club de Santander",
    "real racing club de santander": "Real Racing Club de Santander",
    "real madrid": "Real Madrid CF",
    "real madrid cf": "Real Madrid CF",
    "real sociedad": "Real Sociedad de Futbol",
    "real sociedad de futbol": "Real Sociedad de Futbol",
    "sevilla": "Sevilla FC",
    "sevilla fc": "Sevilla FC",
    "valencia": "Valencia CF",
    "valencia cf": "Valencia CF",
    "villarreal": "Villarreal CF",
    "villarreal cf": "Villarreal CF",
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
    "celta fortuna": "RC Celta Fortuna",
    "rc celta fortuna": "RC Celta Fortuna",
    "cordoba": "Cordoba CF",
    "cordoba cf": "Cordoba CF",
    "eldense": "CD Eldense",
    "cd eldense": "CD Eldense",
    "eibar": "SD Eibar",
    "sd eibar": "SD Eibar",
    "girona": "Girona FC",
    "girona fc": "Girona FC",
    "granada": "Granada CF",
    "granada cf": "Granada CF",
    "leganes": "CD Leganes",
    "cd leganes": "CD Leganes",
    "las palmas": "UD Las Palmas",
    "ud las palmas": "UD Las Palmas",
    "mallorca": "RCD Mallorca",
    "rcd mallorca": "RCD Mallorca",
    "oviedo": "Real Oviedo",
    "real oviedo": "Real Oviedo",
    "real sociedad b": "Real Sociedad B",
    "sociedad b": "Real Sociedad B",
    "sabadell": "CE Sabadell",
    "ce sabadell": "CE Sabadell",
    "sporting gijon": "Real Sporting de Gijon",
    "real sporting de gijon": "Real Sporting de Gijon",
    "sp gijon": "Real Sporting de Gijon",
    "tenerife": "CD Tenerife",
    "cd tenerife": "CD Tenerife",
    "valladolid": "Real Valladolid CF",
    "real valladolid": "Real Valladolid CF",
    "real valladolid cf": "Real Valladolid CF",
}


def ahora_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    try:
        texto = path.read_text(encoding="utf-8").strip()
        if not texto:
            return defecto
        return json.loads(texto)
    except Exception:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalizar(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|sad|club|real|de|del|la|el|futbol|balompie)\b", " ", texto)
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


def es_pretemporada(fecha=None):
    fecha = fecha or datetime.now()
    return fecha.month in {7, 8}


def equipo_cero(nombre, posicion):
    return {
        "equipo": nombre,
        "pj": 0,
        "g": 0,
        "e": 0,
        "p": 0,
        "gf": 0,
        "gc": 0,
        "dg": 0,
        "puntos": 0,
        "pts": 0,
        "posicion": posicion,
        "racha_actual": {"victorias": 0, "empates": 0, "derrotas": 0, "sin_ganar": 0, "sin_perder": 0},
        "tendencias": {
            "puntos_por_partido": 0.0,
            "goles_favor_por_partido": 0.0,
            "goles_contra_por_partido": 0.0,
            "empates_pct": 0.0,
            "forma_5_pts": 0,
            "forma_10_pts": 0,
        },
    }


def tabla_cero(equipos):
    return [equipo_cero(nombre, idx) for idx, nombre in enumerate(equipos, start=1)]


def calendario_vacio(liga, equipos, partidos_por_jornada):
    total_jornadas = (len(equipos) - 1) * 2
    return {
        "competicion": liga,
        "temporada": TEMPORADA,
        "estado": "pretemporada_esperando_calendario_oficial",
        "fuente": "preparar_temporada_2026_2027.py",
        "fuentes_monitorizadas": FUENTES_CALENDARIO[liga],
        "equipos": equipos,
        "jornadas_esperadas": total_jornadas,
        "partidos_por_jornada": partidos_por_jornada,
        "jornadas": [
            {"jornada": jornada, "partidos": [], "estado": "pendiente_calendario_oficial"}
            for jornada in range(1, total_jornadas + 1)
        ],
        "actualizado_en": ahora_iso(),
    }


def fecha_iso(valor):
    texto = str(valor or "").strip()
    if not texto:
        return ""
    for formato in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto[:10], formato).date().isoformat()
        except ValueError:
            pass
    return texto[:10]


def descargar_texto(url):
    if requests is not None:
        respuesta = requests.get(url, headers={"User-Agent": "QuiniHub/1X2 pretemporada"}, timeout=25)
        respuesta.raise_for_status()
        return respuesta.text
    peticion = Request(url, headers={"User-Agent": "QuiniHub/1X2 pretemporada"})
    with urlopen(peticion, timeout=25) as respuesta:
        return respuesta.read().decode("utf-8-sig", errors="replace")


def filas_football_data(liga):
    csv_name = "SP1.csv" if liga == "primera" else "SP2.csv"
    url = f"https://www.football-data.co.uk/mmz4281/{CODIGO_FOOTBALL_DATA}/{csv_name}"
    contenido = descargar_texto(url)
    filas = []
    for fila in csv.DictReader(io.StringIO(contenido)):
        local = canonico(fila.get("HomeTeam"))
        visitante = canonico(fila.get("AwayTeam"))
        if not local or not visitante:
            continue
        resultado = "Pendiente"
        estado = "Pendiente"
        gl = fila.get("FTHG")
        gv = fila.get("FTAG")
        if gl not in (None, "") and gv not in (None, ""):
            try:
                resultado = f"{int(float(gl))}-{int(float(gv))}"
                estado = "Jugado"
            except ValueError:
                pass
        filas.append({
            "fecha": fecha_iso(fila.get("Date")),
            "hora": str(fila.get("Time") or "").strip(),
            "local": local,
            "visitante": visitante,
            "estado": estado,
            "resultado": resultado,
            "fuente": url,
        })
    return url, filas


def construir_calendario_desde_filas(liga, equipos, filas):
    partidos_por_jornada = 10 if liga == "primera" else 11
    calendario = calendario_vacio(liga, equipos, partidos_por_jornada)
    if not filas:
        return calendario
    jornadas = []
    for idx in range(0, len(filas), partidos_por_jornada):
        numero = idx // partidos_por_jornada + 1
        jornadas.append({
            "jornada": numero,
            "partidos": filas[idx: idx + partidos_por_jornada],
            "estado": "integrada_desde_fuente_oficial",
        })
    calendario["jornadas"] = jornadas
    calendario["estado"] = "calendario_integrado"
    calendario["actualizado_en"] = ahora_iso()
    calendario["partidos_integrados"] = len(filas)
    return calendario


def monitorizar_calendario(liga, equipos):
    try:
        fuente, filas = filas_football_data(liga)
    except Exception as exc:
        return None, {"liga": liga, "estado": "esperando_calendario", "error": str(exc), "fuente": FUENTES_CALENDARIO[liga][0]}
    esperados = 380 if liga == "primera" else 462
    if len(filas) < esperados:
        return None, {"liga": liga, "estado": "fuente_sin_calendario_completo", "partidos_detectados": len(filas), "esperados": esperados, "fuente": fuente}
    equipos_detectados = {canonico(p["local"]) for p in filas} | {canonico(p["visitante"]) for p in filas}
    if len(equipos_detectados) != len(equipos):
        return None, {"liga": liga, "estado": "calendario_detectado_no_validado", "equipos_detectados": len(equipos_detectados), "esperados": len(equipos), "fuente": fuente}
    return construir_calendario_desde_filas(liga, equipos, filas), {"liga": liga, "estado": "calendario_integrado", "partidos_detectados": len(filas), "fuente": fuente}


def inicializar_clasificaciones():
    data = cargar_json(CLASIFICACIONES, {})
    historico = data.get("historico_temporadas", {}) if isinstance(data, dict) else {}
    if data:
        historico.setdefault("2025/2026", {
            "preservado_en": ahora_iso(),
            "primera": data.get("primera", []),
            "segunda": data.get("segunda", []),
            "fuentes": data.get("fuentes", {}),
        })
    salida = {
        "actualizado_en": ahora_iso(),
        "temporada": TEMPORADA,
        "modo": "pretemporada_2026_2027",
        "fuente_principal": "preparar_temporada_2026_2027.py",
        "fuentes": {
            "equipos": FUENTES_EQUIPOS,
            "calendario_monitorizado": FUENTES_CALENDARIO,
        },
        "primera": tabla_cero(PRIMERA_2026_2027),
        "segunda": tabla_cero(SEGUNDA_2026_2027),
        "historico_temporadas": historico,
    }
    guardar_json(CLASIFICACIONES, salida)
    return salida


def tiene_partidos_jugados(calendario):
    return any(
        partido.get("estado") == "Jugado"
        for jornada in (calendario or {}).get("jornadas", [])
        for partido in jornada.get("partidos", [])
    )


def archivar_calendario_saliente(liga, existente):
    """Preserva el calendario de la temporada saliente antes de vaciarlo para
    la nueva -sin esto, calendario_vacio() lo borra sin dejar rastro cada vez
    que este script corre en pretemporada (encontrado el 2026-07-22: llevaba
    desde el 2026-07-01 borrando el calendario real 2025/2026 en cada ciclo,
    sin que aprender_patrones_competitivos.py pudiera usarlo nunca)."""
    temporada_saliente = str(existente.get("temporada") or "").strip()
    if not temporada_saliente or temporada_saliente == TEMPORADA:
        return
    if not tiene_partidos_jugados(existente):
        return
    destino = DATA / "historico" / f"calendario_{liga}_{temporada_saliente.replace('/', '_')}.json"
    if destino.exists():
        return
    guardar_json(destino, existente)


def inicializar_o_integrar_calendarios():
    resultados = {}
    for liga, equipos, path, ppj in (
        ("primera", PRIMERA_2026_2027, CALENDARIO_PRIMERA, 10),
        ("segunda", SEGUNDA_2026_2027, CALENDARIO_SEGUNDA, 11),
    ):
        calendario_integrado, estado = monitorizar_calendario(liga, equipos) if es_pretemporada() else (None, {"liga": liga, "estado": "modo_pretemporada_inactivo"})
        if calendario_integrado:
            guardar_json(path, calendario_integrado)
            resultados[liga] = estado
        else:
            existente = cargar_json(path, {})
            if str(existente.get("temporada")) == TEMPORADA and existente.get("jornadas"):
                existente["estado"] = estado.get("estado", existente.get("estado"))
                existente["actualizado_en"] = ahora_iso()
                existente["fuentes_monitorizadas"] = FUENTES_CALENDARIO[liga]
                guardar_json(path, existente)
            else:
                archivar_calendario_saliente(liga, existente)
                guardar_json(path, calendario_vacio(liga, equipos, ppj))
            resultados[liga] = estado
    return resultados


def nuevo_perfil_temporada(nombre, liga, historico_previo=None):
    return {
        "equipo": nombre,
        "liga_actual": liga,
        "temporada_actual": TEMPORADA,
        "partidos_total": 0,
        "temporadas": [TEMPORADA_KEY],
        "historial": [],
        "resumen_ponderado": {
            "partidos_ponderados": 0.0,
            "puntos_por_partido": 0.0,
            "goles_favor_por_partido": 0.0,
            "goles_contra_por_partido": 0.0,
            "empates_pct": 0.0,
            "victorias_pct": 0.0,
            "derrotas_pct": 0.0,
            "surprise_score_medio": 0.0,
        },
        "local": {},
        "visitante": {},
        "forma_reciente": {"forma_5_ppp": 0.0, "forma_10_ppp": 0.0, "racha_actual": {"tipo": "", "partidos": 0}},
        "historico_referencia": historico_previo or {},
        "reset_temporada": {
            "aplicado_en": ahora_iso(),
            "motivo": "Nueva temporada 2026/2027: estadistica de liga reiniciada y historico preservado como referencia.",
        },
    }


def resetear_perfiles_liga():
    data = cargar_json(PERFILES, {})
    equipos_previos = data.get("equipos", {}) if isinstance(data, dict) else {}
    historico = data.get("historico_temporadas", {}) if isinstance(data, dict) else {}
    if equipos_previos:
        historico.setdefault("pre_2026_2027", {"preservado_en": ahora_iso(), "equipos": equipos_previos})

    nuevos = {}
    for liga, equipos in (("primera", PRIMERA_2026_2027), ("segunda", SEGUNDA_2026_2027)):
        for equipo in equipos:
            key = normalizar(equipo)
            previo = equipos_previos.get(key) or {}
            nuevos[key] = nuevo_perfil_temporada(equipo, liga, previo)

    salida = {
        "version": "1.1",
        "generado_en": ahora_iso(),
        "temporada": TEMPORADA,
        "total_equipos": len(nuevos),
        "criterio": "Perfiles de liga reiniciados para equipos 2026/2027; historico anterior queda como referencia.",
        "equipos": nuevos,
        "historico_temporadas": historico,
    }
    guardar_json(PERFILES, salida)
    return salida


def validar_equipos():
    errores = []
    if len(PRIMERA_2026_2027) != 20:
        errores.append(f"Primera tiene {len(PRIMERA_2026_2027)} equipos, esperados 20")
    if len(SEGUNDA_2026_2027) != 22:
        errores.append(f"Segunda tiene {len(SEGUNDA_2026_2027)} equipos, esperados 22")
    duplicados = []
    for liga, equipos in (("primera", PRIMERA_2026_2027), ("segunda", SEGUNDA_2026_2027)):
        vistos = set()
        for equipo in equipos:
            key = normalizar(equipo)
            if key in vistos:
                duplicados.append(f"{liga}: {equipo}")
            vistos.add(key)
    errores.extend(duplicados)
    if errores:
        raise SystemExit("; ".join(errores))


def escribir_estado(resumen_calendarios, clasificaciones, perfiles):
    estado = {
        "version": "1.0",
        "generado_en": ahora_iso(),
        "temporada": TEMPORADA,
        "modo_pretemporada_activo": es_pretemporada(),
        "equipos": {
            "primera": PRIMERA_2026_2027,
            "segunda": SEGUNDA_2026_2027,
        },
        "resumen": {
            "primera_equipos": len(PRIMERA_2026_2027),
            "segunda_equipos": len(SEGUNDA_2026_2027),
            "clasificaciones_inicializadas": bool(clasificaciones.get("primera") and clasificaciones.get("segunda")),
            "perfiles_reset": perfiles.get("total_equipos"),
        },
        "calendarios": resumen_calendarios,
        "siguiente_paso": "En julio-agosto se monitoriza football-data 2627 y fuentes habituales; si aparece calendario completo se integra automaticamente.",
    }
    guardar_json(ESTADO, estado)
    return estado


def main():
    validar_equipos()
    clasificaciones = inicializar_clasificaciones()
    resumen_calendarios = inicializar_o_integrar_calendarios()
    perfiles = resetear_perfiles_liga()
    estado = escribir_estado(resumen_calendarios, clasificaciones, perfiles)
    print(
        "Temporada 2026/2027 preparada: "
        f"{estado['resumen']['primera_equipos']} equipos Primera, "
        f"{estado['resumen']['segunda_equipos']} equipos Segunda. "
        f"Modo pretemporada activo={estado['modo_pretemporada_activo']}."
    )


if __name__ == "__main__":
    main()
