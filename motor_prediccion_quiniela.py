import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from compuerta_jornada import estado_compuerta
from guardar_snapshot_prediccion import crear_snapshot_prediccion
from memoria_autonoma_quiniela import confianza_signos as niveles_confianza_signos

try:
    from modelo_metricas_1x2 import (
        build_prediction_state,
        feature_row_for_match,
        load_trained_model,
        predict_model as predict_modelo_entrenado,
    )
except Exception:
    build_prediction_state = None
    feature_row_for_match = None
    load_trained_model = None
    predict_modelo_entrenado = None


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORIA = DATA / "memoria_ia" / "aprendizaje_global.json"
APRENDIZAJE_PROPIO = DATA / "aprendizaje_ia.json"
PESOS_DINAMICOS = DATA / "memoria_ia" / "pesos_dinamicos.json"
CONTEXTO_EQUIPOS = DATA / "contexto_equipos.json"
CONTEXTO_COMPETITIVO = DATA / "memoria_ia" / "contexto_competitivo.json"
PATRONES_COMPETITIVOS = DATA / "memoria_ia" / "patrones_competitivos.json"
PERFILES_EQUIPOS = DATA / "memoria_ia" / "perfiles_equipos.json"
JORNADAS = DATA / "jornadas"
PREDICCIONES = DATA / "predicciones"
JUGADAS = DATA / "quinielas_jugadas"
MODELO_PREDICTIVO = DATA / "modelo_predictivo"

PRECIO_APUESTA = 1.50
IMPORTE_MINIMO = 1.50
PRECIO_ELIGE8 = 0.50


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def reparar_mojibake(texto):
    texto = str(texto or "")
    try:
        reparado = texto.encode("latin1").decode("utf-8")
        if "�" not in reparado:
            return reparado
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return texto


def normalizar(texto):
    texto = reparar_mojibake(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|sad|club|real|de|del|la|el)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def detectar_jornada_activa():
    jornadas = []
    for path in JORNADAS.glob("jornada_*.json"):
        data = cargar_json(path, {})
        numero = data.get("jornada")
        if not isinstance(numero, int):
            m = re.search(r"(\d+)", path.stem)
            numero = int(m.group(1)) if m else 0
        if numero:
            jornadas.append(numero)
    return max(jornadas) if jornadas else 61


def equipos_memoria(memoria):
    equipos = []
    for liga in ("primera", "segunda"):
        equipos.extend(memoria.get("ligas", {}).get(liga, {}).get("equipos", []))
    return equipos


def puntuacion_nombre_equipo(candidato, objetivo):
    base = normalizar(candidato)
    buscado = normalizar(objetivo)
    if not base or not buscado:
        return 0
    if base == buscado:
        return 1000

    base_tokens = base.split()
    buscado_tokens = buscado.split()
    comunes = [token for token in base_tokens if token in buscado_tokens]
    if not comunes:
        return 0

    ambiguos = {"madrid", "barcelona"}
    if len(comunes) == 1 and comunes[0] in ambiguos and max(len(base_tokens), len(buscado_tokens)) > 1:
        return 0

    cobertura_buscado = len(comunes) / max(len(buscado_tokens), 1)
    cobertura_base = len(comunes) / max(len(base_tokens), 1)
    score = len(comunes) * 30 + cobertura_buscado * 45 + cobertura_base * 35
    if base in buscado or buscado in base:
        score += 20
    score -= abs(len(base_tokens) - len(buscado_tokens)) * 8
    return score


def mejor_coincidencia_equipo(items, nombre, getter):
    mejor = None
    mejor_score = 0
    for item in items or []:
        score = puntuacion_nombre_equipo(getter(item), nombre)
        if score > mejor_score:
            mejor = item
            mejor_score = score
    return mejor if mejor_score >= 55 else None


def buscar_equipo(memoria, nombre):
    return mejor_coincidencia_equipo(
        equipos_memoria(memoria),
        nombre,
        lambda equipo: equipo.get("equipo", ""),
    )


def equipos_contexto(contexto):
    return contexto.get("equipos", {})


def buscar_contexto_equipo(contexto, nombre):
    entradas = [
        {"equipo": equipo, "datos": datos}
        for equipo, datos in equipos_contexto(contexto).items()
    ]
    mejor = mejor_coincidencia_equipo(entradas, nombre, lambda item: item.get("equipo", ""))
    return mejor.get("datos") if mejor else None


def equipos_contexto_competitivo(contexto):
    equipos = []
    for liga in ("primera", "segunda"):
        for equipo in (contexto.get(liga) or {}).get("equipos", []):
            equipos.append({**equipo, "liga": liga})
    return equipos


def buscar_contexto_competitivo(contexto, nombre):
    return mejor_coincidencia_equipo(
        equipos_contexto_competitivo(contexto),
        nombre,
        lambda equipo: equipo.get("equipo", ""),
    )


def valor_motivacion(equipo):
    orden = {"baja": 0, "media": 1, "alta": 2, "maxima": 3}
    if not equipo:
        return 0
    return orden.get(str(equipo.get("motivacion_competitiva", "baja")).lower(), 0)


def objetivo_descenso(equipo):
    if not equipo:
        return False
    for objetivo in equipo.get("objetivos", []):
        texto = f"{objetivo.get('objetivo', '')} {objetivo.get('estado', '')}".lower()
        if "descenso" in texto or "riesgo" in texto:
            return True
    return False


def objetivos_texto(equipo):
    if not equipo:
        return "sin contexto competitivo claro"
    objetivos = []
    for objetivo in equipo.get("objetivos", [])[:3]:
        nombre = str(objetivo.get("objetivo", "")).replace("_", " ")
        estado = str(objetivo.get("estado", "")).replace("_", " ")
        if nombre:
            objetivos.append(f"{nombre} ({estado})")
    return ", ".join(objetivos) if objetivos else "sin objetivo fuerte detectado"


def forma_float(tendencias, clave, divisor):
    try:
        return float(tendencias.get(clave) or 0) / divisor
    except Exception:
        return 0.0


def fuerza(equipo, condicion):
    if not equipo:
        return 0.0
    pj = max(float(equipo.get("pj") or 0), 1.0)
    cond = equipo.get(condicion, {})
    cond_pj = max(float(cond.get("pj") or 0), 1.0)
    tendencias = equipo.get("tendencias", {})
    ppg = float(equipo.get("pts") or 0) / pj
    dg = float(equipo.get("dg") or 0) / pj
    cond_ppg = float(cond.get("pts") or 0) / cond_pj
    forma_5 = forma_float(tendencias, "forma_5_pts", 5.0)
    forma_10 = forma_float(tendencias, "forma_10_pts", 10.0)
    aceleracion = forma_5 - forma_10
    empates = float(tendencias.get("empates_pct") or 0)
    return (
        ppg * 30
        + dg * 12
        + cond_ppg * 20
        + forma_5 * 14
        + forma_10 * 12
        + aceleracion * 6
        + empates * 0.08
    )


def dinamica_texto(equipo):
    if not equipo:
        return ""
    tendencias = equipo.get("tendencias", {})
    forma_5 = float(tendencias.get("forma_5_pts") or 0)
    forma_10 = float(tendencias.get("forma_10_pts") or 0)
    if forma_10 <= 0:
        return "sin dinámica de 10 jornadas suficiente"
    media_5 = forma_5 / 5.0
    media_10 = forma_10 / 10.0
    if media_5 >= media_10 + 0.35:
        etiqueta = "dinámica positiva reciente"
    elif media_5 <= media_10 - 0.35:
        etiqueta = "dinámica negativa reciente"
    else:
        etiqueta = "dinámica estable"
    return f"forma últimos 5/10: {forma_5:.0f}/{forma_10:.0f} puntos, {etiqueta}"


def normalizar_probs(probs):
    probs = {k: max(float(probs.get(k, 1)), 1.0) for k in ("1", "X", "2")}
    total = sum(probs.values()) or 1
    return {k: round(v / total * 100, 1) for k, v in probs.items()}


def preparar_modelo_predictivo_runtime(root=ROOT):
    manifest = cargar_json(Path(root) / "data" / "modelo_predictivo" / "modelo_actual.json", {})
    runtime = {
        "activo": False,
        "manifest": manifest,
        "motivo": "",
        "modelo": None,
        "states": None,
        "priors": None,
    }
    if not all((build_prediction_state, feature_row_for_match, load_trained_model, predict_modelo_entrenado)):
        runtime["motivo"] = "modulo_modelo_metricas_no_disponible"
        return runtime
    try:
        modelo = load_trained_model(root)
    except Exception as exc:
        runtime["motivo"] = f"error_cargando_modelo: {exc}"
        return runtime
    if modelo is None:
        runtime["motivo"] = "artefacto_modelo_no_disponible"
        return runtime
    try:
        states, priors = build_prediction_state(Path(root) / "data" / "jornadas")
    except Exception as exc:
        runtime["motivo"] = f"error_preparando_estado_historico: {exc}"
        return runtime
    runtime.update({"activo": True, "modelo": modelo, "states": states, "priors": priors, "motivo": "ok"})
    return runtime


def ajustar_por_modelo_entrenado(probs, partido, runtime, peso=0.24):
    if not runtime or not runtime.get("activo"):
        return probs, {
            "activo": False,
            "motivo": (runtime or {}).get("motivo", "runtime_no_inicializado"),
            "peso": 0.0,
        }
    try:
        row = feature_row_for_match(partido, runtime["states"], runtime["priors"], JORNADAS)
        pred = predict_modelo_entrenado(runtime["modelo"], row)
        probs_modelo = {signo: round(float(pred.get(signo, 0.0)) * 100.0, 1) for signo in ("1", "X", "2")}
        mezcladas = normalizar_probs({
            signo: float(probs.get(signo, 0.0)) * (1.0 - peso) + probs_modelo[signo] * peso
            for signo in ("1", "X", "2")
        })
        return mezcladas, {
            "activo": True,
            "peso": peso,
            "probabilidades_modelo": probs_modelo,
            "probabilidades_previas": {signo: probs.get(signo) for signo in ("1", "X", "2")},
            "version_id": (runtime.get("manifest") or {}).get("version_id"),
            "estado_modelo": (runtime.get("manifest") or {}).get("estado"),
            "competicion": row.get("competicion"),
            "baseline_modelo": {signo: round(float(row.get("prob_baseline", {}).get(signo, 0.0)) * 100.0, 1) for signo in ("1", "X", "2")},
        }
    except Exception as exc:
        return probs, {"activo": False, "motivo": f"error_inferencia_modelo: {exc}", "peso": 0.0}


PESOS_DINAMICOS_REFERENCIA = {
    "forma_reciente": 0.20,
    "casa_fuera": 0.15,
    "clasificacion": 0.16,
    "goles": 0.12,
    "empate": 0.10,
    "sorpresa": 0.09,
    "motivacion_competitiva": 0.07,
    "necesidad_descenso_ascenso_europa": 0.07,
    "fatiga": 0.02,
    "bajas": 0.02,
}

