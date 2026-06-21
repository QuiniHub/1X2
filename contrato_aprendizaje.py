import json
import re
import unicodedata
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path


SIGNOS = ("1", "X", "2")
TEMPORADA_DEFECTO = "2025/2026"
COMPETICION_DEFECTO = "quiniela"


def utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def reparar_mojibake(texto):
    texto = str(texto or "")
    try:
        reparado = texto.encode("latin1").decode("utf-8")
        if "ï¿½" not in reparado:
            return reparado
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return texto


def normalizar_texto(texto):
    texto = reparar_mojibake(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|sad|club|real|de|del|la|el)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def slug(texto):
    valor = normalizar_texto(texto)
    return re.sub(r"[^a-z0-9]+", "-", valor).strip("-") or "sin-equipo"


def int_o_cero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def partido_id(jornada, num, local, visitante, temporada=TEMPORADA_DEFECTO, competicion=COMPETICION_DEFECTO):
    temporada_txt = slug(str(temporada or TEMPORADA_DEFECTO).replace("/", "_"))
    competicion_txt = slug(competicion or COMPETICION_DEFECTO)
    jornada_txt = str(int_o_cero(jornada)).zfill(3)
    num_txt = str(int_o_cero(num)).zfill(2)
    return f"{temporada_txt}_{competicion_txt}_j{jornada_txt}_p{num_txt}_{slug(local)}_{slug(visitante)}"


def signo_resultado(resultado):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(resultado or ""))
    if not m:
        return None
    gl, gv = int(m.group(1)), int(m.group(2))
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def normalizar_probabilidades(probs):
    probs = probs or {}
    valores = {}
    for signo in SIGNOS:
        try:
            valores[signo] = max(float(probs.get(signo) or 0), 0.0)
        except (TypeError, ValueError):
            valores[signo] = 0.0
    total = sum(valores.values())
    if total <= 0:
        return {signo: round(100.0 / 3.0, 2) for signo in SIGNOS}
    return {signo: round(valores[signo] / total * 100.0, 2) for signo in SIGNOS}


def ordenar_probabilidades(probs):
    probs = normalizar_probabilidades(probs)
    return sorted(SIGNOS, key=lambda signo: (-float(probs.get(signo) or 0), SIGNOS.index(signo)))


def signo_top(probs):
    return ordenar_probabilidades(probs)[0]


def signos_top2(probs):
    return ordenar_probabilidades(probs)[:2]


def signos_pronostico(valor):
    texto = str(valor or "").upper()
    return {signo for signo in SIGNOS if signo in texto}


def tipo_apuesta(valor):
    total = len(signos_pronostico(valor))
    if total >= 3:
        return "TRIPLE"
    if total == 2:
        return "DOBLE"
    if total == 1:
        return "FIJO"
    return "NO_VALIDO"


def probabilidad_signo(probs, signo):
    if signo not in SIGNOS:
        return None
    return round(float(normalizar_probabilidades(probs).get(signo) or 0), 2)


def ranking_signo(probs, signo):
    if signo not in SIGNOS:
        return None
    return ordenar_probabilidades(probs).index(signo) + 1


def brier_score(probs, signo_real):
    if signo_real not in SIGNOS:
        return None
    probs = normalizar_probabilidades(probs)
    total = 0.0
    for signo in SIGNOS:
        esperado = 1.0 if signo == signo_real else 0.0
        total += ((float(probs.get(signo) or 0) / 100.0) - esperado) ** 2
    return round(total, 6)


def nivel_confianza(probs):
    top = probabilidad_signo(probs, signo_top(probs))
    if top >= 60:
        return "alta"
    if top >= 45:
        return "media"
    return "baja"


def bool_sorpresa(categoria, ranking_real, favorito, signo_real):
    categoria_txt = str(categoria or "").lower()
    return (
        ranking_real in {2, 3}
        or "sorpresa" in categoria_txt
        or (favorito in SIGNOS and signo_real in SIGNOS and favorito != signo_real)
    )


