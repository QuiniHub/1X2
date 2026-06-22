import json
import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


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
    texto = str(texto or "").strip().lower()
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


def parse_fecha(valor):
    texto = str(valor or "").strip()
    if not texto:
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto[:10], formato)
        except ValueError:
            pass
    match = re.search(r"(20\d{2})", texto)
    if match:
        return datetime(int(match.group(1)), 1, 1)
    return None


def temporada_de_fecha(fecha):
    if not fecha:
        return "historica"
    year = fecha.year
    if fecha.month >= 8:
        return f"{year}_{year + 1}"
    return f"{year - 1}_{year}"


def temporada_jornada(jornada, partido=None):
    for fuente in (partido or {}, jornada or {}):
        temporada = fuente.get("temporada") or fuente.get("temporada_base")
        if temporada:
            return str(temporada).replace("/", "_")
    fecha = parse_fecha((partido or {}).get("fecha") or (jornada or {}).get("fecha"))
    return temporada_de_fecha(fecha)


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


def cargar_predicciones():
    predicciones = {}
    for path in sorted(PREDICCIONES.glob("jornada_*.json"), key=numero_jornada):
        data = cargar_json(path, {})
        jornada = entero(data.get("jornada") or numero_jornada(path))
        if jornada:
            predicciones[jornada] = data
    if SNAPSHOTS.exists():
        for path in sorted(SNAPSHOTS.glob("jornada_*.json"), key=numero_jornada):
            snap = cargar_json(path, {})
            pred = snap.get("prediccion") or snap
            jornada = entero(snap.get("jornada") or pred.get("jornada") or numero_jornada(path))
            if jornada and pred:
                predicciones.setdefault(jornada, pred)
    return predicciones


def predicciones_por_partido(prediccion):
    return {
        entero(partido.get("num")): partido
        for partido in (prediccion or {}).get("partidos", [])
        if 1 <= entero(partido.get("num")) <= 14
    }


def iter_jornadas():
    for path in sorted(JORNADAS.glob("jornada_*.json"), key=numero_jornada):
        data = cargar_json(path, {})
        jornada = entero(data.get("jornada") or numero_jornada(path))
        if jornada:
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
        registros = []
        for partido in jornada.get("partidos", []):
            num = entero(partido.get("num"))
            if not 1 <= num <= 14:
                continue
            item = registro_partido(jornada_num, jornada, partido, pred_partidos.get(num, {}))
            partidos.append(item)
            registros.append(item)
        jornadas[str(jornada_num)] = {
            "jornada": jornada_num,
            "temporada": temporada_jornada(jornada),
            "fecha": jornada.get("fecha") or jornada.get("fecha_texto"),
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


def cerrar_perfil(perfil):
    historial = sorted(perfil["historial"], key=lambda x: (x.get("fecha") or "", x.get("jornada") or 0))
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
            perfiles.setdefault(key, nuevo_perfil(nombre))
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
            temporadas[temporada]["equipos"].add(item.get("local"))
        if item.get("visitante"):
            temporadas[temporada]["equipos"].add(item.get("visitante"))
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
    jornadas = {
        jornada: {"jornada": entero(jornada), **metricas_jornada(items)}
        for jornada, items in sorted(por_jornada.items(), key=lambda kv: entero(kv[0]))
    }
    cerradas = [j for j in jornadas.values() if j["partidos_cerrados"] >= 14 and j["partidos_con_prediccion"]]
    ultimas = cerradas[-8:]
    return {
        "version": "1.0",
        "generado_en": ahora(),
        "jornadas": jornadas,
        "resumen": {
            "jornadas_evaluadas": len(cerradas),
            "precision_media_ultimas_8": round(
                sum(numero(j.get("precision_boleto")) for j in ultimas) / max(len(ultimas), 1),
                2,
            ) if ultimas else None,
            "criterio_aprendizaje": "tras cada jornada cerrada se compara prediccion vs resultado y se reentrena la memoria",
        },
    }


def construir_estado_autonomia(historial, perfiles, temporadas, rendimiento):
    jornadas = historial.get("jornadas", {})
    ultima = max((entero(k) for k in jornadas), default=0)
    ultima_info = jornadas.get(str(ultima), {})
    estado = "lista_para_aprender" if ultima_info.get("cerrados", 0) >= 14 else "esperando_resultados"
    return {
        "version": "1.0",
        "generado_en": ahora(),
        "estado": estado,
        "ultima_jornada_detectada": ultima,
        "ultima_jornada_cerrada": max((entero(k) for k, v in jornadas.items() if v.get("cerrados", 0) >= 14), default=0),
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