LIMITES_PESOS_DINAMICOS = {
    "empate": (0.06, 0.18),
    "sorpresa": (0.05, 0.16),
}


def limitar(valor, minimo, maximo):
    return max(min(float(valor), maximo), minimo)


def limites_peso(clave, referencia):
    return LIMITES_PESOS_DINAMICOS.get(clave, (max(referencia * 0.45, 0.01), min(referencia * 1.8, 0.24)))


def normalizar_con_limites(valores):
    actuales = {clave: max(float(valor), 0.0) for clave, valor in valores.items()}
    for _ in range(8):
        total = sum(actuales.values()) or 1.0
        actuales = {clave: valor / total for clave, valor in actuales.items()}
        fijos = {}
        libres = {}
        for clave, valor in actuales.items():
            minimo, maximo = limites_peso(clave, PESOS_DINAMICOS_REFERENCIA[clave])
            if valor < minimo:
                fijos[clave] = minimo
            elif valor > maximo:
                fijos[clave] = maximo
            else:
                libres[clave] = valor
        if not fijos:
            break
        restante = max(1.0 - sum(fijos.values()), 0.0)
        suma_libres = sum(libres.values()) or 1.0
        actuales = {**fijos, **{clave: valor / suma_libres * restante for clave, valor in libres.items()}}
        if all(limites_peso(clave, PESOS_DINAMICOS_REFERENCIA[clave])[0] <= valor <= limites_peso(clave, PESOS_DINAMICOS_REFERENCIA[clave])[1] for clave, valor in actuales.items()):
            break
    total = sum(actuales.values()) or 1.0
    return {clave: round(valor / total, 4) for clave, valor in actuales.items()}


def normalizar_pesos_dinamicos(pesos, decay=0.94):
    data = dict(pesos or {})
    valores = data.get("pesos") or {}
    normalizados = {}
    for clave, referencia in PESOS_DINAMICOS_REFERENCIA.items():
        try:
            valor = float(valores.get(clave, referencia))
        except (TypeError, ValueError):
            valor = referencia
        valor = referencia + (valor - referencia) * decay
        minimo, maximo = limites_peso(clave, referencia)
        normalizados[clave] = limitar(valor, minimo, maximo)

    normalizados = normalizar_con_limites(normalizados)
    data["pesos"] = normalizados
    data["referencia"] = data.get("referencia") or PESOS_DINAMICOS_REFERENCIA
    data["normalizacion_runtime"] = {
        "aplicada": True,
        "decay": decay,
        "limites": LIMITES_PESOS_DINAMICOS,
        "motivo": "Evitar saturacion de pesos dinamicos antes de ajustar probabilidades.",
    }
    return data


def buscar_perfil_autonomo(perfiles, nombre):
    equipos = (perfiles or {}).get("equipos") or {}
    clave = normalizar(nombre)
    if clave in equipos:
        return equipos[clave]
    piezas = set(clave.split())
    mejor = None
    mejor_score = 0
    for key, perfil in equipos.items():
        candidato = set(str(key).split())
        score = len(piezas & candidato)
        if clave and (clave in key or key in clave):
            score += 3
        if score > mejor_score:
            mejor = perfil
            mejor_score = score
    return mejor if mejor_score >= 1 else None


def valor_perfil(perfil, seccion, clave, defecto=0.0):
    try:
        return float(((perfil or {}).get(seccion) or {}).get(clave, defecto) or defecto)
    except (TypeError, ValueError):
        return defecto


def resumen_perfil_autonomo(perfil):
    if not perfil:
        return {}
    resumen = perfil.get("resumen_ponderado") or {}
    forma = perfil.get("forma_reciente") or {}
    return {
        "equipo": perfil.get("equipo"),
        "partidos_total": perfil.get("partidos_total"),
        "puntos_por_partido": resumen.get("puntos_por_partido"),
        "empates_pct": resumen.get("empates_pct"),
        "surprise_score_medio": resumen.get("surprise_score_medio"),
        "forma_5_ppp": forma.get("forma_5_ppp"),
        "forma_10_ppp": forma.get("forma_10_ppp"),
        "racha_actual": forma.get("racha_actual"),
    }


def ajustar_por_perfiles_autonomos(probs, perfiles, local_nombre, visitante_nombre):
    local = buscar_perfil_autonomo(perfiles, local_nombre)
    visitante = buscar_perfil_autonomo(perfiles, visitante_nombre)
    if not local or not visitante:
        return probs, 0.0, [], local, visitante

    p = dict(probs)
    local_ppp = (
        valor_perfil(local, "resumen_ponderado", "puntos_por_partido")
        + valor_perfil(local, "local", "puntos_por_partido")
        + valor_perfil(local, "forma_reciente", "forma_5_ppp")
    ) / 3.0
    visitante_ppp = (
        valor_perfil(visitante, "resumen_ponderado", "puntos_por_partido")
        + valor_perfil(visitante, "visitante", "puntos_por_partido")
        + valor_perfil(visitante, "forma_reciente", "forma_5_ppp")
    ) / 3.0
    diff = local_ppp - visitante_ppp
    ajuste = max(min(diff * 2.4, 4.2), -4.2)
    p["1"] += ajuste
    p["2"] -= ajuste

    empate_medio = (
        valor_perfil(local, "resumen_ponderado", "empates_pct")
        + valor_perfil(visitante, "resumen_ponderado", "empates_pct")
    ) / 2.0
    if empate_medio >= 28:
        p["X"] += min((empate_medio - 28.0) * 0.22, 3.0)
    elif empate_medio <= 17:
        p["X"] -= min((17.0 - empate_medio) * 0.12, 1.2)

    sorpresa_medio = (
        valor_perfil(local, "resumen_ponderado", "surprise_score_medio")
        + valor_perfil(visitante, "resumen_ponderado", "surprise_score_medio")
    ) / 2.0
    riesgo_extra = max(0.0, min((sorpresa_medio - 45.0) * 0.18, 8.0))
    lecturas = [
        "Memoria autonoma: perfiles persistentes ponderados por actualidad ajustan forma y local/visitante.",
        f"Perfil local {local.get('equipo')}: ppp={local_ppp:.2f}; perfil visitante {visitante.get('equipo')}: ppp={visitante_ppp:.2f}.",
    ]
    if empate_medio >= 28:
        lecturas.append(f"Memoria autonoma: tendencia de empate conjunta alta ({empate_medio:.1f}%).")
    if riesgo_extra:
        lecturas.append(f"Memoria autonoma: historial de sorpresa medio elevado ({sorpresa_medio:.1f}).")
    return normalizar_probs(p), round(riesgo_extra, 2), lecturas, local, visitante


def peso_dinamico(pesos, clave):
    try:
        return float((pesos.get("pesos") or {}).get(clave, PESOS_DINAMICOS_REFERENCIA[clave]))
    except (TypeError, ValueError, KeyError):
        return PESOS_DINAMICOS_REFERENCIA.get(clave, 0.0)


def delta_peso(pesos, clave):
    referencia = (pesos.get("referencia") or PESOS_DINAMICOS_REFERENCIA).get(clave, PESOS_DINAMICOS_REFERENCIA.get(clave, 0.0))
    return peso_dinamico(pesos, clave) - float(referencia or 0.0)


def alertas_contexto(datos):
    return {str(alerta).lower() for alerta in (datos or {}).get("alertas", [])}


def ajustar_por_pesos_dinamicos(probs, pesos, local_comp, visitante_comp, contexto_local, contexto_visitante):
    if not pesos or not isinstance(pesos.get("pesos"), dict):
        return probs, 0.0, []

    p = dict(probs)
    riesgo_extra = 0.0
    lecturas = []
    top = signo_top(p)

    d_empate = delta_peso(pesos, "empate")
    if d_empate > 0:
        ajuste = min(d_empate * 38, 1.8)
        p["X"] += ajuste
        riesgo_extra += ajuste * 1.4
        lecturas.append("Pesos dinamicos: se refuerza ligeramente la X por fallos historicos de empate.")

    d_sorpresa = delta_peso(pesos, "sorpresa")
    if d_sorpresa > 0:
        ajuste_top = min(d_sorpresa * 42, 2.0)
        p[top] -= ajuste_top
        for signo in ("1", "X", "2"):
            if signo != top:
                p[signo] += ajuste_top / 2
        riesgo_extra += d_sorpresa * 120
        lecturas.append("Pesos dinamicos: se suaviza el favorito por memoria de sorpresas no cubiertas.")

    d_clasificacion = delta_peso(pesos, "clasificacion")
    if d_clasificacion < 0 and top in {"1", "2"}:
        ajuste = min(abs(d_clasificacion) * 30, 1.2)
        p[top] -= ajuste
        p["X"] += ajuste * 0.55
        riesgo_extra += ajuste
        lecturas.append("Pesos dinamicos: la clasificacion pura pesa algo menos antes de dejar fijo.")

    d_motivacion = max(delta_peso(pesos, "motivacion_competitiva"), 0.0)
    d_necesidad = max(delta_peso(pesos, "necesidad_descenso_ascenso_europa"), 0.0)
    if (d_motivacion or d_necesidad) and (necesidad_viva_motor(local_comp) or necesidad_viva_motor(visitante_comp)):
        ajuste = min((d_motivacion + d_necesidad) * 22, 1.6)
        if necesidad_viva_motor(local_comp):
            p["1"] += ajuste
        if necesidad_viva_motor(visitante_comp):
            p["2"] += ajuste
        p["X"] += ajuste * 0.5
        riesgo_extra += ajuste * 2.0
        lecturas.append("Pesos dinamicos: la necesidad competitiva viva tiene mas peso acumulado.")

    d_bajas = max(delta_peso(pesos, "bajas"), 0.0)
    if d_bajas:
        alertas_local = alertas_contexto(contexto_local)
        alertas_visitante = alertas_contexto(contexto_visitante)
        alertas_riesgo = {"lesiones", "sanciones", "dudas"}
        ajuste = min(d_bajas * 22, 0.8)
        if alertas_local & alertas_riesgo:
            p["1"] -= ajuste
            p["X"] += ajuste * 0.5
            riesgo_extra += ajuste
        if alertas_visitante & alertas_riesgo:
            p["2"] -= ajuste
            p["X"] += ajuste * 0.5
            riesgo_extra += ajuste

    return normalizar_probs(p), round(riesgo_extra, 2), lecturas


def aplicar_patron_posicion(probs, memoria, posicion):
    perfil = memoria.get("quiniela", {}).get("historico_csv", {}).get("perfil_por_posicion", {}).get(str(posicion), {})
    if not perfil:
        return probs
    return normalizar_probs({
        "1": probs["1"] * 0.88 + float(perfil.get("1", 33.3)) * 0.12,
        "X": probs["X"] * 0.88 + float(perfil.get("X", 33.3)) * 0.12,
        "2": probs["2"] * 0.88 + float(perfil.get("2", 33.3)) * 0.12,
    })