def contrato_partido_prediccion(prediccion, partido):
    jornada = prediccion.get("jornada")
    temporada = prediccion.get("temporada") or prediccion.get("temporada_base") or TEMPORADA_DEFECTO
    competicion = partido.get("competicion") or prediccion.get("competicion") or COMPETICION_DEFECTO
    probs = normalizar_probabilidades(partido.get("probabilidades") or {})
    signo_predicho = partido.get("signo_final") or partido.get("signo_base") or signo_top(probs)
    signo_real = partido.get("signo_oficial") if partido.get("signo_oficial") in SIGNOS else signo_resultado(partido.get("resultado"))
    ranking_real = ranking_signo(probs, signo_real) if signo_real in SIGNOS else None
    prob_real = probabilidad_signo(probs, signo_real) if signo_real in SIGNOS else None
    signos = signos_pronostico(signo_predicho)
    acierto = signo_real in signos if signo_real in SIGNOS and signos else None
    favorito = partido.get("favorito") or signo_top(probs)
    return {
        "jornada": jornada,
        "temporada": temporada,
        "competicion": competicion,
        "partido_id": partido_id(jornada, partido.get("num"), partido.get("local"), partido.get("visitante"), temporada, competicion),
        "num": partido.get("num"),
        "local": partido.get("local"),
        "visitante": partido.get("visitante"),
        "signo_predicho": signo_predicho,
        "signo_top": signo_top(probs),
        "probabilidades": probs,
        "signo_real": signo_real,
        "probabilidad_signo_real": prob_real,
        "ranking_signo_real": ranking_real,
        "acierto": acierto,
        "error_probabilistico": round(1.0 - (float(prob_real or 0) / 100.0), 6) if prob_real is not None else None,
        "brier_score": brier_score(probs, signo_real),
        "top1_acierto": signo_top(probs) == signo_real if signo_real in SIGNOS else None,
        "top2_acierto": signo_real in signos_top2(probs) if signo_real in SIGNOS else None,
        "tipo_apuesta": partido.get("tipo") or tipo_apuesta(signo_predicho),
        "nivel_confianza": partido.get("nivel_confianza") or nivel_confianza(probs),
        "riesgo": partido.get("incertidumbre"),
        "categoria_sorpresa": partido.get("categoria_sorpresa"),
        "partido_sorpresa": bool_sorpresa(partido.get("categoria_sorpresa"), ranking_real, favorito, signo_real),
        "favorito": favorito,
        "favorito_nombre": partido.get("favorito_nombre"),
        "favorito_acertado": favorito == signo_real if favorito in SIGNOS and signo_real in SIGNOS else None,
        "timestamp_generacion": prediccion.get("generado_en") or partido.get("generado_en"),
    }


def validacion_desde_prediccion(prediccion):
    partidos = sorted(
        [p for p in prediccion.get("partidos", []) if int_o_cero(p.get("num")) <= 14],
        key=lambda p: int_o_cero(p.get("num")),
    )
    signos = [
        str(p.get("signo_final") or p.get("signo_base") or signo_top(p.get("probabilidades") or {})).upper()
        for p in partidos
    ]
    pleno15 = prediccion.get("pleno15") or {}
    pleno_valor = ""
    if isinstance(pleno15, dict):
        pleno_valor = str(pleno15.get("signo_final") or pleno15.get("pronostico") or pleno15.get("resultado") or "").strip()
    else:
        pleno_valor = str(pleno15 or "").strip()
    generado_en = prediccion.get("generado_en") or utcnow_iso()
    return {
        "version": "1.0",
        "jornada": prediccion.get("jornada"),
        "temporada": prediccion.get("temporada") or prediccion.get("temporada_base") or TEMPORADA_DEFECTO,
        "competicion": prediccion.get("competicion") or COMPETICION_DEFECTO,
        "signos": signos[:14],
        "elige8": [int_o_cero(p.get("num")) for p in partidos if p.get("elige8")],
        "pleno15": pleno_valor,
        "fecha": generado_en,
        "validado_en": generado_en,
        "generado_en": generado_en,
        "origen": "prediccion_ia_json",
        "partidos": [contrato_partido_prediccion(prediccion, p) for p in partidos],
    }


def firma_validacion(validacion):
    partidos = []
    for partido in validacion.get("partidos") or []:
        probs = normalizar_probabilidades(partido.get("probabilidades") or {})
        partidos.append({
            "partido_id": partido.get("partido_id"),
            "signo_predicho": partido.get("signo_predicho"),
            "tipo_apuesta": partido.get("tipo_apuesta"),
            "probabilidades": {signo: round(float(probs.get(signo) or 0), 1) for signo in SIGNOS},
        })
    return {
        "jornada": validacion.get("jornada"),
        "signos": validacion.get("signos") or [],
        "elige8": sorted(int_o_cero(x) for x in (validacion.get("elige8") or [])),
        "pleno15": validacion.get("pleno15") or "",
        "partidos": partidos,
    }


