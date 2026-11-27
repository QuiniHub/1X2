import json
import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import cronologia_jornadas as cj


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
PREDICCIONES = DATA / "predicciones"
SNAPSHOTS = DATA / "backtesting" / "pre_cierre"
MEMORIA = DATA / "memoria_ia"
HISTORIAL_PERMANENTE = MEMORIA / "historial_permanente.json"
PERFILES_EQUIPOS = MEMORIA / "perfiles_equipos.json"
RENDIMIENTO_JORNADAS = MEMORIA / "rendimiento_jornadas.json"
TEMPORADAS_DETECTADAS = MEMORIA / "temporadas_detectadas.json"
ESTADO_AUTONOMIA = MEMORIA / "estado_autonomia.json"

SIGNOS = ("1", "X", "2")
HALF_LIFE_PARTIDOS = 24.0


def ahora():
    return datetime.now(timezone.utc).isoformat()


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalizar(texto):
    # Reparar mojibake ANTES de quitar acentos: 'Belgica' con el acento roto
    # (UTF-8 leido como Latin-1) daba la clave 'ba lgica', que el motor casaba
    # por prefijo con 'Balompie' (Real Betis).
    texto = cj.reparar_mojibake(str(texto or "")).strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|sad|club|real|de|del|la|el|futbol|balompie)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split())


def numero(valor, defecto=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def entero(valor, defecto=0):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


def clamp(valor, minimo=0.0, maximo=100.0):
    return max(min(float(valor), maximo), minimo)


def numero_jornada(path):
    match = re.search(r"(\d+)", Path(path).stem)
    return int(match.group(1)) if match else 0


def parse_fecha(valor, anio_por_defecto=None):
    """Fecha real (datetime) de cualquier texto de fecha del repo; None si no
    se entiende. Nunca se inventa el 1 de enero: 'La Quiniela Domingo, 14 de
    diciembre de 2025' es el 14/12/2025 (cronologia_jornadas.parsear_fecha)."""
    fecha = cj.parsear_fecha(valor, anio_por_defecto=anio_por_defecto)
    if fecha is None:
        return None
    return datetime(fecha.year, fecha.month, fecha.day)


def temporada_de_fecha(fecha, numero=None):
    return cj.temporada_de_fecha(fecha, numero) or "historica"


def fecha_real_jornada(jornada):
    """date del primer partido de la jornada (o la de su cabecera); None si no hay."""
    return cj.fecha_real_jornada(jornada or {})


def fecha_real_partido(jornada, partido):
    """date real del partido: su propia fecha si es valida y cercana a la
    jornada (las erratas lejanas se descartan); si no, la de la jornada."""
    base = fecha_real_jornada(jornada)
    fecha = cj.parsear_fecha((partido or {}).get("fecha"), anio_por_defecto=base.year if base else None)
    if fecha is not None and base is not None and abs((fecha - base).days) > 10:
        fecha = None
    return fecha or base


def fecha_iso(fecha):
    return fecha.isoformat() if fecha else None


def temporada_jornada(jornada, partido=None):
    for fuente in (partido or {}, jornada or {}):
        temporada = fuente.get("temporada") or fuente.get("temporada_base")
        if temporada:
            return str(temporada).replace("/", "_")
    # La temporada es la de la JORNADA (fecha real + numero para desambiguar
    # julio/agosto: J76 de 25/26 se jugo en agosto de 2026).
    fecha = fecha_real_jornada(jornada) or fecha_real_partido(jornada, partido)
    return temporada_de_fecha(fecha, (jornada or {}).get("jornada"))


def signo_de_resultado(valor):
    signo = str(valor or "").strip().upper()
    if signo in SIGNOS:
        return signo
    match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(valor or ""))
    if not match:
        return ""
    local, visitante = int(match.group(1)), int(match.group(2))
    if local > visitante:
        return "1"
    if local == visitante:
        return "X"
    return "2"


def marcador(valor):
    match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(valor or ""))
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def signo_partido(partido):
    return signo_de_resultado(partido.get("signo_oficial") or partido.get("signo_real") or partido.get("resultado"))


def signos_pronostico(valor):
    texto = str(valor or "").upper()
    return "".join(signo for signo in SIGNOS if signo in texto)


