"""Aprendizaje universal desde resultados reales de jornadas.

Este script no aprende de aciertos/fallos propios. Aprende patrones generales del
futbol a partir de signos oficiales de data/jornadas/jornada_*.json, incluso en
jornadas sin prediccion guardada. El resultado se guarda en:
  data/memoria_ia/aprendizaje_historial_universal.json

y se integra como capa base en data/memoria_ia/aprendizaje_global.json cuando esta
memoria ya existe. Es incremental: si no hay jornadas cerradas nuevas desde la
ultima ejecucion, no recalcula todo el historico.
"""

import json
import math
import re
import unicodedata
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
MEMORIA = DATA / "memoria_ia"
SALIDA = MEMORIA / "aprendizaje_historial_universal.json"
APRENDIZAJE_GLOBAL = MEMORIA / "aprendizaje_global.json"
SIGNOS = ("1", "X", "2")
HALF_LIFE_JORNADAS = 18.0


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
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split())


def numero_jornada(path):
    match = re.search(r"(\d+)", Path(path).stem)
    return int(match.group(1)) if match else 0


def signo_oficial(partido):
    signo = str(partido.get("signo_oficial") or "").strip().upper()
    if signo in SIGNOS:
        return signo
    resultado = str(partido.get("resultado") or "").strip()
    match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", resultado)
    if not match:
        return ""
    gl, gv = int(match.group(1)), int(match.group(2))
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def es_jornada_cerrada(data):
    partidos = [p for p in data.get("partidos", []) if 1 <= int(p.get("num") or 0) <= 14]
    if len(partidos) < 14:
        return False
    return all(signo_oficial(p) in SIGNOS for p in partidos)


def contexto_partido(partido, data):
    resolucion = partido.get("resolucion_competicion") or {}
    comp = str(
        partido.get("competicion_resuelta")
        or resolucion.get("competicion")
        or partido.get("competicion")
        or data.get("competicion")
        or ""
    ).lower()
    modelo = str(partido.get("modelo_datos_recomendado") or resolucion.get("modelo_recomendado") or "").lower()
    texto = " ".join([comp, modelo, str(data.get("fuente") or "").lower()])
    if "mundial" in texto or comp == "mundial_2026":
        return "mundial_2026"
    if "seleccion" in texto or "selecciones" in texto or "internacional" in texto:
        return "selecciones"
    if "primera" in texto or "segunda" in texto or "liga" in texto or "laliga" in texto:
        return "liga"
    return "otros"


def fase_partido(partido, contexto):
    resolucion = partido.get("resolucion_competicion") or {}
    fase = str(partido.get("fase") or resolucion.get("fase") or partido.get("ronda") or "").strip().lower()
    if fase:
        return normalizar(fase)
    if contexto == "mundial_2026":
        return "fase_grupos_mundial"
    if contexto == "liga":
        return "liga_regular"
    if contexto == "selecciones":
        return "selecciones_sin_fase"
    return "fase_desconocida"


def peso_jornada(jornada, max_jornada):
    antiguedad = max(int(max_jornada or 0) - int(jornada or 0), 0)
    return round(0.5 ** (antiguedad / HALF_LIFE_JORNADAS), 6)


def stats_vacias():
    return {"pj": 0, "1": 0, "X": 0, "2": 0, "gf": 0, "gc": 0, "puntos_local": 0, "puntos_visitante": 0}


def marcador(partido):
    resultado = str(partido.get("resultado") or "").strip()
    match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", resultado)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def actualizar_equipo(historial, equipo, condicion, signo, goles_favor=0, goles_contra=0):
    key = normalizar(equipo)
    stats = historial.setdefault(key, {"equipo": equipo, "pj": 0, "pts": 0, "gf": 0, "gc": 0, "ultimos": deque(maxlen=8)})
    stats["pj"] += 1
    stats["gf"] += goles_favor
    stats["gc"] += goles_contra
    if condicion == "local":
        pts = 3 if signo == "1" else 1 if signo == "X" else 0
    else:
        pts = 3 if signo == "2" else 1 if signo == "X" else 0
    stats["pts"] += pts
    stats["ultimos"].append(pts)


def fuerza_equipo(historial, equipo):
    stats = historial.get(normalizar(equipo))
    if not stats or stats.get("pj", 0) < 3:
        return None
    pj = max(stats["pj"], 1)
    forma = sum(stats["ultimos"]) / max(len(stats["ultimos"]), 1)
    ppg = stats["pts"] / pj
    dg = (stats["gf"] - stats["gc"]) / pj
    return ppg * 30 + forma * 18 + dg * 10