def calcular_probabilidades(memoria, partido):
    local = buscar_equipo(memoria, partido.get("local", ""))
    visitante = buscar_equipo(memoria, partido.get("visitante", ""))
    fl = fuerza(local, "local")
    fv = fuerza(visitante, "visitante")
    diff = fl - fv

    probs = {
        "1": 37 + max(min(diff * 0.52, 24), -20),
        "X": 29 + max(0, 10 - abs(diff) * 0.20),
        "2": 34 + max(min(-diff * 0.52, 24), -20),
    }

    if local and visitante:
        emp_l = float(local.get("tendencias", {}).get("empates_pct") or 0)
        emp_v = float(visitante.get("tendencias", {}).get("empates_pct") or 0)
        if (emp_l + emp_v) / 2 >= 28:
            probs["X"] += 5
        if float(local.get("gc") or 0) / max(float(local.get("pj") or 1), 1) > 1.35:
            probs["2"] += 3
        if float(visitante.get("gc") or 0) / max(float(visitante.get("pj") or 1), 1) > 1.35:
            probs["1"] += 3

    probs = normalizar_probs(probs)
    probs = aplicar_patron_posicion(probs, memoria, partido.get("num"))
    return probs, local, visitante, round(diff, 2)


def ajustar_por_contexto(probs, contexto_local, contexto_visitante):
    probs = dict(probs)
    riesgo_extra = 0
    lecturas = []

    def penalizar(datos, lado):
        nonlocal riesgo_extra
        if not datos:
            return
        alertas = set(datos.get("alertas", []))
        nombre_lado = "local" if lado == "1" else "visitante"
        contrario = "2" if lado == "1" else "1"
        if "lesiones" in alertas or "sanciones" in alertas:
            probs[lado] -= 3
            probs[contrario] += 2
            probs["X"] += 1
            riesgo_extra += 5
            lecturas.append(f"Contexto {nombre_lado}: posibles bajas/sanciones detectadas.")
        if "dudas" in alertas:
            probs[lado] -= 1.5
            probs["X"] += 1.5
            riesgo_extra += 3
            lecturas.append(f"Contexto {nombre_lado}: dudas de disponibilidad o entrenamiento.")
        if "altas" in alertas:
            probs[lado] += 1.5
            riesgo_extra = max(riesgo_extra - 1, 0)
            lecturas.append(f"Contexto {nombre_lado}: posibles altas o regresos.")

    penalizar(contexto_local, "1")
    penalizar(contexto_visitante, "2")
    return normalizar_probs(probs), riesgo_extra, lecturas


def ajustar_por_motivacion(probs, local_comp, visitante_comp):
    probs = dict(probs)
    riesgo_extra = 0
    lecturas = []
    motivacion_local = valor_motivacion(local_comp)
    motivacion_visitante = valor_motivacion(visitante_comp)
    diferencia = motivacion_local - motivacion_visitante

    if diferencia:
        ajuste = max(min(diferencia * 2.2, 6), -6)
        probs["1"] += ajuste
        probs["2"] -= ajuste
        riesgo_extra += min(abs(diferencia) * 3, 8)
        if diferencia > 0:
            lecturas.append(
                f"Motivacion: el local compite con mas urgencia ({objetivos_texto(local_comp)})."
            )
        else:
            lecturas.append(
                f"Motivacion: el visitante compite con mas urgencia ({objetivos_texto(visitante_comp)})."
            )

    if motivacion_local >= 2 and motivacion_visitante >= 2:
        probs["X"] += 2
        riesgo_extra += 3
        lecturas.append("Motivacion: choque de alta presion para ambos; sube el riesgo de empate o resultado cerrado.")

    if objetivo_descenso(local_comp):
        probs["1"] += 1.5
        riesgo_extra += 2
        lecturas.append("Contexto competitivo local: partido condicionado por permanencia/descenso.")
    if objetivo_descenso(visitante_comp):
        probs["2"] += 1.5
        riesgo_extra += 2
        lecturas.append("Contexto competitivo visitante: partido condicionado por permanencia/descenso.")

    return normalizar_probs(probs), riesgo_extra, lecturas



def texto_competitivo_motor(equipo):
    objetivos = " ".join(
        f"{o.get('objetivo', '')} {o.get('estado', '')} {o.get('lectura', '')}"
        for o in (equipo or {}).get("objetivos", [])
    )
    return f"{objetivos} {(equipo or {}).get('situacion_competitiva', '')} {(equipo or {}).get('motivacion_competitiva', '')}".lower()


def objetivo_cerrado_motor(equipo):
    if not equipo:
        return False
    if equipo.get("objetivos_vivos"):
        return False
    texto = texto_competitivo_motor(equipo)
    return any(
        clave in texto
        for clave in (
            "asegurado_matematicamente",
            "campeon_matematico",
            "salvado_matematicamente",
            "descendido_matematicamente",
            "sin_opciones_matematicas",
            "no se juega nada",
        )
    )


def necesidad_viva_motor(equipo):
    if not equipo or objetivo_cerrado_motor(equipo):
        return False
    texto = texto_competitivo_motor(equipo)
    motivacion = str(equipo.get("motivacion_competitiva") or equipo.get("motivacion") or "").lower()
    return bool(equipo.get("objetivos_vivos")) or motivacion in {"alta", "maxima", "máxima"} or any(
        clave in texto
        for clave in (
            "riesgo_descenso",
            "en_descenso_con_opciones",
            "permanencia_por_cerrar",
            "defiende_plaza",
            "aspira_matematicamente",
            "aspira_por_desempate",
            "descenso",
            "permanencia",
            "playoff",
            "ascenso",
            "conference",
            "europa",
            "champions",
        )
    )


def descenso_vivo_motor(equipo):
    return necesidad_viva_motor(equipo) and any(c in texto_competitivo_motor(equipo) for c in ("descenso", "permanencia", "salvarse"))


def tasa_patron(patrones, clave):
    try:
        return float((patrones.get("patrones") or {}).get(clave, {}).get("tasa_sorpresa") or 0)
    except Exception:
        return 0.0


def ajustar_por_patrones_aprendidos(probs, patrones, local_comp, visitante_comp):
    probs = dict(probs)
    riesgo_extra = 0.0
    lecturas = []
    local_cerrado = objetivo_cerrado_motor(local_comp)
    visitante_cerrado = objetivo_cerrado_motor(visitante_comp)
    local_necesita = necesidad_viva_motor(local_comp)
    visitante_necesita = necesidad_viva_motor(visitante_comp)
    local_descenso = descenso_vivo_motor(local_comp)
    visitante_descenso = descenso_vivo_motor(visitante_comp)
    top = signo_top(probs)

    if visitante_cerrado and local_necesita:
        tasa = tasa_patron(patrones, "necesitado_local_vs_visitante_objetivo_cerrado")
        probs["1"] += 16 + tasa * 0.16
        probs["X"] += 11 + tasa * 0.09
        probs["2"] -= 12
        riesgo_extra += 24 + tasa * 0.38
        lecturas.append(f"Aprendizaje competitivo: cuando el local necesita y el visitante tiene objetivo cerrado, el fijo visitante se rompe con frecuencia ({tasa:.1f}% en la memoria).")

    if local_cerrado and visitante_necesita:
        tasa = tasa_patron(patrones, "visitante_necesitado_vs_local_objetivo_cerrado")
        probs["2"] += 16 + tasa * 0.16
        probs["X"] += 11 + tasa * 0.09
        probs["1"] -= 12
        riesgo_extra += 24 + tasa * 0.38
        lecturas.append(f"Aprendizaje competitivo: cuando el visitante necesita y el local tiene objetivo cerrado, el 1 fijo no debe ser tranquilo ({tasa:.1f}% de rupturas en memoria).")

    if visitante_descenso and top == "1":
        tasa = tasa_patron(patrones, "visitante_descenso_vs_local_favorito")
        probs["X"] += 16 + tasa * 0.12
        probs["2"] += 18 + tasa * 0.16
        probs["1"] -= 20
        riesgo_extra += 75 + tasa * 0.40
        lecturas.append(f"Aprendizaje de descenso: un visitante que se juega permanencia contra favorito local debe subir a zona prioritaria de cobertura; patron historico {tasa:.1f}%.")

    if local_descenso and top == "2":
        tasa = tasa_patron(patrones, "local_descenso_vs_visitante_favorito")
        probs["X"] += 16 + tasa * 0.12
        probs["1"] += 18 + tasa * 0.16
        probs["2"] -= 20
        riesgo_extra += 75 + tasa * 0.40
        lecturas.append(f"Aprendizaje de descenso: un local que se juega permanencia contra favorito visitante debe subir a zona prioritaria de cobertura; patron historico {tasa:.1f}%.")

    if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
        tasa = tasa_patron(patrones, "equipo_necesitado_vs_equipo_sin_objetivo")
        riesgo_extra += 22 + tasa * 0.34
        lecturas.append(f"Patron general aprendido: necesidad contra objetivo cerrado aumenta sorpresa y exige desconfiar del fijo limpio ({tasa:.1f}%).")

    if local_necesita and visitante_necesita:
        probs["X"] += 7
        riesgo_extra += 20
        lecturas.append("Choque de necesidades vivas: el empate y la cobertura amplia ganan valor frente al fijo limpio.")

    return normalizar_probs(probs), round(riesgo_extra, 2), lecturas

def signo_top(probs):
    return sorted(probs.items(), key=lambda x: x[1], reverse=True)[0][0]


def ajuste_motor_aprendizaje(aprendizaje):
    ajuste = aprendizaje.get("ajuste_motor") if isinstance(aprendizaje, dict) else {}
    return ajuste if isinstance(ajuste, dict) else {}


def aprendizaje_propio_activo(aprendizaje):
    ajuste = ajuste_motor_aprendizaje(aprendizaje)
    try:
        partidos_base = int(ajuste.get("partidos_base") or aprendizaje.get("partidos_revisados") or 0)
    except Exception:
        partidos_base = 0
    return partidos_base >= 28 and str(ajuste.get("muestra") or "").lower() != "baja"


def valor_ajuste(ajuste, clave, defecto=0.0):
    try:
        return float(ajuste.get(clave, defecto) or defecto)
    except (TypeError, ValueError):
        return defecto


def tendencia_empate_media(local, visitante):
    valores = []
    for equipo in (local, visitante):
        try:
            valores.append(float((equipo or {}).get("tendencias", {}).get("empates_pct") or 0))
        except (TypeError, ValueError):
            continue
    return sum(valores) / len(valores) if valores else 0.0