def probabilidades_pct(probs):
    valores = {signo: max(numero((probs or {}).get(signo)), 0.0) for signo in SIGNOS}
    total = sum(valores.values())
    if total <= 0:
        return {}
    if total <= 1.5:
        return {signo: round(valores[signo] * 100.0 / total, 4) for signo in SIGNOS}
    return {signo: round(valores[signo] * 100.0 / total, 4) for signo in SIGNOS}


def signo_top(probs):
    probs = probabilidades_pct(probs)
    if not probs:
        return ""
    return max(SIGNOS, key=lambda signo: probs.get(signo, 0.0))


def margen_probabilidades(probs):
    valores = sorted(probabilidades_pct(probs).values(), reverse=True)
    if len(valores) < 2:
        return 0.0
    return round(valores[0] - valores[1], 4)


def surprise_score(prediccion, real):
    probs = probabilidades_pct((prediccion or {}).get("probabilidades") or {})
    if real not in SIGNOS or not probs:
        return None
    top = signo_top(probs)
    prob_real = probs.get(real, 0.0)
    prob_top = probs.get(top, 0.0)
    jugado = signos_pronostico((prediccion or {}).get("signo_final") or (prediccion or {}).get("signo_base"))
    score = (100.0 - prob_real) * 0.62 + max(prob_top - prob_real, 0.0) * 0.28
    if top != real:
        score += 7.5
    if jugado and real not in jugado:
        score += 8.0
    return round(clamp(score), 2)


def confianza_signos(probs):
    valores = probabilidades_pct(probs)
    return {
        signo: {
            "probabilidad": round(valores.get(signo, 0.0), 2),
            "nivel": "alta" if valores.get(signo, 0.0) >= 55 else "media" if valores.get(signo, 0.0) >= 35 else "baja",
        }
        for signo in SIGNOS
    }


def confianza_real_elige8(prediccion):
    probs = probabilidades_pct((prediccion or {}).get("probabilidades") or {})
    if not probs:
        return 0.0
    signos = signos_pronostico((prediccion or {}).get("signo_final") or (prediccion or {}).get("signo_base"))
    if not signos:
        signos = signo_top(probs)
    cubierta = sum(probs.get(signo, 0.0) for signo in signos)
    incertidumbre = numero((prediccion or {}).get("incertidumbre"), 80.0)
    sorpresa = numero((prediccion or {}).get("probabilidad_sorpresa") or (prediccion or {}).get("surprise_score"), 35.0)
    calidad = str((prediccion or {}).get("calidad_datos") or "").lower()
    penalizacion_calidad = 18.0 if calidad == "baja" else 9.0 if calidad in {"media_baja", "media"} else 0.0
    return round(clamp(cubierta * 0.92 + max(probs.values()) * 0.12 - incertidumbre * 0.16 - sorpresa * 0.22 - penalizacion_calidad), 2)


# Nombres de RELLENO: el partido se predijo sin conocer aun al rival
# ('Ganador Octavos 5', '3o Grupo EFGIJ', 'F1 Hypermotion').
_RELLENOS_EQUIPO = (
    re.compile(r"^(ganador|perdedor|vencedor|finalista|semifinalista|clasificado)( |$)"),
    re.compile(r"^[0-9]+ ?[oa]? ?grupo( |$)"),
    re.compile(r"^grupo [a-l]{1,6}$"),
    re.compile(r"^[a-z][0-9] (hypermotion|playoff|play off|ascenso)"),
    re.compile(r"^por (definir|determinar|confirmar)"),
)


def es_equipo_de_relleno(nombre):
    plano = cj.normalizar_equipo(nombre)
    return bool(plano) and any(patron.search(plano) for patron in _RELLENOS_EQUIPO)


def prediccion_es_del_partido(prediccion, partido):
    """True si la prediccion de un 'num' es para ESTE partido y no para otro.

    El numero no basta: hay snapshots hechos con el rival sin decidir
    ('Ganador Octavos 5 - Ganador Octavos 6' en la casilla que luego fue
    Espana-Belgica) o con el partido cambiado despues por la LAE. Se descarta
    si algun nombre es de relleno o si no coincide NINGUNO de los dos equipos;
    con uno basta porque los alias reales no siempre se reconocen
    ('VPS'/'vaasa PS', 'Rep. Irlanda'/'Eire'). Sin nombres en la prediccion
    no hay nada que comparar y se acepta."""
    if not isinstance(prediccion, dict) or not prediccion:
        return False
    local, visitante = prediccion.get("local"), prediccion.get("visitante")
    nombres = [n for n in (local, visitante) if isinstance(n, str) and n.strip()]
    if not nombres:
        return True
    if any(es_equipo_de_relleno(n) for n in nombres):
        return False
    return bool(
        cj.mismo_equipo(local, (partido or {}).get("local"))
        or cj.mismo_equipo(visitante, (partido or {}).get("visitante"))
    )