def prior_desde_counter(counter):
    total = sum(counter.values())
    if total <= 0:
        return {"1": 44.0, "X": 28.0, "2": 28.0}
    return {s: round(counter[s] / total * 100, 2) for s in SIGNOS}


def signo_esperado(partido, contexto, contadores_contexto, historial_equipos):
    prior = prior_desde_counter(contadores_contexto.get(contexto, Counter()))
    fl = fuerza_equipo(historial_equipos, partido.get("local"))
    fv = fuerza_equipo(historial_equipos, partido.get("visitante"))
    if fl is not None and fv is not None:
        diff = fl - fv
        if diff > 9:
            return "1", round(abs(diff), 2), prior, "fuerza_rolling_local"
        if diff < -9:
            return "2", round(abs(diff), 2), prior, "fuerza_rolling_visitante"
        return "X", round(abs(diff), 2), prior, "fuerza_rolling_equilibrada"
    orden = sorted(prior.items(), key=lambda item: item[1], reverse=True)
    margen = round(orden[0][1] - orden[1][1], 2) if len(orden) > 1 else 0.0
    return orden[0][0], margen, prior, "frecuencia_contextual"


def es_sorpresa(signo_real, esperado, margen, prior):
    orden_prior = sorted(prior.items(), key=lambda item: item[1])
    menos_esperado = orden_prior[0][0] if orden_prior else ""
    if signo_real == menos_esperado and (prior.get(signo_real, 0) <= 26 or margen >= 8):
        return True, "signo_menos_frecuente_del_contexto"
    if esperado in SIGNOS and signo_real != esperado and margen >= 10:
        return True, "rompe_signo_esperado_por_modelo_rolling"
    return False, ""


def init_bucket():
    return {
        "partidos": 0,
        "peso_total": 0.0,
        "signos": {s: 0 for s in SIGNOS},
        "signos_ponderados": {s: 0.0 for s in SIGNOS},
        "sorpresas": 0,
        "sorpresas_ponderadas": 0.0,
    }


def sumar_bucket(bucket, signo, peso, sorpresa=False):
    bucket["partidos"] += 1
    bucket["peso_total"] += peso
    bucket["signos"][signo] += 1
    bucket["signos_ponderados"][signo] += peso
    if sorpresa:
        bucket["sorpresas"] += 1
        bucket["sorpresas_ponderadas"] += peso


def cerrar_bucket(bucket):
    total = max(bucket["partidos"], 1)
    total_peso = max(bucket["peso_total"], 0.0001)
    return {
        "partidos": bucket["partidos"],
        "peso_total": round(bucket["peso_total"], 4),
        "frecuencia_real": {s: round(bucket["signos"][s] / total * 100, 2) for s in SIGNOS},
        "frecuencia_ponderada_reciente": {s: round(bucket["signos_ponderados"][s] / total_peso * 100, 2) for s in SIGNOS},
        "sorpresas": bucket["sorpresas"],
        "sorpresas_pct": round(bucket["sorpresas"] / total * 100, 2),
        "sorpresas_ponderadas_pct": round(bucket["sorpresas_ponderadas"] / total_peso * 100, 2),
    }


def cargar_jornadas_cerradas():
    jornadas = []
    for path in sorted(JORNADAS.glob("jornada_*.json"), key=numero_jornada):
        data = cargar_json(path, {})
        jornada = int(data.get("jornada") or numero_jornada(path) or 0)
        if jornada and es_jornada_cerrada(data):
            jornadas.append((jornada, path, data))
    return jornadas


def debe_recalcular(jornadas):
    previo = cargar_json(SALIDA, {})
    max_cerrada = max((j for j, _, _ in jornadas), default=0)
    procesadas = sorted(int(j) for j, _, _ in jornadas)
    estado = previo.get("estado_incremental") or {}
    if estado.get("ultima_jornada_cerrada") == max_cerrada and estado.get("jornadas_cerradas") == procesadas:
        return False, previo
    return True, previo