def ajustar_por_aprendizaje_propio(probs, local, visitante, aprendizaje):
    if not aprendizaje_propio_activo(aprendizaje):
        return probs, 0.0, []

    ajuste = ajuste_motor_aprendizaje(aprendizaje)
    probs = dict(probs)
    orden = sorted(probs.values(), reverse=True)
    margen = orden[0] - orden[1] if len(orden) > 1 else 0.0
    top_prob = orden[0] if orden else 0.0
    tercera = orden[2] if len(orden) > 2 else 0.0
    empate_medio = tendencia_empate_media(local, visitante)
    hay_memoria_estadistica = bool(local or visitante)
    riesgo_extra = 0.0
    lecturas = []

    boost_empate = valor_ajuste(ajuste, "boost_empate_zona_riesgo")
    if boost_empate and hay_memoria_estadistica and (probs.get("X", 0) >= 24 or margen <= 14 or empate_medio >= 26):
        incremento = min(boost_empate, 6.0)
        probs["X"] = probs.get("X", 0) + incremento
        riesgo_extra += incremento * 1.2
        lecturas.append(
            "Aprendizaje propio: el historial dejo empates sin cubrir; se refuerza la X en zona de riesgo."
        )
    elif boost_empate and not hay_memoria_estadistica:
        riesgo_extra += min(boost_empate, 6.0)
        lecturas.append(
            "Aprendizaje propio: hay sesgo de empates no cubiertos, pero sin memoria de equipos no se altera el porcentaje; solo sube el riesgo."
        )

    umbral_fijo = valor_ajuste(ajuste, "umbral_fijo_seguro", 54.0)
    riesgo_fijo = valor_ajuste(ajuste, "riesgo_extra_fijo_fragil")
    if riesgo_fijo and (top_prob < umbral_fijo or margen < 14):
        riesgo_extra += riesgo_fijo
        lecturas.append(
            f"Aprendizaje propio: los fijos fallados obligan a desconfiar de favoritos por debajo de {umbral_fijo:.0f}%."
        )

    riesgo_triple = valor_ajuste(ajuste, "riesgo_extra_triple_insuficiente")
    if riesgo_triple and tercera >= 17:
        riesgo_extra += riesgo_triple
        lecturas.append(
            "Aprendizaje propio: hubo dobles insuficientes; el tercer signo vivo sube prioridad de triple."
        )

    return normalizar_probs(probs), round(riesgo_extra, 2), lecturas


def doble_top(probs):
    top2 = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:2]
    signos = {s for s, _ in top2}
    return "".join(s for s in ("1", "X", "2") if s in signos)


def signos_jugados(partido):
    texto = str(partido.get("signo_final") or partido.get("signo_base") or "")
    signos = "".join(s for s in ("1", "X", "2") if s in texto)
    if signos:
        return signos
    probs = partido.get("probabilidades") or {}
    return signo_top(probs) if probs else "1"


def probabilidad_signo(partido, signo):
    try:
        return float((partido.get("probabilidades") or {}).get(signo) or 0)
    except (TypeError, ValueError):
        return 0.0


def probabilidad_cubierta(partido):
    signos = signos_jugados(partido)
    return min(100.0, sum(probabilidad_signo(partido, signo) for signo in signos))


def prioridad_elige8(partido):
    signos = signos_jugados(partido)
    prioridad_cobertura = 30000 if len(signos) == 3 else 20000 if len(signos) == 2 else 10000
    incertidumbre_partido = float(partido.get("incertidumbre") or 0)
    sorpresa = float(partido.get("probabilidad_sorpresa") or 0)
    riesgo_necesidad = 1 if partido.get("riesgo_necesidad_real") or partido.get("riesgo_necesidad") else 0
    penalizacion = min(25, incertidumbre_partido * 0.05) + min(15, sorpresa * 0.05) + riesgo_necesidad
    return (
        prioridad_cobertura
        + probabilidad_cubierta(partido) * 3
        + probabilidad_signo(partido, partido.get("signo_base") or signos[0]) * 0.2
        - penalizacion
    )


def incertidumbre(probs, local, visitante, diff, riesgo_contexto=0):
    orden = sorted(probs.values(), reverse=True)
    margen = orden[0] - orden[1]
    puntos = 100 - margen + probs["X"] * 0.35
    if abs(diff) < 8:
        puntos += 8
    if local and local.get("racha_actual", {}).get("sin_ganar", 0) >= 3:
        puntos += 4
    if visitante and visitante.get("racha_actual", {}).get("sin_perder", 0) >= 3:
        puntos += 4
    puntos += riesgo_contexto
    return round(puntos, 2)


def explicar(
    partido,
    probs,
    signo,
    local,
    visitante,
    diff,
    tipo,
    contexto_local=None,
    contexto_visitante=None,
    lecturas_contexto=None,
    local_comp=None,
    visitante_comp=None,
    lecturas_motivacion=None,
    prob_sorpresa=None,
    indice_sorpresa=None,
):
    razones = []
    razones.append(f"Probabilidades IA: 1={probs['1']}%, X={probs['X']}%, 2={probs['2']}%.")
    if local:
        t = local.get("tendencias", {})
        razones.append(
            f"{partido.get('local')} llega con {local.get('pts', 0)} puntos, "
            f"{dinamica_texto(local)} y "
            f"{t.get('goles_favor_por_partido', 0)} goles a favor por partido."
        )
    if visitante:
        t = visitante.get("tendencias", {})
        razones.append(
            f"{partido.get('visitante')} llega con {visitante.get('pts', 0)} puntos, "
            f"{dinamica_texto(visitante)} y "
            f"{t.get('goles_contra_por_partido', 0)} goles encajados por partido."
        )
    if not local or not visitante:
        faltan = []
        if not local:
            faltan.append(partido.get("local"))
        if not visitante:
            faltan.append(partido.get("visitante"))
        razones.append(
            "Aviso de datos: no hay estadistica historica completa para "
            f"{', '.join(str(x) for x in faltan if x)}; los porcentajes se apoyan en "
            "patron general del boleto, posicion quinielistica y contexto/noticias disponibles."
        )
    if abs(diff) < 8:
        if local and visitante:
            razones.append("El partido queda equilibrado por fuerza reciente, asi que sube el riesgo de empate o sorpresa.")
        else:
            razones.append(
                "Al no existir diferencial estadistico fiable entre ambos equipos, el partido se trata como abierto "
                "y sube el peso de empate o sorpresa."
            )
    if tipo == "TRIPLE":
        razones.append("Se protege con triple porque es de los partidos con mas incertidumbre del boleto.")
    elif tipo == "DOBLE":
        razones.append("Se protege con doble porque el segundo signo tiene peso suficiente para cubrir una desviacion razonable.")
    else:
        razones.append("Se deja como fijo porque el signo principal tiene mejor relacion entre probabilidad y riesgo.")
    lecturas_contexto = lecturas_contexto or []
    if contexto_local:
        razones.append(contexto_local.get("resumen", ""))
    if contexto_visitante:
        razones.append(contexto_visitante.get("resumen", ""))
    razones.extend(lecturas_contexto)
    lecturas_motivacion = lecturas_motivacion or []
    razones.extend(lecturas_motivacion)
    if local_comp or visitante_comp:
        razones.append(
            f"Objetivos: {partido.get('local')} ({objetivos_texto(local_comp)}) frente a "
            f"{partido.get('visitante')} ({objetivos_texto(visitante_comp)})."
        )
    if prob_sorpresa is not None:
        razones.append(f"Riesgo de azar/sorpresa estimado: {prob_sorpresa}%.")
    if indice_sorpresa:
        cobertura = indice_sorpresa.get("cobertura_sugerida", "FIJO")
        motivos = ", ".join(indice_sorpresa.get("motivos", [])[:3])
        favorito = indice_sorpresa.get("favorito_nombre") or "sin favorito claro"
        razones.append(
            f"Indice de sorpresa quinielistica: {indice_sorpresa.get('indice', 0)}/100; "
            f"favorito a vigilar: {favorito}; cobertura sugerida por sorpresa: {cobertura}. {motivos}."
        )
    razones.append(f"Decision final: {signo}.")
    return " ".join(razones)


def probabilidad_sorpresa(probs, incertidumbre_puntos):
    top = max(float(v) for v in probs.values())
    base = 100 - top
    extra = max(min((float(incertidumbre_puntos) - 90) * 0.25, 12), 0)
    return round(max(min(base + extra, 70), 18), 1)


def riesgo_necesidad_real(local_comp, visitante_comp):
    return (
        necesidad_viva_motor(local_comp)
        or necesidad_viva_motor(visitante_comp)
        or descenso_vivo_motor(local_comp)
        or descenso_vivo_motor(visitante_comp)
    )


def trazabilidad_datos_partido(local, visitante, contexto_local, contexto_visitante, local_comp, visitante_comp):
    memoria_local = bool(local)
    memoria_visitante = bool(visitante)
    noticias_local = bool((contexto_local or {}).get("noticias"))
    noticias_visitante = bool((contexto_visitante or {}).get("noticias"))
    competitivo_local = bool(local_comp)
    competitivo_visitante = bool(visitante_comp)

    if memoria_local and memoria_visitante:
        origen = "estadistica_equipos"
        calidad = "alta"
    elif noticias_local or noticias_visitante or competitivo_local or competitivo_visitante:
        origen = "fallback_posicion_con_contexto"
        calidad = "media_baja"
    else:
        origen = "fallback_posicion"
        calidad = "baja"

    return {
        "origen_probabilidades": origen,
        "calidad_datos": calidad,
        "memoria_estadistica": {
            "local": memoria_local,
            "visitante": memoria_visitante,
        },
        "noticias_recientes": {
            "local": noticias_local,
            "visitante": noticias_visitante,
        },
        "contexto_competitivo": {
            "local": competitivo_local,
            "visitante": competitivo_visitante,
        },
    }


def racha_valor(equipo, clave):
    try:
        return float((equipo or {}).get("racha_actual", {}).get(clave) or 0)
    except Exception:
        return 0.0


def tendencia_valor(equipo, clave):
    try:
        return float((equipo or {}).get("tendencias", {}).get(clave) or 0)
    except Exception:
        return 0.0


def goles_por_partido(equipo, clave):
    try:
        tendencias = (equipo or {}).get("tendencias", {})
        if clave in tendencias:
            return float(tendencias.get(clave) or 0)
        pj = max(float((equipo or {}).get("pj") or 1), 1.0)
        campo = "gf" if "favor" in clave else "gc"
        return float((equipo or {}).get(campo) or 0) / pj
    except Exception:
        return 0.0


def signos_ordenados(probs):
    return sorted(
        ((signo, float((probs or {}).get(signo) or 0)) for signo in ("1", "X", "2")),
        key=lambda item: item[1],
        reverse=True,
    )


def equipo_memoria_por_signo(partido, signo):
    if signo == "1":
        return partido.get("_local")
    if signo == "2":
        return partido.get("_visitante")
    return None