def upsert_validacion_generada(prediccion, destino):
    destino = Path(destino)
    nueva = validacion_desde_prediccion(prediccion)
    if len(nueva.get("signos") or []) < 14:
        return False, "prediccion_sin_14_partidos"

    data = cargar_json(destino, {"version": "1.0", "jugadas": []})
    jugadas = data.get("jugadas") or []
    reemplazada = False
    sin_cambios = False
    for idx, jugada in enumerate(jugadas):
        if int_o_cero(jugada.get("jornada")) == int_o_cero(nueva.get("jornada")):
            if firma_validacion(jugada) == firma_validacion(nueva):
                sin_cambios = True
            else:
                jugadas[idx] = nueva
                reemplazada = True
            break
    else:
        jugadas.append(nueva)
        reemplazada = True

    if sin_cambios:
        return False, "sin_cambios"

    data.update({
        "version": "1.0",
        "actualizado_en": utcnow_iso(),
        "descripcion": "Predicciones IA persistidas automaticamente para aprendizaje cuando no hay backend.",
        "jugadas": sorted(jugadas, key=lambda j: int_o_cero(j.get("jornada"))),
    })
    guardar_json(destino, data)
    return reemplazada, "actualizada"


def revisar_partido(jornada, partido_resultado, prediccion_partido, pronostico=None, es_elige8=False, origen=""):
    prediccion_partido = prediccion_partido or {}
    prediccion_meta = {
        "jornada": jornada,
        "temporada": prediccion_partido.get("_temporada") or prediccion_partido.get("temporada") or TEMPORADA_DEFECTO,
        "competicion": prediccion_partido.get("_competicion") or prediccion_partido.get("competicion") or COMPETICION_DEFECTO,
        "generado_en": prediccion_partido.get("_generado_en") or prediccion_partido.get("generado_en"),
    }
    base = dict(prediccion_partido)
    base.setdefault("num", partido_resultado.get("num"))
    base.setdefault("local", partido_resultado.get("local"))
    base.setdefault("visitante", partido_resultado.get("visitante"))
    if pronostico:
        base["signo_final"] = pronostico
        base["tipo"] = tipo_apuesta(pronostico)
    base["resultado"] = partido_resultado.get("resultado")
    base["signo_oficial"] = partido_resultado.get("signo_oficial") or signo_resultado(partido_resultado.get("resultado"))
    revision = contrato_partido_prediccion(prediccion_meta, base)
    revision.update({
        "resultado": partido_resultado.get("resultado"),
        "es_elige8": bool(es_elige8),
        "origen": origen,
    })
    return revision


def porcentaje(aciertos, total):
    return round(float(aciertos or 0) / max(float(total or 0), 1.0) * 100.0, 2)


def resumen_counter(aciertos, totales):
    salida = {}
    for clave in sorted(set(aciertos) | set(totales)):
        total = int(totales.get(clave) or 0)
        ok = int(aciertos.get(clave) or 0)
        salida[clave] = {
            "total": total,
            "aciertos": ok,
            "fallos": max(total - ok, 0),
            "accuracy": porcentaje(ok, total),
        }
    return salida


def metricas_probabilisticas(revisiones):
    evaluadas = [r for r in revisiones if r.get("signo_real") in SIGNOS and r.get("acierto") is not None]
    total = len(evaluadas)
    top1 = sum(1 for r in evaluadas if r.get("top1_acierto"))
    top2 = sum(1 for r in evaluadas if r.get("top2_acierto"))
    por_signo_total = Counter(r.get("signo_real") for r in evaluadas)
    por_signo_ok = Counter(r.get("signo_real") for r in evaluadas if r.get("top1_acierto"))
    por_tipo_total = Counter(r.get("tipo_apuesta") for r in evaluadas)
    por_tipo_ok = Counter(r.get("tipo_apuesta") for r in evaluadas if r.get("acierto"))
    favoritos = [r for r in evaluadas if r.get("favorito") in SIGNOS]
    sorpresas = [r for r in evaluadas if r.get("partido_sorpresa")]
    briers = [float(r["brier_score"]) for r in evaluadas if r.get("brier_score") is not None]
    errores = [float(r["error_probabilistico"]) for r in evaluadas if r.get("error_probabilistico") is not None]

    return {
        "version": "1.0",
        "generado_en": utcnow_iso(),
        "partidos_evaluados": total,
        "probabilidad_media_signo_real": round(
            sum(float(r.get("probabilidad_signo_real") or 0) for r in evaluadas) / max(total, 1),
            4,
        ),
        "error_probabilistico_medio": round(sum(errores) / max(len(errores), 1), 6),
        "brier_score_medio": round(sum(briers) / max(len(briers), 1), 6),
        "accuracy_top1": porcentaje(top1, total),
        "accuracy_top2": porcentaje(top2, total),
        "accuracy_por_signo": resumen_counter(por_signo_ok, por_signo_total),
        "accuracy_por_tipo_apuesta": resumen_counter(por_tipo_ok, por_tipo_total),
        "accuracy_favoritos": {
            "total": len(favoritos),
            "aciertos_top1": sum(1 for r in favoritos if r.get("favorito_acertado")),
            "accuracy": porcentaje(sum(1 for r in favoritos if r.get("favorito_acertado")), len(favoritos)),
        },
        "accuracy_sorpresas": {
            "total": len(sorpresas),
            "aciertos_cobertura": sum(1 for r in sorpresas if r.get("acierto")),
            "accuracy": porcentaje(sum(1 for r in sorpresas if r.get("acierto")), len(sorpresas)),
        },
        "ranking_signo_real": dict(Counter(str(r.get("ranking_signo_real")) for r in evaluadas)),
    }