def inferir_patrones(jornadas):
    max_jornada = max((j for j, _, _ in jornadas), default=0)
    buckets = defaultdict(init_bucket)
    fases = defaultdict(init_bucket)
    incertidumbre = defaultdict(init_bucket)
    contadores_contexto = defaultdict(Counter)
    historial_equipos = {}
    sorpresas = []
    jornadas_resumen = []

    for jornada, path, data in jornadas:
        peso = peso_jornada(jornada, max_jornada)
        signos_jornada = Counter()
        sorpresas_jornada = 0
        for partido in data.get("partidos", []):
            num = int(partido.get("num") or 0)
            if not 1 <= num <= 14:
                continue
            signo = signo_oficial(partido)
            if signo not in SIGNOS:
                continue
            contexto = contexto_partido(partido, data)
            fase = fase_partido(partido, contexto)
            esperado, margen, prior, metodo = signo_esperado(partido, contexto, contadores_contexto, historial_equipos)
            sorpresa, motivo_sorpresa = es_sorpresa(signo, esperado, margen, prior)

            sumar_bucket(buckets["global"], signo, peso, sorpresa)
            sumar_bucket(buckets[contexto], signo, peso, sorpresa)
            if contexto == "mundial_2026":
                sumar_bucket(buckets["selecciones"], signo, peso, sorpresa)
            sumar_bucket(fases[fase], signo, peso, sorpresa)

            if margen < 6:
                tipo_incertidumbre = "muy_equilibrado"
            elif margen < 12:
                tipo_incertidumbre = "margen_corto"
            elif esperado != signo:
                tipo_incertidumbre = "favorito_discutido"
            else:
                tipo_incertidumbre = "favorito_claro"
            sumar_bucket(incertidumbre[tipo_incertidumbre], signo, peso, sorpresa)

            if sorpresa:
                sorpresas_jornada += 1
                sorpresas.append({
                    "jornada": jornada,
                    "num": num,
                    "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
                    "competicion": contexto,
                    "fase": fase,
                    "signo_real": signo,
                    "signo_esperado": esperado,
                    "margen_previo": margen,
                    "motivo": motivo_sorpresa,
                    "metodo_esperado": metodo,
                    "prior_contextual": prior,
                })

            signos_jornada[signo] += 1
            contadores_contexto[contexto][signo] += 1
            m = marcador(partido)
            if m:
                gl, gv = m
                actualizar_equipo(historial_equipos, partido.get("local"), "local", signo, gl, gv)
                actualizar_equipo(historial_equipos, partido.get("visitante"), "visitante", signo, gv, gl)

        jornadas_resumen.append({
            "jornada": jornada,
            "archivo": str(path.relative_to(ROOT)),
            "peso_reciente": peso,
            "signos": {s: signos_jornada[s] for s in SIGNOS},
            "sorpresas": sorpresas_jornada,
        })

    return buckets, fases, incertidumbre, sorpresas, jornadas_resumen


def ordenar_patrones(buckets):
    cerrados = {k: cerrar_bucket(v) for k, v in buckets.items()}
    return dict(sorted(cerrados.items(), key=lambda item: (-item[1]["partidos"], item[0])))


def construir_recomendaciones(patrones_contexto, patrones_incertidumbre, patrones_fase):
    recomendaciones = []
    global_x = patrones_contexto.get("global", {}).get("frecuencia_ponderada_reciente", {}).get("X", 0)
    global_2 = patrones_contexto.get("global", {}).get("frecuencia_ponderada_reciente", {}).get("2", 0)
    for nombre, datos in patrones_contexto.items():
        freq = datos.get("frecuencia_ponderada_reciente", {})
        if nombre != "global" and freq.get("X", 0) >= global_x + 4:
            recomendaciones.append(f"En contexto {nombre}, el empate aparece por encima de la media reciente: subir proteccion de X.")
        if nombre != "global" and freq.get("2", 0) >= global_2 + 4:
            recomendaciones.append(f"En contexto {nombre}, la victoria visitante supera la media reciente: no sobrerreforzar el 1.")
        if datos.get("sorpresas_ponderadas_pct", 0) >= 28:
            recomendaciones.append(f"Contexto {nombre} muestra alta sorpresa reciente: exigir margen mayor antes de fijo.")
    for nombre, datos in patrones_incertidumbre.items():
        freq = datos.get("frecuencia_ponderada_reciente", {})
        if freq.get("X", 0) >= 32:
            recomendaciones.append(f"Patron {nombre}: muchos empates; activar doble con X si el margen del favorito es corto.")
    fases_riesgo = [k for k, v in patrones_fase.items() if v.get("sorpresas_ponderadas_pct", 0) >= 30 and v.get("partidos", 0) >= 6]
    if fases_riesgo:
        recomendaciones.append("Fases mas impredecibles detectadas: " + ", ".join(fases_riesgo[:6]) + ".")
    return recomendaciones[:20]