def contexto_competitivo_por_signo(partido, signo):
    if signo == "1":
        return partido.get("contexto_competitivo_local")
    if signo == "2":
        return partido.get("contexto_competitivo_visitante")
    return None


def nombre_por_signo(partido, signo):
    if signo == "1":
        return partido.get("local", "")
    if signo == "2":
        return partido.get("visitante", "")
    return "Empate"


def clamp(valor, minimo=0.0, maximo=100.0):
    return max(min(float(valor), maximo), minimo)


def indice_sorpresa_quinielistica(partido, patrones=None):
    probs = partido.get("probabilidades", {})
    orden = signos_ordenados(probs)
    if not orden:
        return {
            "indice": 0.0,
            "categoria": "sin_datos",
            "favorito": None,
            "favorito_nombre": "",
            "favorito_atacable": False,
            "signo_sorpresa_principal": "",
            "signos_contra_favorito": [],
            "cobertura_sugerida": "FIJO",
            "motivos": ["Sin probabilidades suficientes para medir sorpresa."],
        }

    top, top_prob = orden[0]
    segundo, segundo_prob = orden[1] if len(orden) > 1 else ("", 0.0)
    tercero, tercera_prob = orden[2] if len(orden) > 2 else ("", 0.0)
    margen = top_prob - segundo_prob
    inc = float(partido.get("incertidumbre") or 0)
    sorpresa = float(partido.get("probabilidad_sorpresa") or 0)
    x_prob = float(probs.get("X") or 0)
    patrones = patrones or {}

    local_comp = partido.get("contexto_competitivo_local")
    visitante_comp = partido.get("contexto_competitivo_visitante")
    local_necesita = necesidad_viva_motor(local_comp)
    visitante_necesita = necesidad_viva_motor(visitante_comp)
    local_cerrado = objetivo_cerrado_motor(local_comp)
    visitante_cerrado = objetivo_cerrado_motor(visitante_comp)
    local_descenso = descenso_vivo_motor(local_comp)
    visitante_descenso = descenso_vivo_motor(visitante_comp)

    favorito_signo = top if top in {"1", "2"} else None
    favorito_comp = contexto_competitivo_por_signo(partido, favorito_signo)
    rival_signo = "2" if favorito_signo == "1" else "1" if favorito_signo == "2" else None
    rival_comp = contexto_competitivo_por_signo(partido, rival_signo)
    favorito_memoria = equipo_memoria_por_signo(partido, favorito_signo)
    rival_memoria = equipo_memoria_por_signo(partido, rival_signo)

    favorito_necesita = necesidad_viva_motor(favorito_comp)
    rival_necesita = necesidad_viva_motor(rival_comp)
    favorito_cerrado = objetivo_cerrado_motor(favorito_comp)
    rival_descenso = descenso_vivo_motor(rival_comp)

    score = 0.0
    motivos = []

    score += clamp((inc - 85) * 0.45, 0, 42)
    score += clamp((sorpresa - 35) * 0.55, 0, 24)

    if margen <= 4:
        score += 20
        motivos.append("margen minimo entre primer y segundo signo")
    elif margen <= 8:
        score += 16
        motivos.append("margen corto entre favorito y alternativa")
    elif margen <= 12:
        score += 11
        motivos.append("favorito con ventaja moderada, no dominante")
    elif margen <= 18:
        score += 6

    if top_prob < 45:
        score += 16
        motivos.append("ningun signo supera claramente el 45%")
    elif top_prob < 50:
        score += 10
        motivos.append("favorito por debajo del 50%")
    elif top_prob < 55:
        score += 5

    if x_prob >= 33:
        score += 10
        motivos.append("empate con peso alto")
    elif x_prob >= 29:
        score += 5

    if tercera_prob >= 23:
        score += 14
        motivos.append("tercer signo vivo: partido candidato a triple")
    elif tercera_prob >= 18:
        score += 8

    if favorito_signo is None:
        score += 10
        motivos.append("el signo base es X: no hay favorito limpio")

    if favorito_cerrado and rival_necesita:
        score += 30
        motivos.append("favorito con objetivo cerrado ante rival que necesita puntuar")
    if rival_descenso:
        score += 26
        motivos.append("rival del favorito con urgencia de descenso/permanencia")
    if rival_necesita and not favorito_necesita:
        score += 12
        motivos.append("la necesidad competitiva esta mas del lado del no favorito")
    if favorito_necesita and rival_necesita and margen <= 12:
        score += 10
        motivos.append("ambos tienen necesidad viva y el margen es estrecho")

    if favorito_signo == "1":
        if visitante_descenso:
            tasa = tasa_patron(patrones, "visitante_descenso_vs_local_favorito")
            score += tasa * 0.28
        if visitante_necesita and local_cerrado:
            tasa = tasa_patron(patrones, "visitante_necesitado_vs_local_objetivo_cerrado")
            score += tasa * 0.22
            score += tasa_patron(patrones, "equipo_necesitado_vs_equipo_sin_objetivo") * 0.14
    elif favorito_signo == "2":
        if local_descenso:
            tasa = tasa_patron(patrones, "local_descenso_vs_visitante_favorito")
            score += tasa * 0.28
        if local_necesita and visitante_cerrado:
            tasa = tasa_patron(patrones, "necesitado_local_vs_visitante_objetivo_cerrado")
            score += tasa * 0.22
            score += tasa_patron(patrones, "equipo_necesitado_vs_equipo_sin_objetivo") * 0.14

    if racha_valor(favorito_memoria, "sin_ganar") >= 3:
        score += 10
        motivos.append("favorito con racha reciente sin ganar")
    if racha_valor(rival_memoria, "sin_perder") >= 3:
        score += 8
        motivos.append("rival del favorito llega sin perder")
    if goles_por_partido(favorito_memoria, "goles_contra_por_partido") >= 1.35:
        score += 6
        motivos.append("favorito encaja demasiado para ser fijo limpio")
    if goles_por_partido(rival_memoria, "goles_favor_por_partido") >= 1.30:
        score += 5
    if tendencia_valor(rival_memoria, "forma_5_pts") - tendencia_valor(favorito_memoria, "forma_5_pts") >= 3:
        score += 9
        motivos.append("el no favorito llega con mejor forma reciente")

    indice = round(clamp(score), 1)
    if indice >= 75:
        categoria = "favorito_muy_atacable" if favorito_signo else "partido_muy_abierto"
    elif indice >= 60:
        categoria = "favorito_atacable" if favorito_signo else "partido_abierto"
    elif indice >= 45:
        categoria = "sorpresa_vigilada"
    else:
        categoria = "riesgo_controlado"

    cobertura = "FIJO"
    if indice >= 76 and tercera_prob >= 18 and (margen <= 10 or x_prob >= 30 or favorito_signo is None):
        cobertura = "TRIPLE"
    elif indice >= 55 or margen <= 8 or sorpresa >= 60:
        cobertura = "DOBLE"

    signos_contra = [signo for signo, _ in orden if signo != top]
    if tercero and tercero not in signos_contra:
        signos_contra.append(tercero)

    if not motivos:
        motivos.append("sin senales fuertes de ruptura del favorito")

    return {
        "indice": indice,
        "categoria": categoria,
        "favorito": favorito_signo,
        "favorito_nombre": nombre_por_signo(partido, favorito_signo),
        "favorito_atacable": bool(favorito_signo and indice >= 60),
        "signo_sorpresa_principal": segundo,
        "signos_contra_favorito": signos_contra[:2],
        "cobertura_sugerida": cobertura,
        "motivos": motivos[:6],
    }


def indice_sorpresa_partido(partido):
    datos = partido.get("_indice_sorpresa_quinielistica") or partido.get("indice_sorpresa_detalle")
    if isinstance(datos, dict):
        return float(datos.get("indice") or 0)
    return float(partido.get("indice_sorpresa_quinielistica") or 0)


def prioridad_cobertura(partido):
    probs = partido.get("probabilidades", {})
    valores = sorted(probs.values(), reverse=True)
    margen = valores[0] - valores[1] if len(valores) > 1 else 0
    local_comp = partido.get("contexto_competitivo_local")
    visitante_comp = partido.get("contexto_competitivo_visitante")
    local_necesita = necesidad_viva_motor(local_comp)
    visitante_necesita = necesidad_viva_motor(visitante_comp)
    local_cerrado = objetivo_cerrado_motor(local_comp)
    visitante_cerrado = objetivo_cerrado_motor(visitante_comp)
    local_descenso = descenso_vivo_motor(local_comp)
    visitante_descenso = descenso_vivo_motor(visitante_comp)
    top = signo_top(probs)
    score = float(partido.get("incertidumbre", 0))
    indice = indice_sorpresa_partido(partido)
    score += indice * 1.25
    detalle_indice = partido.get("_indice_sorpresa_quinielistica") or {}
    if detalle_indice.get("favorito_atacable"):
        score += 35

    if partido.get("riesgo_necesidad_real"):
        score += 25
    if local_descenso or visitante_descenso:
        score += 70
    if local_descenso and visitante_descenso:
        score += 40
    if (visitante_descenso and top == "1") or (local_descenso and top == "2"):
        score += 85
    if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
        score += 75
    if local_necesita and visitante_necesita:
        score += 45
    if margen < 8:
        score += 28
    elif margen < 16:
        score += 18
    return score


def tercera_probabilidad(partido):
    valores = sorted((partido.get("probabilidades") or {}).values(), reverse=True)
    return valores[2] if len(valores) > 2 else 0


def prioridad_triple(partido):
    probs = partido.get("probabilidades", {})
    valores = sorted(probs.values(), reverse=True)
    tercera = valores[2] if len(valores) > 2 else 0
    local_comp = partido.get("contexto_competitivo_local")
    visitante_comp = partido.get("contexto_competitivo_visitante")
    local_necesita = necesidad_viva_motor(local_comp)
    visitante_necesita = necesidad_viva_motor(visitante_comp)
    local_cerrado = objetivo_cerrado_motor(local_comp)
    visitante_cerrado = objetivo_cerrado_motor(visitante_comp)
    local_descenso = descenso_vivo_motor(local_comp)
    visitante_descenso = descenso_vivo_motor(visitante_comp)
    top = signo_top(probs)
    score = prioridad_cobertura(partido)
    detalle_indice = partido.get("_indice_sorpresa_quinielistica") or {}
    indice = indice_sorpresa_partido(partido)

    if tercera >= 18:
        score += 85
    elif tercera >= 14:
        score += 40
    elif tercera < 8:
        score -= 70
    else:
        score -= 35

    duelo_necesidades = local_necesita and visitante_necesita
    necesitado_vs_cerrado = (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado)
    ambos_cerrados = local_cerrado and visitante_cerrado
    margen = valores[0] - valores[1] if len(valores) > 1 else 0

    if top == "X" and tercera >= 18:
        score += 25
    if detalle_indice.get("cobertura_sugerida") == "TRIPLE":
        score += 95 + indice * 0.55
    elif detalle_indice.get("cobertura_sugerida") == "DOBLE":
        score -= 20
    if duelo_necesidades:
        score += 95
    if (local_descenso or visitante_descenso) and duelo_necesidades:
        score += 60
    if necesitado_vs_cerrado:
        score -= 55
        if tercera >= 22 and margen <= 10:
            score += 25
    if ambos_cerrados:
        score -= 35
    return score