def prediccion_del_partido(partido, del_cierre, del_espejo=None):
    """(prediccion, origen) para un partido: la principal si es de ese
    partido; si no, la del espejo si lo es; si no, ninguna."""
    if prediccion_es_del_partido(del_cierre, partido):
        return del_cierre, "principal"
    if prediccion_es_del_partido(del_espejo, partido):
        return del_espejo, "respaldo_espejo"
    return {}, ("descartada_otro_partido" if (del_cierre or del_espejo) else "sin_prediccion")


def espejo_es_de_la_jornada(espejo, jornada):
    """El espejo data/predicciones/jornada_N.json solo vale si es de la MISMA
    jornada real: la numeracion se reinicia cada temporada y el jornada_28 de
    la 25/26 no puede emparejarse con la J28 de la 26/27. Si no hay equipos
    que comparar (espejo o jornada sin nombres) no se puede negar y se acepta."""
    if not isinstance(jornada, dict):
        return True
    _, comparables = cj.coincidencia_equipos(espejo, jornada)
    if not comparables:
        return True
    return cj.misma_jornada(espejo, jornada)


def cargar_predicciones():
    """Prediccion por numero de jornada. Manda el snapshot pre-cierre (lo que
    se dijo ANTES del primer partido); el espejo data/predicciones/jornada_N
    se regenera despues del cierre y solo vale de respaldo. Los dos se
    comprueban contra la jornada real (equipos), no solo por el numero."""
    predicciones = {}
    espejos = {}
    for path in sorted(PREDICCIONES.glob("jornada_*.json"), key=numero_jornada):
        data = cargar_json(path, {})
        if not isinstance(data, dict):
            continue
        jornada = entero(data.get("jornada") or numero_jornada(path))
        if not jornada:
            continue
        if not espejo_es_de_la_jornada(data, cj.cargar_jornada(jornada, JORNADAS)):
            continue
        espejos[jornada] = data
        predicciones[jornada] = dict(data, origen_prediccion_memoria="espejo_post_cierre")
    if SNAPSHOTS.exists():
        for path in sorted(SNAPSHOTS.glob("jornada_*.json"), key=numero_jornada):
            jornada = numero_jornada(path)
            if not jornada:
                continue
            # Comprueba que el snapshot es de la MISMA jornada real (equipos o
            # fecha) y no de la jornada N de otra temporada.
            pred = cj.prediccion_del_cierre(jornada, SNAPSHOTS, JORNADAS)
            if pred and pred.get("partidos"):
                predicciones[jornada] = dict(
                    pred,
                    origen_prediccion_memoria="snapshot_pre_cierre",
                    # por si algun partido del snapshot no es el que se jugo
                    respaldo_espejo_partidos=(espejos.get(jornada) or {}).get("partidos") or [],
                )
    return predicciones


def predicciones_por_partido(prediccion):
    return {
        entero(partido.get("num")): partido
        for partido in (prediccion or {}).get("partidos", [])
        if isinstance(partido, dict) and 1 <= entero(partido.get("num")) <= 14
    }


def iter_jornadas():
    """Jornadas en orden CRONOLOGICO real (no por numero: la numeracion se
    reinicia cada temporada). Las que no tienen fecha van al principio."""
    filas = []
    for path in JORNADAS.glob("jornada_*.json"):
        data = cargar_json(path, {})
        if not isinstance(data, dict):
            continue
        jornada = entero(data.get("jornada") or numero_jornada(path))
        if jornada:
            filas.append((fecha_iso(fecha_real_jornada(data)) or "", jornada, data))
    filas.sort(key=lambda fila: (fila[0], fila[1]))
    for _, jornada, data in filas:
        yield jornada, data


def acierto_pronostico(pronostico, real):
    signos = signos_pronostico(pronostico)
    return bool(real in SIGNOS and signos and real in signos)