def nivel_fiabilidad(total, accuracy, tendencia):
    if total < 4:
        return "muestra_baja"
    if accuracy >= 68 and tendencia >= 60:
        return "alta"
    if accuracy >= 52:
        return "media"
    return "baja"


def fiabilidad_equipos(revisiones):
    equipos = defaultdict(lambda: {
        "partidos_evaluados": 0,
        "aciertos": 0,
        "fallos": 0,
        "local_total": 0,
        "local_aciertos": 0,
        "visitante_total": 0,
        "visitante_aciertos": 0,
        "fallos_por_sorpresa": 0,
        "aciertos_como_favorito": 0,
        "fallos_como_favorito": 0,
        "_ultimos": deque(maxlen=10),
    })

    for revision in sorted(revisiones, key=lambda r: (int_o_cero(r.get("jornada")), int_o_cero(r.get("num")))):
        if revision.get("acierto") is None:
            continue
        ok = bool(revision.get("acierto"))
        favorito = revision.get("favorito")
        for condicion, nombre in (("local", revision.get("local")), ("visitante", revision.get("visitante"))):
            if not nombre:
                continue
            stats = equipos[nombre]
            stats["partidos_evaluados"] += 1
            stats["aciertos"] += 1 if ok else 0
            stats["fallos"] += 0 if ok else 1
            stats[f"{condicion}_total"] += 1
            stats[f"{condicion}_aciertos"] += 1 if ok else 0
            if revision.get("partido_sorpresa") and not ok:
                stats["fallos_por_sorpresa"] += 1
            es_favorito = (favorito == "1" and condicion == "local") or (favorito == "2" and condicion == "visitante")
            if es_favorito:
                if ok:
                    stats["aciertos_como_favorito"] += 1
                else:
                    stats["fallos_como_favorito"] += 1
            stats["_ultimos"].append(ok)

    salida = {}
    for equipo, stats in sorted(equipos.items()):
        total = stats["partidos_evaluados"]
        ultimos = list(stats["_ultimos"])
        tendencia = porcentaje(sum(1 for ok in ultimos if ok), len(ultimos))
        accuracy = porcentaje(stats["aciertos"], total)
        salida[equipo] = {
            "partidos_evaluados": total,
            "aciertos": stats["aciertos"],
            "fallos": stats["fallos"],
            "accuracy_global": accuracy,
            "accuracy_como_local": porcentaje(stats["local_aciertos"], stats["local_total"]),
            "accuracy_como_visitante": porcentaje(stats["visitante_aciertos"], stats["visitante_total"]),
            "fallos_por_sorpresa": stats["fallos_por_sorpresa"],
            "aciertos_como_favorito": stats["aciertos_como_favorito"],
            "fallos_como_favorito": stats["fallos_como_favorito"],
            "tendencia_reciente": {
                "partidos": len(ultimos),
                "aciertos": sum(1 for ok in ultimos if ok),
                "accuracy": tendencia,
                "secuencia": ["A" if ok else "F" for ok in ultimos],
            },
            "nivel_fiabilidad_motor": nivel_fiabilidad(total, accuracy, tendencia),
        }
    return {
        "version": "1.0",
        "generado_en": utcnow_iso(),
        "equipos": salida,
    }


def contrato_documentado():
    return {
        "version": "1.0",
        "generado_en": utcnow_iso(),
        "partido_id": "temporada_competicion_jornada_num_local_visitante",
        "entidades": {
            "prediccion": [
                "jornada", "temporada", "competicion", "partido_id", "local", "visitante",
                "signo_predicho", "probabilidades", "tipo_apuesta", "nivel_confianza",
                "riesgo", "categoria_sorpresa", "timestamp_generacion",
            ],
            "resultado_real": ["partido_id", "resultado", "signo_real"],
            "validacion": ["jornada", "signos", "elige8", "pleno15", "origen", "generado_en"],
            "revision": [
                "partido_id", "signo_predicho", "signo_real", "probabilidad_signo_real",
                "ranking_signo_real", "acierto", "error_probabilistico", "brier_score",
            ],
            "aprendizaje": [
                "metricas_probabilisticas", "diario_aprendizaje", "pesos_dinamicos",
                "fiabilidad_equipos",
            ],
        },
    }