def prioridad_doble(partido):
    probs = partido.get("probabilidades", {})
    valores = sorted(probs.values(), reverse=True)
    margen = valores[0] - valores[1] if len(valores) > 1 else 0
    tercera = valores[2] if len(valores) > 2 else 0
    top = signo_top(probs)
    score = prioridad_cobertura(partido)
    detalle_indice = partido.get("_indice_sorpresa_quinielistica") or {}
    indice = indice_sorpresa_partido(partido)

    local_comp = partido.get("contexto_competitivo_local")
    visitante_comp = partido.get("contexto_competitivo_visitante")
    local_necesita = necesidad_viva_motor(local_comp)
    visitante_necesita = necesidad_viva_motor(visitante_comp)
    local_cerrado = objetivo_cerrado_motor(local_comp)
    visitante_cerrado = objetivo_cerrado_motor(visitante_comp)
    duelo_necesidades = local_necesita and visitante_necesita
    necesitado_vs_cerrado = (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado)

    if tercera < 10:
        score += 45
    elif tercera >= 22:
        score -= 50
    if detalle_indice.get("cobertura_sugerida") == "DOBLE":
        score += 80 + indice * 0.45
    elif detalle_indice.get("cobertura_sugerida") == "TRIPLE":
        score -= 30
    if margen < 12:
        score += 30
    if necesitado_vs_cerrado:
        score += 55
    if duelo_necesidades and margen < 14:
        score += 25
    if top == "X":
        score += 8
    return score


def margen_probabilidades(probs):
    valores = sorted([float(v) for v in (probs or {}).values()], reverse=True)
    if len(valores) < 2:
        return 0.0
    return round(valores[0] - valores[1], 2)


def probabilidad_top(probs):
    valores = [float(v) for v in (probs or {}).values()]
    return round(max(valores), 2) if valores else 0.0


def tercera_probabilidad_valor(probs):
    valores = sorted([float(v) for v in (probs or {}).values()], reverse=True)
    return round(valores[2], 2) if len(valores) > 2 else 0.0


def perfil_riesgo_boleto(evaluados):
    riesgos = []
    for partido in evaluados:
        probs = partido.get("probabilidades", {})
        margen = margen_probabilidades(probs)
        top = probabilidad_top(probs)
        tercera = tercera_probabilidad_valor(probs)
        inc = float(partido.get("incertidumbre") or 0)
        sorpresa = float(partido.get("probabilidad_sorpresa") or 0)
        x_prob = float(probs.get("X") or 0)
        indice = partido.get("_indice_sorpresa_quinielistica") or indice_sorpresa_quinielistica(partido)
        indice_valor = float(indice.get("indice") or 0)
        if (
            inc >= 115
            or sorpresa >= 55
            or margen < 8
            or top < 45
            or x_prob >= 33
            or indice_valor >= 45
            or indice.get("cobertura_sugerida") != "FIJO"
        ):
            riesgos.append({
                "num": partido.get("num"),
                "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
                "incertidumbre": round(inc, 2),
                "probabilidad_sorpresa": round(sorpresa, 2),
                "probabilidad_top": top,
                "margen": margen,
                "tercera_probabilidad": tercera,
                "prioridad_cobertura": round(prioridad_cobertura(partido), 2),
                "indice_sorpresa_quinielistica": indice_valor,
                "categoria_sorpresa": indice.get("categoria"),
                "favorito": indice.get("favorito"),
                "favorito_nombre": indice.get("favorito_nombre"),
                "favorito_atacable": bool(indice.get("favorito_atacable")),
                "signos_contra_favorito": indice.get("signos_contra_favorito", []),
                "cobertura_sorpresa_sugerida": indice.get("cobertura_sugerida"),
                "motivo_sorpresa": "; ".join(indice.get("motivos", [])[:3]),
            })
    return sorted(
        riesgos,
        key=lambda p: (
            p["indice_sorpresa_quinielistica"],
            p["prioridad_cobertura"],
            p["incertidumbre"],
        ),
        reverse=True,
    )


def riesgos_no_cubiertos_por_presupuesto(partidos):
    riesgos = []
    for partido in partidos:
        tipo = str(partido.get("tipo") or "").upper()
        if tipo != "FIJO":
            continue
        indice = float(partido.get("indice_sorpresa_quinielistica") or 0)
        sugerida = str(partido.get("cobertura_sorpresa_sugerida") or "FIJO").upper()
        calidad = str(partido.get("calidad_datos") or "").lower()
        tercera = float(partido.get("tercera_probabilidad") or 0)
        if sugerida == "FIJO" and indice < 60 and not (calidad == "baja" and tercera >= 18):
            continue
        riesgos.append({
            "num": partido.get("num"),
            "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
            "tipo_final": tipo,
            "signo_final": partido.get("signo_final"),
            "cobertura_sorpresa_sugerida": sugerida,
            "indice_sorpresa_quinielistica": indice,
            "tercera_probabilidad": tercera,
            "probabilidad_sorpresa": partido.get("probabilidad_sorpresa"),
            "calidad_datos": partido.get("calidad_datos"),
            "motivo": "Riesgo detectado, pero no cubierto por el limite de dobles/triples del boleto.",
        })
    return sorted(
        riesgos,
        key=lambda item: (
            item["indice_sorpresa_quinielistica"],
            float(item.get("probabilidad_sorpresa") or 0),
            item["tercera_probabilidad"],
        ),
        reverse=True,
    )


def cobertura_automatica(evaluados, aprendizaje=None):
    riesgos = perfil_riesgo_boleto(evaluados)
    muy_abiertos = [
        p for p in evaluados
        if (
            tercera_probabilidad_valor(p.get("probabilidades", {})) >= 20
            and (float(p.get("incertidumbre") or 0) >= 118 or margen_probabilidades(p.get("probabilidades", {})) < 6)
        )
        or (p.get("_indice_sorpresa_quinielistica") or {}).get("cobertura_sugerida") == "TRIPLE"
    ]
    ataques_favorito = [
        p for p in evaluados
        if (p.get("_indice_sorpresa_quinielistica") or {}).get("favorito_atacable")
    ]
    if not riesgos:
        return 0, 0, "Sin riesgos claros: se conserva boleto sencillo."

    triples = 0
    if muy_abiertos and len(riesgos) >= 4:
        triples = 1
    if len(muy_abiertos) >= 5 and len(riesgos) >= 8:
        triples = 2

    base_dobles = max(len(riesgos), len(ataques_favorito))
    if base_dobles >= 9:
        dobles = 5
    elif base_dobles >= 6:
        dobles = 4
    elif base_dobles >= 3:
        dobles = 3
    else:
        dobles = min(2, base_dobles)

    detalle_aprendizaje = ""
    if aprendizaje_propio_activo(aprendizaje or {}):
        ajuste = ajuste_motor_aprendizaje(aprendizaje or {})
        min_dobles = int(ajuste.get("min_dobles_auto") or 0)
        min_triples = int(ajuste.get("min_triples_auto") or 0)
        if min_dobles and len(riesgos) >= min_dobles:
            dobles = max(dobles, min_dobles)
        if min_triples and muy_abiertos:
            triples = max(triples, min_triples)
        if min_dobles or min_triples:
            detalle_aprendizaje = (
                f" Aprendizaje propio aplicado: minimo {min_dobles} dobles y "
                f"{min_triples} triples por errores historicos."
            )

    # Mantiene una propuesta jugable por defecto y evita que la IA publique 14 fijos
    # cuando su propio perfil de riesgo detecta una jornada abierta.
    dobles = min(dobles, 5)
    triples = min(triples, 2)
    if triples and dobles + triples > 6:
        dobles = 6 - triples

    detalle = (
        f"Cobertura automatica: {len(riesgos)} partidos de riesgo detectados; "
        f"{len(ataques_favorito)} favoritos atacables por indice de sorpresa; "
        f"se recomiendan {dobles} dobles y {triples} triples.{detalle_aprendizaje}"
    )
    return dobles, triples, detalle


def multiplicador_signos(signos):
    total = 1
    for signo in signos or []:
        limpios = "".join(s for s in ("1", "X", "2") if s in str(signo or "").upper())
        total *= max(len(limpios), 1)
    return total


def apuestas_elige8_partidos(partidos):
    signos = [
        partido.get("signo_final") or partido.get("signo_base") or "1"
        for partido in (partidos or [])
        if partido.get("elige8")
    ]
    return multiplicador_signos(signos) if signos else 0


def coste(dobles, triples, elige8, partidos=None):
    apuestas = 2 ** dobles * 3 ** triples
    importe_quiniela = max(apuestas * PRECIO_APUESTA, IMPORTE_MINIMO)
    apuestas_elige8 = apuestas_elige8_partidos(partidos) if elige8 else 0
    if elige8 and not apuestas_elige8:
        apuestas_elige8 = apuestas
    importe_elige8 = apuestas_elige8 * PRECIO_ELIGE8 if elige8 else 0.0
    return {
        "apuestas": apuestas,
        "apuestas_elige8": apuestas_elige8,
        "importe_quiniela": round(importe_quiniela, 2),
        "importe_elige8": round(importe_elige8, 2),
        "importe_total": round(importe_quiniela + importe_elige8, 2),
    }


def guardar_salida_prediccion(salida, validar=False):
    jornada = salida.get("jornada")
    destino = (JUGADAS if validar else PREDICCIONES) / f"jornada_{jornada}.json"
    guardar_json(destino, salida)
    if validar:
        guardar_json(JUGADAS / "ultima_validada.json", salida)
    else:
        guardar_json(PREDICCIONES / "ultima_prediccion.json", salida)
    return destino


def partido_bloqueado(partido):
    return {
        "num": partido.get("num"),
        "local": partido.get("local"),
        "visitante": partido.get("visitante"),
        "fecha": partido.get("fecha"),
        "hora": partido.get("hora"),
        "resultado": partido.get("resultado", "Pendiente"),
        "signo_oficial": partido.get("signo_oficial", "Pendiente"),
        "signo_nuestro": partido.get("signo_nuestro", "No jugada"),
        "estado_prediccion": "bloqueada_por_compuerta_maestra",
        "signo_base": "",
        "signo_final": "",
        "pronostico_ia": "SIN PREDICCION",
        "elige8": False,
        "lectura": "Partido cargado oficialmente. Prediccion retenida por la compuerta maestra.",
    }