def registro_partido(jornada_num, jornada, partido, prediccion):
    num = entero(partido.get("num"))
    real = signo_partido(partido)
    probs = probabilidades_pct((prediccion or {}).get("probabilidades") or {})
    score_sorpresa = surprise_score(prediccion, real)
    signo_final = (prediccion or {}).get("signo_final") or partido.get("signo_nuestro")
    return {
        "jornada": jornada_num,
        "temporada": temporada_jornada(jornada, partido),
        "fecha": partido.get("fecha") or jornada.get("fecha"),
        "fecha_iso": fecha_iso(fecha_real_partido(jornada, partido)),
        "num": num,
        "local": partido.get("local"),
        "visitante": partido.get("visitante"),
        "resultado": partido.get("resultado"),
        "signo_real": real,
        "prediccion_disponible": bool(prediccion and prediccion.get("probabilidades")),
        "signo_final": signo_final,
        "tipo": (prediccion or {}).get("tipo") or "",
        "doble": str((prediccion or {}).get("tipo") or "").upper() == "DOBLE",
        "triple": str((prediccion or {}).get("tipo") or "").upper() == "TRIPLE",
        "elige8": bool((prediccion or {}).get("elige8")),
        "probabilidades": probs,
        "confianza_signos": confianza_signos(probs),
        "confianza_top": round(max(probs.values()), 2) if probs else None,
        "margen_probabilidad": margen_probabilidades(probs),
        "incertidumbre": (prediccion or {}).get("incertidumbre"),
        "surprise_score": score_sorpresa,
        "confianza_real_elige8": confianza_real_elige8(prediccion),
        "acierto": acierto_pronostico(signo_final, real),
        "acierto_top": signo_top(probs) == real if probs and real in SIGNOS else None,
    }


def construir_historial_permanente():
    predicciones = cargar_predicciones()
    partidos = []
    jornadas = {}
    for jornada_num, jornada in iter_jornadas():
        pred = predicciones.get(jornada_num, {})
        pred_partidos = predicciones_por_partido(pred)
        respaldo_partidos = predicciones_por_partido({"partidos": pred.get("respaldo_espejo_partidos") or []})
        registros = []
        de_respaldo = []
        descartadas = []
        for partido in jornada.get("partidos", []):
            num = entero(partido.get("num"))
            if not 1 <= num <= 14:
                continue
            # El 'num' no basta: la prediccion tiene que ser de ESTE partido.
            pred_partido, origen = prediccion_del_partido(partido, pred_partidos.get(num), respaldo_partidos.get(num))
            if origen == "respaldo_espejo":
                de_respaldo.append(num)
            elif origen == "descartada_otro_partido":
                descartadas.append(num)
            item = registro_partido(jornada_num, jornada, partido, pred_partido)
            partidos.append(item)
            registros.append(item)
        jornadas[str(jornada_num)] = {
            "jornada": jornada_num,
            "temporada": temporada_jornada(jornada),
            "fecha": jornada.get("fecha") or jornada.get("fecha_texto"),
            "fecha_iso": fecha_iso(fecha_real_jornada(jornada)),
            "origen_prediccion": pred.get("origen_prediccion_memoria") if pred else None,
            "predicciones_de_respaldo_espejo": de_respaldo,
            "predicciones_descartadas_otro_partido": descartadas,
            "estado": jornada.get("estado"),
            "partidos": len(registros),
            "cerrados": sum(1 for item in registros if item["signo_real"] in SIGNOS),
            "predicciones_disponibles": sum(1 for item in registros if item["prediccion_disponible"]),
            "elige8": [item["num"] for item in registros if item["elige8"]],
            "dobles": [item["num"] for item in registros if item["doble"]],
            "triples": [item["num"] for item in registros if item["triple"]],
        }
    return {
        "version": "1.0",
        "generado_en": ahora(),
        "retencion": "permanente_no_borrar",
        "total_jornadas": len(jornadas),
        "total_partidos": len(partidos),
        "jornadas": jornadas,
        "partidos": partidos,
    }


def puntos_equipo(signo_real, condicion):
    if signo_real == "X":
        return 1
    if condicion == "local" and signo_real == "1":
        return 3
    if condicion == "visitante" and signo_real == "2":
        return 3
    return 0