def integrar_en_memoria_global(aprendizaje):
    memoria = cargar_json(APRENDIZAJE_GLOBAL, {})
    if not memoria:
        return False
    memoria["conocimiento_universal"] = {
        "archivo": "data/memoria_ia/aprendizaje_historial_universal.json",
        "generado_en": aprendizaje.get("generado_en"),
        "jornadas_cerradas": aprendizaje.get("estado_incremental", {}).get("total_jornadas_cerradas"),
        "partidos_analizados": aprendizaje.get("resumen", {}).get("partidos_analizados"),
        "frecuencia_global": aprendizaje.get("patrones_frecuencia", {}).get("por_contexto", {}).get("global", {}),
        "sorpresas": aprendizaje.get("patrones_sorpresa", {}).get("resumen", {}),
        "recomendaciones_base": aprendizaje.get("recomendaciones_modelo", []),
        "criterio": "Capa base universal aprendida de resultados reales; se aplica antes del aprendizaje especifico de predicciones propias.",
    }
    capas = memoria.setdefault("capas_aprendizaje", [])
    capa = "historial_resultados_universal"
    if capa not in capas:
        capas.insert(0, capa)
    guardar_json(APRENDIZAJE_GLOBAL, memoria)
    return True


def main():
    jornadas = cargar_jornadas_cerradas()
    recalcular, previo = debe_recalcular(jornadas)
    if not recalcular:
        print("Aprendizaje universal: sin jornadas cerradas nuevas; no se recalcula.")
        integrar_en_memoria_global(previo)
        return

    buckets, fases, incertidumbre, sorpresas, jornadas_resumen = inferir_patrones(jornadas)
    patrones_contexto = ordenar_patrones(buckets)
    patrones_fase = ordenar_patrones(fases)
    patrones_incertidumbre = ordenar_patrones(incertidumbre)
    total_partidos = patrones_contexto.get("global", {}).get("partidos", 0)
    total_sorpresas = patrones_contexto.get("global", {}).get("sorpresas", 0)
    aprendizaje = {
        "version": "1.0",
        "generado_en": ahora_iso(),
        "estado_incremental": {
            "ultima_jornada_cerrada": max((j for j, _, _ in jornadas), default=0),
            "total_jornadas_cerradas": len(jornadas),
            "jornadas_cerradas": sorted(j for j, _, _ in jornadas),
            "half_life_jornadas": HALF_LIFE_JORNADAS,
            "criterio_recalculo": "Solo recalcula cuando aparece una jornada cerrada nueva o cambia el conjunto de jornadas cerradas.",
        },
        "resumen": {
            "partidos_analizados": total_partidos,
            "jornadas_analizadas": len(jornadas),
            "sorpresas_detectadas": total_sorpresas,
            "sorpresas_pct": round(total_sorpresas / max(total_partidos, 1) * 100, 2),
            "fuente": "data/jornadas/jornada_*.json con signo_oficial 1/X/2",
        },
        "patrones_frecuencia": {
            "por_contexto": patrones_contexto,
            "por_fase": patrones_fase,
            "lectura": "Frecuencias reales y ponderadas por recencia de 1/X/2 sin depender de predicciones propias.",
        },
        "patrones_sorpresa": {
            "resumen": {
                "total": total_sorpresas,
                "porcentaje": round(total_sorpresas / max(total_partidos, 1) * 100, 2),
                "criterio": "Signo menos frecuente del contexto o resultado contrario al signo esperado por modelo rolling con margen suficiente.",
            },
            "ultimas_120": sorpresas[-120:],
        },
        "patrones_incertidumbre": {
            "tipos_enfrentamiento": patrones_incertidumbre,
            "lectura": "Agrupa partidos por margen previo: muy equilibrado, margen corto, favorito discutido y favorito claro.",
        },
        "velocidad_aprendizaje": {
            "half_life_jornadas": HALF_LIFE_JORNADAS,
            "peso_jornada_mas_reciente": 1.0 if jornadas else 0.0,
            "descripcion": "Las jornadas recientes pesan mas que las antiguas para reflejar evolucion tactica y competitiva del futbol.",
            "ultimas_jornadas": jornadas_resumen[-20:],
        },
        "recomendaciones_modelo": construir_recomendaciones(patrones_contexto, patrones_incertidumbre, patrones_fase),
    }
    guardar_json(SALIDA, aprendizaje)
    integrado = integrar_en_memoria_global(aprendizaje)
    print(
        "Aprendizaje universal actualizado: "
        f"{len(jornadas)} jornadas cerradas, {total_partidos} partidos, "
        f"{total_sorpresas} sorpresas. Integrado={integrado}."
    )


if __name__ == "__main__":
    main()