def prediccion_bloqueada_por_compuerta(jornada, data, compuerta, validar=False):
    partidos = [partido_bloqueado(p) for p in data.get("partidos", []) if int(p.get("num", 0) or 0) <= 14]
    pleno15 = data.get("pleno15")
    pleno_bloqueado = None
    if pleno15:
        pleno_bloqueado = partido_bloqueado(pleno15)
        pleno_bloqueado["lectura"] = "Pleno al 15 cargado oficialmente. Prediccion retenida por la compuerta maestra."
    salida = {
        "version": "1.4",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "jornada": jornada,
        "fecha": data.get("fecha") or data.get("fecha_texto"),
        "fuente": data.get("fuente"),
        "temporada_base": "2025/2026",
        "temporada": data.get("temporada", "2025/2026"),
        "competicion": data.get("competicion", "quiniela"),
        "estado": compuerta.get("estado", "bloqueada"),
        "prediccion_disponible": False,
        "aprendizaje_pendiente": compuerta.get("estado") == "aprendiendo" or not compuerta.get("aprendizaje_aplicado_anterior"),
        "prediccion_permitida": False,
        "publicar_solo_boleto": True,
        "publicar_prediccion": False,
        "compuerta_maestra": compuerta,
        "partidos": partidos,
        "pleno15": pleno_bloqueado,
        "configuracion": {
            "dobles": 0,
            "triples": 0,
            "elige8": False,
            "elige8_modo": "bloqueado",
            "elige8_modos_disponibles": ["conservador", "rentable"],
            "cobertura_auto": False,
        },
        "coste": {
            "apuestas": 0,
            "apuestas_elige8": 0,
            "importe_quiniela": 0,
            "importe_elige8": 0,
            "importe_total": 0,
        },
        "mensaje": compuerta.get("motivo") or "Prediccion bloqueada por compuerta maestra.",
        "motivo_bloqueo": compuerta.get("motivo") or "Compuerta maestra activa.",
        "resumen": {
            "fijos": 0,
            "dobles": 0,
            "triples": 0,
            "elige8_seleccionados": 0,
            "partidos_cargados": len(partidos),
            "pleno15_cargado": bool(pleno_bloqueado),
            "total_casillas": len(partidos) + (1 if pleno_bloqueado else 0),
            "prediccion": "BLOQUEADA_POR_COMPUERTA_MAESTRA",
        },
    }
    destino = guardar_salida_prediccion(salida, validar=validar)
    print(destino)
    return salida


def explicabilidad_partido(partido, signo, tipo):
    probs = partido.get("probabilidades") or {}
    orden = sorted(("1", "X", "2"), key=lambda s: float(probs.get(s) or 0), reverse=True)
    principal = orden[0] if orden else signo
    alternativa = orden[1] if len(orden) > 1 else ""
    prob_principal = float(probs.get(principal) or 0)
    prob_alternativa = float(probs.get(alternativa) or 0) if alternativa else 0.0
    margen = margen_probabilidades(probs)
    riesgo = partido.get("categoria_sorpresa") or "riesgo_no_clasificado"
    sorpresa = float(partido.get("probabilidad_sorpresa") or 0)
    if tipo == "TRIPLE":
        motivo = "Triple porque los tres signos siguen vivos o la sorpresa exige cobertura total."
    elif tipo == "DOBLE":
        motivo = "Doble porque el favorito no tiene margen suficiente para quedar como fijo limpio."
    else:
        motivo = "Fijo por mayor probabilidad relativa dentro del presupuesto disponible."
    return {
        "hipotesis_principal": f"{principal} como signo dominante ({prob_principal:.1f}%).",
        "hipotesis_alternativa": f"{alternativa} como alternativa ({prob_alternativa:.1f}%)." if alternativa else "",
        "motivo_fijo_doble_triple": motivo,
        "riesgo_de_sorpresa": {
            "categoria": riesgo,
            "probabilidad": sorpresa,
            "favorito_atacable": bool(partido.get("favorito_atacable")),
        },
        "justificacion_final": (
            f"Decision {tipo} {signo}: margen {margen:.1f} puntos, "
            f"indice sorpresa {partido.get('indice_sorpresa_quinielistica', 0)}."
        ),
    }