def signo_equipo(signo_real, condicion):
    puntos = puntos_equipo(signo_real, condicion)
    return "G" if puntos == 3 else "E" if puntos == 1 else "P"


def peso_reciente(indice, total, half_life=HALF_LIFE_PARTIDOS):
    edad = max(total - indice - 1, 0)
    return 0.5 ** (edad / max(float(half_life), 1.0))


def nuevo_perfil(nombre):
    return {
        "equipo": nombre,
        "key": normalizar(nombre),
        "temporadas": [],
        "partidos_total": 0,
        "historial": [],
    }


def agregar_partido_perfil(perfil, item, condicion):
    score = marcador(item.get("resultado"))
    if not score or item.get("signo_real") not in SIGNOS:
        return
    gl, gv = score
    gf, gc = (gl, gv) if condicion == "local" else (gv, gl)
    rival = item["visitante"] if condicion == "local" else item["local"]
    perfil["partidos_total"] += 1
    if item["temporada"] not in perfil["temporadas"]:
        perfil["temporadas"].append(item["temporada"])
    perfil["historial"].append({
        "jornada": item["jornada"],
        "temporada": item["temporada"],
        "fecha": item.get("fecha"),
        "fecha_iso": item.get("fecha_iso") or fecha_iso(cj.parsear_fecha(item.get("fecha"))),
        "condicion": condicion,
        "rival": rival,
        "gf": gf,
        "gc": gc,
        "signo_equipo": signo_equipo(item["signo_real"], condicion),
        "puntos": puntos_equipo(item["signo_real"], condicion),
        "signo_quiniela": item["signo_real"],
        "surprise_score": item.get("surprise_score"),
    })


def sumar_stats(stats, entrada, peso):
    stats["pj"] += peso
    stats["gf"] += entrada["gf"] * peso
    stats["gc"] += entrada["gc"] * peso
    stats["pts"] += entrada["puntos"] * peso
    stats["g"] += (1 if entrada["signo_equipo"] == "G" else 0) * peso
    stats["e"] += (1 if entrada["signo_equipo"] == "E" else 0) * peso
    stats["p"] += (1 if entrada["signo_equipo"] == "P" else 0) * peso
    if entrada.get("surprise_score") is not None:
        stats["surprise_score"] += numero(entrada.get("surprise_score")) * peso
        stats["surprise_pj"] += peso


def stats_vacias():
    return {"pj": 0.0, "g": 0.0, "e": 0.0, "p": 0.0, "gf": 0.0, "gc": 0.0, "pts": 0.0, "surprise_score": 0.0, "surprise_pj": 0.0}


def cerrar_stats(stats):
    pj = max(stats["pj"], 0.0001)
    return {
        "partidos_ponderados": round(stats["pj"], 3),
        "puntos_por_partido": round(stats["pts"] / pj, 3),
        "goles_favor_por_partido": round(stats["gf"] / pj, 3),
        "goles_contra_por_partido": round(stats["gc"] / pj, 3),
        "empates_pct": round(stats["e"] / pj * 100.0, 2),
        "victorias_pct": round(stats["g"] / pj * 100.0, 2),
        "derrotas_pct": round(stats["p"] / pj * 100.0, 2),
        "surprise_score_medio": round(stats["surprise_score"] / max(stats["surprise_pj"], 0.0001), 2) if stats["surprise_pj"] else 0.0,
    }


def racha_actual(historial):
    if not historial:
        return {"tipo": "", "partidos": 0}
    ultimo = historial[-1]["signo_equipo"]
    total = 0
    for item in reversed(historial):
        if item["signo_equipo"] != ultimo:
            break
        total += 1
    return {"tipo": ultimo, "partidos": total}


def forma_ppp(historial, n):
    recientes = historial[-n:]
    if not recientes:
        return 0.0
    return round(sum(item["puntos"] for item in recientes) / len(recientes), 3)


def clave_cronologica(entrada):
    """Orden por FECHA REAL (ISO). La fecha en texto ('La Quiniela Domingo, 14
    de diciembre de 2025') no sirve para ordenar: quedaba detras de '2026-...'.
    Sin fecha, la entrada va al principio (la mas antigua), por temporada y jornada."""
    return (
        entrada.get("fecha_iso") or fecha_iso(cj.parsear_fecha(entrada.get("fecha"))) or "",
        str(entrada.get("temporada") or ""),
        entero(entrada.get("jornada")),
    )


def cerrar_perfil(perfil):
    historial = sorted(perfil["historial"], key=clave_cronologica)
    total = len(historial)
    global_stats = stats_vacias()
    local_stats = stats_vacias()
    visitante_stats = stats_vacias()
    for idx, entrada in enumerate(historial):
        peso = peso_reciente(idx, total)
        sumar_stats(global_stats, entrada, peso)
        if entrada["condicion"] == "local":
            sumar_stats(local_stats, entrada, peso)
        else:
            sumar_stats(visitante_stats, entrada, peso)
    perfil["historial"] = historial
    perfil["temporadas"] = sorted(perfil["temporadas"])
    perfil["decay"] = {"half_life_partidos": HALF_LIFE_PARTIDOS, "criterio": "los partidos recientes pesan mas que los antiguos"}
    perfil["resumen_ponderado"] = cerrar_stats(global_stats)
    perfil["local"] = cerrar_stats(local_stats)
    perfil["visitante"] = cerrar_stats(visitante_stats)
    perfil["forma_reciente"] = {
        "forma_5_ppp": forma_ppp(historial, 5),
        "forma_10_ppp": forma_ppp(historial, 10),
        "racha_actual": racha_actual(historial),
    }
    perfil["historial"] = historial[-120:]
    return perfil


def construir_perfiles_equipos(historial):
    perfiles = {}
    for item in historial.get("partidos", []):
        if item.get("signo_real") not in SIGNOS:
            continue
        for condicion, nombre in (("local", item.get("local")), ("visitante", item.get("visitante"))):
            key = normalizar(nombre)
            if not key:
                continue
            perfiles.setdefault(key, nuevo_perfil(cj.reparar_mojibake(nombre)))
            agregar_partido_perfil(perfiles[key], item, condicion)
    perfiles = {key: cerrar_perfil(perfil) for key, perfil in sorted(perfiles.items())}
    return {
        "version": "1.0",
        "generado_en": ahora(),
        "total_equipos": len(perfiles),
        "decay": {"half_life_partidos": HALF_LIFE_PARTIDOS},
        "equipos": perfiles,
    }


def detectar_temporadas(historial):
    temporadas = defaultdict(lambda: {"jornadas": set(), "equipos": set(), "partidos": 0})
    for item in historial.get("partidos", []):
        temporada = item.get("temporada") or "historica"
        temporadas[temporada]["jornadas"].add(item.get("jornada"))
        if item.get("local"):
            temporadas[temporada]["equipos"].add(cj.reparar_mojibake(item.get("local")))
        if item.get("visitante"):
            temporadas[temporada]["equipos"].add(cj.reparar_mojibake(item.get("visitante")))
        temporadas[temporada]["partidos"] += 1
    salida = {}
    prev_equipos = set()
    for temporada in sorted(temporadas):
        equipos = temporadas[temporada]["equipos"]
        salida[temporada] = {
            "temporada": temporada,
            "jornadas_cargadas": sorted(n for n in temporadas[temporada]["jornadas"] if n),
            "partidos": temporadas[temporada]["partidos"],
            "equipos": sorted(equipos),
            "altas_detectadas": sorted(equipos - prev_equipos) if prev_equipos else sorted(equipos),
            "bajas_detectadas": sorted(prev_equipos - equipos) if prev_equipos else [],
        }
        prev_equipos = equipos
    return {
        "version": "1.0",
        "generado_en": ahora(),
        "criterio": "deteccion por equipos presentes en jornadas cargadas; no borra historico",
        "temporadas": salida,
    }