def predecir(jornada=None, dobles=None, triples=None, elige8=False, validar=False):
    memoria = cargar_json(MEMORIA, {})
    aprendizaje = cargar_json(APRENDIZAJE_PROPIO, {})
    pesos_dinamicos = normalizar_pesos_dinamicos(cargar_json(PESOS_DINAMICOS, {}))
    contexto = cargar_json(CONTEXTO_EQUIPOS, {})
    contexto_competitivo = cargar_json(CONTEXTO_COMPETITIVO, {})
    patrones_competitivos = cargar_json(PATRONES_COMPETITIVOS, {})
    perfiles_autonomos = cargar_json(PERFILES_EQUIPOS, {})
    modelo_runtime = preparar_modelo_predictivo_runtime(ROOT)
    jornada = jornada or detectar_jornada_activa()
    data = cargar_json(JORNADAS / f"jornada_{jornada}.json", {})
    partidos_base = [p for p in data.get("partidos", []) if int(p.get("num", 0)) <= 14]
    if not partidos_base:
        raise SystemExit(f"No hay partidos para jornada {jornada}")

    compuerta = estado_compuerta(jornada, DATA)
    if not compuerta.get("prediccion_permitida"):
        return prediccion_bloqueada_por_compuerta(jornada, data, compuerta, validar=validar)

    evaluados = []
    for partido in partidos_base:
        probs, local, visitante, diff = calcular_probabilidades(memoria, partido)
        probs, ajuste_modelo_entrenado = ajustar_por_modelo_entrenado(probs, partido, modelo_runtime)
        contexto_local = buscar_contexto_equipo(contexto, partido.get("local", ""))
        contexto_visitante = buscar_contexto_equipo(contexto, partido.get("visitante", ""))
        probs, riesgo_contexto, lecturas_contexto = ajustar_por_contexto(probs, contexto_local, contexto_visitante)
        probs, riesgo_perfiles, lecturas_perfiles, perfil_local, perfil_visitante = ajustar_por_perfiles_autonomos(
            probs, perfiles_autonomos, partido.get("local", ""), partido.get("visitante", "")
        )
        local_comp = buscar_contexto_competitivo(contexto_competitivo, partido.get("local", ""))
        visitante_comp = buscar_contexto_competitivo(contexto_competitivo, partido.get("visitante", ""))
        probs, riesgo_motivacion, lecturas_motivacion = ajustar_por_motivacion(probs, local_comp, visitante_comp)
        probs, riesgo_patrones, lecturas_patrones = ajustar_por_patrones_aprendidos(
            probs, patrones_competitivos, local_comp, visitante_comp
        )
        lecturas_motivacion.extend(lecturas_perfiles)
        lecturas_motivacion.extend(lecturas_patrones)
        probs, riesgo_aprendizaje, lecturas_aprendizaje = ajustar_por_aprendizaje_propio(
            probs, local, visitante, aprendizaje
        )
        lecturas_motivacion.extend(lecturas_aprendizaje)
        probs, riesgo_pesos_dinamicos, lecturas_pesos_dinamicos = ajustar_por_pesos_dinamicos(
            probs, pesos_dinamicos, local_comp, visitante_comp, contexto_local, contexto_visitante
        )
        lecturas_motivacion.extend(lecturas_pesos_dinamicos)
        inc = incertidumbre(
            probs,
            local,
            visitante,
            diff,
            riesgo_contexto + riesgo_perfiles + riesgo_motivacion + riesgo_patrones + riesgo_aprendizaje + riesgo_pesos_dinamicos,
        )
        sorpresa = probabilidad_sorpresa(probs, inc)
        trazabilidad = trazabilidad_datos_partido(
            local,
            visitante,
            contexto_local,
            contexto_visitante,
            local_comp,
            visitante_comp,
        )
        trazabilidad["modelo_entrenado"] = ajuste_modelo_entrenado
        if ajuste_modelo_entrenado.get("activo"):
            trazabilidad["origen_probabilidades"] = f"{trazabilidad['origen_probabilidades']}+modelo_entrenado"
        evaluado = {
            **partido,
            "probabilidades": probs,
            "signo_base": signo_top(probs),
            "incertidumbre": inc,
            "probabilidad_sorpresa": sorpresa,
            "riesgo_necesidad_real": riesgo_necesidad_real(local_comp, visitante_comp),
            "contexto_local": contexto_local,
            "contexto_visitante": contexto_visitante,
            "lecturas_contexto": lecturas_contexto,
            "perfil_autonomo_local": resumen_perfil_autonomo(perfil_local),
            "perfil_autonomo_visitante": resumen_perfil_autonomo(perfil_visitante),
            "ajuste_perfiles_autonomos": {
                "activo": bool(lecturas_perfiles),
                "riesgo_extra": riesgo_perfiles,
                "lecturas": lecturas_perfiles,
            },
            "contexto_competitivo_local": local_comp,
            "contexto_competitivo_visitante": visitante_comp,
            "lecturas_motivacion": lecturas_motivacion,
            "ajuste_modelo_entrenado": ajuste_modelo_entrenado,
            "ajuste_aprendizaje": {
                "activo": bool(lecturas_aprendizaje),
                "riesgo_extra": riesgo_aprendizaje,
                "lecturas": lecturas_aprendizaje,
            },
            "ajuste_pesos_dinamicos": {
                "activo": bool(lecturas_pesos_dinamicos),
                "riesgo_extra": riesgo_pesos_dinamicos,
                "lecturas": lecturas_pesos_dinamicos,
            },
            "trazabilidad_datos": trazabilidad,
            "_local": local,
            "_visitante": visitante,
            "_diff": diff,
        }
        indice_sorpresa = indice_sorpresa_quinielistica(evaluado, patrones_competitivos)
        evaluado["_indice_sorpresa_quinielistica"] = indice_sorpresa
        evaluado["indice_sorpresa_quinielistica"] = indice_sorpresa["indice"]
        evaluado["categoria_sorpresa"] = indice_sorpresa["categoria"]
        evaluado["favorito_atacable"] = indice_sorpresa["favorito_atacable"]
        evaluados.append(evaluado)

    cobertura_auto = dobles is None and triples is None
    criterio_cobertura = "Cobertura indicada manualmente."
    if cobertura_auto:
        dobles, triples, criterio_cobertura = cobertura_automatica(evaluados, aprendizaje)
    else:
        dobles = int(dobles or 0)
        triples = int(triples or 0)

    por_triple = sorted(evaluados, key=prioridad_triple, reverse=True)
    triples_set = {p["num"] for p in por_triple[:triples]}
    por_doble = sorted(
        [p for p in evaluados if p["num"] not in triples_set],
        key=prioridad_doble,
        reverse=True,
    )
    dobles_set = {p["num"] for p in por_doble[:dobles]}

    partidos = []
    for partido in sorted(evaluados, key=lambda p: p["num"]):
        if partido["num"] in triples_set:
            signo = "1X2"
            tipo = "TRIPLE"
        elif partido["num"] in dobles_set:
            signo = doble_top(partido["probabilidades"])
            tipo = "DOBLE"
        else:
            signo = partido["signo_base"]
            tipo = "FIJO"

        explicacion = explicabilidad_partido(partido, signo, tipo)
        razonamiento = explicar(
            partido,
            partido["probabilidades"],
            signo,
            partido["_local"],
            partido["_visitante"],
            partido["_diff"],
            tipo,
            partido.get("contexto_local"),
            partido.get("contexto_visitante"),
            partido.get("lecturas_contexto"),
            partido.get("contexto_competitivo_local"),
            partido.get("contexto_competitivo_visitante"),
            partido.get("lecturas_motivacion"),
            partido.get("probabilidad_sorpresa"),
            partido.get("_indice_sorpresa_quinielistica"),
        )
        partidos.append({
            "num": partido["num"],
            "local": partido.get("local"),
            "visitante": partido.get("visitante"),
            "resultado": partido.get("resultado"),
            "signo_oficial": partido.get("signo_oficial"),
            "probabilidades": partido["probabilidades"],
            "confianza_signos": niveles_confianza_signos(partido["probabilidades"]),
            "signo_base": partido["signo_base"],
            "signo_final": signo,
            "tipo": tipo,
            "incertidumbre": partido["incertidumbre"],
            "probabilidad_sorpresa": partido["probabilidad_sorpresa"],
            "probabilidad_top": probabilidad_top(partido["probabilidades"]),
            "margen_probabilidad": margen_probabilidades(partido["probabilidades"]),
            "tercera_probabilidad": tercera_probabilidad_valor(partido["probabilidades"]),
            "riesgo_necesidad_real": partido["riesgo_necesidad_real"],
            "indice_sorpresa_quinielistica": partido["indice_sorpresa_quinielistica"],
            "surprise_score": partido["indice_sorpresa_quinielistica"],
            "categoria_sorpresa": partido["categoria_sorpresa"],
            "favorito_atacable": partido["favorito_atacable"],
            "favorito": partido["_indice_sorpresa_quinielistica"].get("favorito"),
            "favorito_nombre": partido["_indice_sorpresa_quinielistica"].get("favorito_nombre"),
            "signo_sorpresa_principal": partido["_indice_sorpresa_quinielistica"].get("signo_sorpresa_principal"),
            "signos_contra_favorito": partido["_indice_sorpresa_quinielistica"].get("signos_contra_favorito", []),
            "cobertura_sorpresa_sugerida": partido["_indice_sorpresa_quinielistica"].get("cobertura_sugerida"),
            "motivos_sorpresa": partido["_indice_sorpresa_quinielistica"].get("motivos", []),
            "origen_probabilidades": partido["trazabilidad_datos"]["origen_probabilidades"],
            "calidad_datos": partido["trazabilidad_datos"]["calidad_datos"],
            "trazabilidad_datos": partido["trazabilidad_datos"],
            "perfil_autonomo_local": partido["perfil_autonomo_local"],
            "perfil_autonomo_visitante": partido["perfil_autonomo_visitante"],
            "ajuste_perfiles_autonomos": partido["ajuste_perfiles_autonomos"],
            "ajuste_modelo_entrenado": partido["ajuste_modelo_entrenado"],
            "ajuste_aprendizaje": partido["ajuste_aprendizaje"],
            "ajuste_pesos_dinamicos": partido["ajuste_pesos_dinamicos"],
            "elige8": False,
            "razonamiento": razonamiento,
            "explicabilidad_ia": explicacion,
            "hipotesis_principal": explicacion["hipotesis_principal"],
            "hipotesis_alternativa": explicacion["hipotesis_alternativa"],
            "motivo_fijo_doble_triple": explicacion["motivo_fijo_doble_triple"],
            "riesgo_de_sorpresa": explicacion["riesgo_de_sorpresa"],
            "justificacion_final": explicacion["justificacion_final"],
        })

    if elige8:
        elige8_set = {p["num"] for p in sorted(partidos, key=prioridad_elige8, reverse=True)[:8]}
        for partido in partidos:
            partido["elige8"] = partido["num"] in elige8_set

    riesgos_sin_cubrir = riesgos_no_cubiertos_por_presupuesto(partidos)
    ataques_favorito_prioritarios = [
        {
            "num": p["num"],
            "partido": f"{p['local']} - {p['visitante']}",
            "favorito": p["favorito"],
            "favorito_nombre": p["favorito_nombre"],
            "indice_sorpresa_quinielistica": p["indice_sorpresa_quinielistica"],
            "signo_sorpresa_principal": p["signo_sorpresa_principal"],
            "signos_contra_favorito": p["signos_contra_favorito"],
            "cobertura_sorpresa_sugerida": p["cobertura_sorpresa_sugerida"],
            "tipo_final": p["tipo"],
            "signo_final": p["signo_final"],
            "motivo_sorpresa": "; ".join(p["motivos_sorpresa"][:3]),
        }
        for p in sorted(partidos, key=lambda item: item["indice_sorpresa_quinielistica"], reverse=True)
        if p["favorito_atacable"]
    ][:8]
    ranking_incertidumbre_coberturas = [
        {
            "num": p["num"],
            "partido": f"{p['local']} - {p['visitante']}",
            "tipo_final": p["tipo"],
            "incertidumbre": p["incertidumbre"],
            "probabilidad_sorpresa": p["probabilidad_sorpresa"],
            "surprise_score": p["surprise_score"],
            "margen_probabilidad": p["margen_probabilidad"],
        }
        for p in sorted(
            partidos,
            key=lambda item: (
                float(item.get("incertidumbre") or 0),
                float(item.get("surprise_score") or 0),
                -float(item.get("margen_probabilidad") or 0),
            ),
            reverse=True,
        )
    ]
    ranking_elige8_confianza_real = [
        {
            "num": p["num"],
            "partido": f"{p['local']} - {p['visitante']}",
            "signo_final": p["signo_final"],
            "probabilidad_top": p["probabilidad_top"],
            "margen_probabilidad": p["margen_probabilidad"],
            "surprise_score": p["surprise_score"],
            "elige8": p["elige8"],
        }
        for p in sorted(partidos, key=prioridad_elige8, reverse=True)
    ][:8]

    salida = {
        "version": "1.4",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "jornada": jornada,
        "temporada_base": memoria.get("temporada", "2025/2026"),
        "estado": "publicada" if validar else "lista_para_publicar",
        "prediccion_disponible": True,
        "prediccion_permitida": True,
        "publicar_solo_boleto": False,
        "publicar_prediccion": True,
        "compuerta_maestra": compuerta,
        "configuracion": {
            "dobles": dobles,
            "triples": triples,
            "elige8": elige8,
            "elige8_modo": "conservador" if elige8 else "desactivado",
            "elige8_modos_disponibles": ["conservador", "rentable"],
            "cobertura_auto": cobertura_auto,
        },
        "coste": coste(dobles, triples, elige8, partidos),
        "partidos": partidos,
        "criterio_cobertura": criterio_cobertura,
        "ataques_favorito_prioritarios": ataques_favorito_prioritarios,
        "ranking_incertidumbre_coberturas": ranking_incertidumbre_coberturas[:8],
        "ranking_elige8_confianza_real": ranking_elige8_confianza_real,
        "riesgos_detectados": perfil_riesgo_boleto(evaluados)[:8],
        "riesgos_no_cubiertos_por_presupuesto": riesgos_sin_cubrir[:8],
        "alertas_boleto": [
            {
                "nivel": "media",
                "titulo": "Riesgos no cubiertos por presupuesto",
                "detalle": (
                    f"{len(riesgos_sin_cubrir)} partidos quedan como FIJO pese a tener senales de sorpresa "
                    "o datos insuficientes para tratarlos como seguros."
                ),
            }
        ] if riesgos_sin_cubrir else [],
        "contexto_equipos": {
            "generado_en": contexto.get("generado_en"),
            "fuentes": contexto.get("fuentes", []),
        },
        "contexto_competitivo": {
            "generado_en": contexto_competitivo.get("generado_en"),
            "reglas": contexto_competitivo.get("reglas", {}),
        },
        "aprendizaje_motor": {
            "activo": aprendizaje_propio_activo(aprendizaje),
            "precision": aprendizaje.get("precision"),
            "partidos_revisados": aprendizaje.get("partidos_revisados"),
            "fallos_por_tipo": aprendizaje.get("fallos_por_tipo", {}),
            "ajuste_motor": ajuste_motor_aprendizaje(aprendizaje),
            "pesos_dinamicos": {
                "generado_en": pesos_dinamicos.get("generado_en"),
                "pesos": pesos_dinamicos.get("pesos", {}),
                "ajustes": pesos_dinamicos.get("ajustes", []),
            },
        },
        "modelo_predictivo": {
            "activo": bool(modelo_runtime.get("activo")),
            "motivo": modelo_runtime.get("motivo"),
            "manifest": modelo_runtime.get("manifest", {}),
        },
        "pleno15": data.get("pleno15"),
        "resumen": {
            "fijos": sum(1 for p in partidos if p["tipo"] == "FIJO"),
            "dobles": sum(1 for p in partidos if p["tipo"] == "DOBLE"),
            "triples": sum(1 for p in partidos if p["tipo"] == "TRIPLE"),
            "elige8_seleccionados": sum(1 for p in partidos if p["elige8"]),
            "favoritos_atacables": sum(1 for p in partidos if p["favorito_atacable"]),
            "indice_sorpresa_max": max((p["indice_sorpresa_quinielistica"] for p in partidos), default=0),
            "riesgos_no_cubiertos_por_presupuesto": len(riesgos_sin_cubrir),
            "calidad_datos": {
                "alta": sum(1 for p in partidos if p.get("calidad_datos") == "alta"),
                "media_baja": sum(1 for p in partidos if p.get("calidad_datos") == "media_baja"),
                "baja": sum(1 for p in partidos if p.get("calidad_datos") == "baja"),
            },
            "partidos_sin_memoria_estadistica": sum(
                1
                for p in partidos
                if not all((p.get("trazabilidad_datos") or {}).get("memoria_estadistica", {}).values())
            ),
        },
    }

    snapshot = crear_snapshot_prediccion(salida)
    salida["snapshot_pre_cierre"] = snapshot
    destino = guardar_salida_prediccion(salida, validar=validar)
    print(destino)
    return salida


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jornada", type=int, default=None)
    parser.add_argument("--dobles", type=int, default=None)
    parser.add_argument("--triples", type=int, default=None)
    parser.add_argument("--elige8", action="store_true")
    parser.add_argument("--validar", action="store_true")
    args = parser.parse_args()
    predecir(args.jornada, args.dobles, args.triples, args.elige8, args.validar)


if __name__ == "__main__":
    main()