def metricas_jornada(items):
    cerrados = [item for item in items if item.get("signo_real") in SIGNOS]
    predichos = [item for item in cerrados if item.get("prediccion_disponible")]
    por_tipo = {}
    for tipo in ("FIJO", "DOBLE", "TRIPLE"):
        grupo = [item for item in predichos if str(item.get("tipo") or "").upper() == tipo]
        por_tipo[tipo] = {
            "total": len(grupo),
            "aciertos": sum(1 for item in grupo if item.get("acierto")),
            "precision": round(sum(1 for item in grupo if item.get("acierto")) / max(len(grupo), 1) * 100.0, 2) if grupo else None,
        }
    brier = []
    logloss = []
    for item in predichos:
        probs = item.get("probabilidades") or {}
        real = item.get("signo_real")
        if real not in SIGNOS or not probs:
            continue
        brier.append(sum(((probs.get(signo, 0.0) / 100.0) - (1.0 if signo == real else 0.0)) ** 2 for signo in SIGNOS))
        logloss.append(-math.log(max(probs.get(real, 0.0) / 100.0, 1e-9)))
    elige8 = [item for item in predichos if item.get("elige8")]
    return {
        "partidos_cerrados": len(cerrados),
        "partidos_con_prediccion": len(predichos),
        "precision_boleto": round(sum(1 for item in predichos if item.get("acierto")) / max(len(predichos), 1) * 100.0, 2) if predichos else None,
        "precision_top1": round(sum(1 for item in predichos if item.get("acierto_top")) / max(len(predichos), 1) * 100.0, 2) if predichos else None,
        "brier_medio": round(sum(brier) / len(brier), 4) if brier else None,
        "logloss_medio": round(sum(logloss) / len(logloss), 4) if logloss else None,
        "por_tipo": por_tipo,
        "elige8": {
            "selecciones": len(elige8),
            "aciertos": sum(1 for item in elige8 if item.get("acierto")),
            "precision": round(sum(1 for item in elige8 if item.get("acierto")) / max(len(elige8), 1) * 100.0, 2) if elige8 else None,
        },
        "surprise_score_medio": round(
            sum(numero(item.get("surprise_score")) for item in predichos if item.get("surprise_score") is not None)
            / max(sum(1 for item in predichos if item.get("surprise_score") is not None), 1),
            2,
        ) if predichos else None,
        "ranking_incertidumbre": sorted(
            [
                {
                    "num": item["num"],
                    "partido": f"{item.get('local')} - {item.get('visitante')}",
                    "incertidumbre": item.get("incertidumbre"),
                    "surprise_score": item.get("surprise_score"),
                    "margen_probabilidad": item.get("margen_probabilidad"),
                }
                for item in predichos
            ],
            key=lambda x: (numero(x.get("incertidumbre")), numero(x.get("surprise_score")), -numero(x.get("margen_probabilidad"))),
            reverse=True,
        )[:8],
        "ranking_elige8_confianza_real": sorted(
            [
                {
                    "num": item["num"],
                    "partido": f"{item.get('local')} - {item.get('visitante')}",
                    "confianza_real_elige8": item.get("confianza_real_elige8"),
                    "elige8": item.get("elige8"),
                }
                for item in predichos
            ],
            key=lambda x: numero(x.get("confianza_real_elige8")),
            reverse=True,
        )[:8],
    }


def construir_rendimiento(historial):
    por_jornada = {}
    for item in historial.get("partidos", []):
        por_jornada.setdefault(str(item["jornada"]), []).append(item)
    def fecha_jornada(clave):
        # Fecha real del primer partido de la jornada (clave = numero en texto).
        fechas = [item.get("fecha_iso") for item in por_jornada[clave] if item.get("fecha_iso")]
        return min(fechas) if fechas else ""

    # Orden CRONOLOGICO: por numero, las "ultimas 8" eran J69-J76 de la 25/26.
    jornadas = {
        jornada: {
            "jornada": entero(jornada),
            "fecha_iso": fecha_jornada(jornada) or None,
            "temporada": (items[0].get("temporada") if items else None),
            **metricas_jornada(items),
        }
        for jornada, items in sorted(por_jornada.items(), key=lambda kv: (fecha_jornada(kv[0]), entero(kv[0])))
    }
    cerradas = [j for j in jornadas.values() if j["partidos_cerrados"] >= 14 and j["partidos_con_prediccion"]]
    ultimas = cerradas[-8:]
    return {
        "version": "1.0",
        "generado_en": ahora(),
        "jornadas": jornadas,
        "resumen": {
            "jornadas_evaluadas": len(cerradas),
            "ultimas_8_jornadas": [j["jornada"] for j in ultimas],
            "precision_media_ultimas_8": round(
                sum(numero(j.get("precision_boleto")) for j in ultimas) / max(len(ultimas), 1),
                2,
            ) if ultimas else None,
            "criterio_aprendizaje": "tras cada jornada cerrada se compara prediccion vs resultado y se reentrena la memoria",
        },
    }


def construir_estado_autonomia(historial, perfiles, temporadas, rendimiento):
    jornadas = historial.get("jornadas", {})
    # "Ultima" es la mas reciente por FECHA real, no la de numero mas alto
    # (J76 es de agosto de 2026, temporada 25/26).
    def por_fecha(clave):
        return ((jornadas.get(clave) or {}).get("fecha_iso") or "", entero(clave))

    ultima = entero(max(jornadas, key=por_fecha, default=0))
    ultima_info = jornadas.get(str(ultima), {})
    cerradas = [k for k, v in jornadas.items() if v.get("cerrados", 0) >= 14]
    estado = "lista_para_aprender" if ultima_info.get("cerrados", 0) >= 14 else "esperando_resultados"
    return {
        "version": "1.0",
        "generado_en": ahora(),
        "estado": estado,
        "ultima_jornada_detectada": ultima,
        "ultima_jornada_cerrada": entero(max(cerradas, key=por_fecha, default=0)),
        "ultima_jornada_detectada_fecha": ultima_info.get("fecha_iso"),
        "temporada_actual": ultima_info.get("temporada"),
        "memoria_permanente": {
            "historial_partidos": HISTORIAL_PERMANENTE.as_posix(),
            "perfiles_equipos": PERFILES_EQUIPOS.as_posix(),
            "rendimiento": RENDIMIENTO_JORNADAS.as_posix(),
            "temporadas": TEMPORADAS_DETECTADAS.as_posix(),
            "retencion": "append/reconstruccion_desde_fuentes_sin_borrar_historico",
        },
        "totales": {
            "jornadas": historial.get("total_jornadas", 0),
            "partidos": historial.get("total_partidos", 0),
            "equipos": perfiles.get("total_equipos", 0),
            "temporadas": len(temporadas.get("temporadas", {})),
            "jornadas_evaluadas": rendimiento.get("resumen", {}).get("jornadas_evaluadas", 0),
        },
        "politica": {
            "prediccion_siguiente": "bloqueada_hasta_cerrar_y_aprender_jornada_anterior",
            "dobles_triples": "solo ranking de mayor incertidumbre",
            "elige8": "ranking por confianza real, no por favorito simple",
            "pesos": "actualizacion con rendimiento, limites y decay temporal",
        },
    }


def actualizar_memoria_autonoma(root=ROOT):
    global ROOT, DATA, JORNADAS, PREDICCIONES, SNAPSHOTS, MEMORIA
    global HISTORIAL_PERMANENTE, PERFILES_EQUIPOS, RENDIMIENTO_JORNADAS, TEMPORADAS_DETECTADAS, ESTADO_AUTONOMIA
    ROOT = Path(root)
    DATA = ROOT / "data"
    JORNADAS = DATA / "jornadas"
    PREDICCIONES = DATA / "predicciones"
    SNAPSHOTS = DATA / "backtesting" / "pre_cierre"
    MEMORIA = DATA / "memoria_ia"
    HISTORIAL_PERMANENTE = MEMORIA / "historial_permanente.json"
    PERFILES_EQUIPOS = MEMORIA / "perfiles_equipos.json"
    RENDIMIENTO_JORNADAS = MEMORIA / "rendimiento_jornadas.json"
    TEMPORADAS_DETECTADAS = MEMORIA / "temporadas_detectadas.json"
    ESTADO_AUTONOMIA = MEMORIA / "estado_autonomia.json"

    historial = construir_historial_permanente()
    perfiles = construir_perfiles_equipos(historial)
    temporadas = detectar_temporadas(historial)
    rendimiento = construir_rendimiento(historial)
    estado = construir_estado_autonomia(historial, perfiles, temporadas, rendimiento)
    guardar_json(HISTORIAL_PERMANENTE, historial)
    guardar_json(PERFILES_EQUIPOS, perfiles)
    guardar_json(TEMPORADAS_DETECTADAS, temporadas)
    guardar_json(RENDIMIENTO_JORNADAS, rendimiento)
    guardar_json(ESTADO_AUTONOMIA, estado)
    return estado


def main():
    estado = actualizar_memoria_autonoma(ROOT)
    print(
        "Memoria autonoma actualizada: "
        f"{estado['totales']['jornadas']} jornadas, {estado['totales']['equipos']} equipos, "
        f"estado={estado['estado']}"
    )


if __name__ == "__main__":
    main()
