import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from compuerta_jornada import estado_compuerta
from datos_profesionales import buscar_partido as buscar_datos_profesionales_partido
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
DATOS_PROFESIONALES = DATA / "datos_profesionales.json"
CONTEXTO_COMPETITIVO = DATA / "memoria_ia" / "contexto_competitivo.json"
PATRONES_COMPETITIVOS = DATA / "memoria_ia" / "patrones_competitivos.json"
PERFILES_EQUIPOS = DATA / "memoria_ia" / "perfiles_equipos.json"
CLASIFICACIONES_MUNDIAL = DATA / "memoria_ia" / "clasificaciones_mundial_2026.json"
FUENTE_LOSILLA = DATA / "memoria_ia" / "fuente_losilla.json"
FUENTE_LESIONES_LALIGA = DATA / "memoria_ia" / "fuente_lesiones_laliga.json"
FUENTE_LESIONES_RESPALDO = DATA / "memoria_ia" / "fuente_lesiones_jornadaperfecta.json"
SORPRESAS_MERCADO = DATA / "memoria_ia" / "sorpresas_mercado.json"
JORNADAS = DATA / "jornadas"
PREDICCIONES = DATA / "predicciones"
JUGADAS = DATA / "quinielas_jugadas"
MODELO_PREDICTIVO = DATA / "modelo_predictivo"

PRECIO_APUESTA = 0.75
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



DERBIS_HISTORICOS = {
    tuple(sorted(("real madrid", "barcelona"))),
    tuple(sorted(("atletico madrid", "real madrid"))),
    tuple(sorted(("sevilla", "betis"))),
    tuple(sorted(("athletic", "real sociedad"))),
    tuple(sorted(("espanyol", "barcelona"))),
    tuple(sorted(("deportivo", "celta"))),
    tuple(sorted(("brasil", "argentina"))),
    tuple(sorted(("argentina", "uruguay"))),
    tuple(sorted(("espana", "portugal"))),
    tuple(sorted(("francia", "alemania"))),
    tuple(sorted(("paises bajos", "alemania"))),
    tuple(sorted(("mexico", "estados unidos"))),
}


def normalizar_situacion(valor):
    texto = normalizar(valor or "")
    equivalencias = {
        "ya clasificada": "ya_clasificada",
        "clasificada": "ya_clasificada",
        "ya clasificado": "ya_clasificada",
        "clasificado": "ya_clasificada",
        "eliminada": "eliminada",
        "eliminado": "eliminada",
        "sin opciones": "eliminada",
        "sin opciones matematicas": "eliminada",
    }
    return equivalencias.get(texto, texto.replace(" ", "_"))


def es_ya_clasificada(equipo):
    return normalizar_situacion((equipo or {}).get("situacion_competitiva")) == "ya_clasificada"


def es_eliminada(equipo):
    return normalizar_situacion((equipo or {}).get("situacion_competitiva")) == "eliminada"


def iterar_equipos_mundial(data):
    if isinstance(data, dict):
        if any(k in data for k in ("equipo", "nombre", "seleccion")):
            yield data
        for value in data.values():
            yield from iterar_equipos_mundial(value)
    elif isinstance(data, list):
        for item in data:
            yield from iterar_equipos_mundial(item)


def nombre_item_competitivo(item):
    return item.get("equipo") or item.get("nombre") or item.get("seleccion") or item.get("name") or ""


def buscar_equipo_mundial(clasificaciones_mundial, nombre):
    return mejor_coincidencia_equipo(list(iterar_equipos_mundial(clasificaciones_mundial or {})), nombre, nombre_item_competitivo)


def ligas_losilla(fuente_losilla):
    ligas = (((fuente_losilla or {}).get("clasificaciones") or {}).get("ligas") or {})
    return ligas.items() if isinstance(ligas, dict) else []


def buscar_equipo_losilla(fuente_losilla, nombre):
    mejor = None; mejor_liga = ""; mejor_tabla = []; mejor_score = 0
    for liga, tabla in ligas_losilla(fuente_losilla):
        if not isinstance(tabla, list):
            continue
        for fila in tabla:
            score = puntuacion_nombre_equipo(fila.get("equipo", ""), nombre)
            if score > mejor_score:
                mejor = fila; mejor_liga = liga; mejor_tabla = tabla; mejor_score = score
    return (mejor, mejor_liga, mejor_tabla) if mejor_score >= 55 else (None, "", [])


def puntos_fila(fila):
    try:
        return float(fila.get("Pts") if fila.get("Pts") is not None else fila.get("pts") or 0)
    except Exception:
        return 0.0


def posicion_fila(fila):
    try:
        return int(fila.get("posicion") or fila.get("pos") or 0)
    except Exception:
        return 0


def pj_fila(fila):
    try:
        return int(fila.get("PJ") if fila.get("PJ") is not None else fila.get("pj") or 0)
    except Exception:
        return 0


def contexto_liga_losilla(fila, liga, tabla):
    if not fila or not tabla:
        return {"descenso": False, "europa_ascenso": False, "sin_objetivos": False}
    tabla_ordenada = sorted(tabla, key=posicion_fila)
    total = len(tabla_ordenada); pos = posicion_fila(fila); pts = puntos_fila(fila); liga_norm = normalizar(liga)
    puestos_descenso = 3 if total >= 16 else max(1, round(total * 0.15))
    corte_descenso_idx = max(total - puestos_descenso, 0)
    pts_corte_descenso = puntos_fila(tabla_ordenada[corte_descenso_idx]) if total else 0
    en_descenso = pos >= max(total - 2, 1); cerca_descenso = pts <= pts_corte_descenso + 3
    plazas_objetivo = 2 if "segunda" in liga_norm else (6 if total >= 16 else max(2, round(total * 0.25)))
    idx_obj = min(max(plazas_objetivo - 1, 0), total - 1)
    pts_corte_obj = puntos_fila(tabla_ordenada[idx_obj]) if total else 0
    en_objetivo = pos <= plazas_objetivo; cerca_objetivo = pts >= pts_corte_obj - 3
    pj_max = max((pj_fila(x) for x in tabla_ordenada), default=0)
    ultimas_5 = pj_max >= 33 if total >= 16 else pj_max >= max(1, total * 2 - 5)
    return {"liga": liga, "posicion": pos, "puntos": pts, "total_equipos": total, "descenso": bool(en_descenso or cerca_descenso), "europa_ascenso": bool(en_objetivo or cerca_objetivo), "sin_objetivos": bool((not en_descenso and not cerca_descenso) and (not en_objetivo and not cerca_objetivo) and ultimas_5)}


def partido_es_derbi(partido):
    par = tuple(sorted((normalizar(partido.get("local", "")), normalizar(partido.get("visitante", "")))))
    if par in DERBIS_HISTORICOS:
        return True
    texto = normalizar(" ".join(str(partido.get(k, "")) for k in ("competicion", "liga", "rivalidad", "observaciones", "contexto")))
    return "derbi" in texto or "clasico" in texto or "maxima rivalidad" in texto


def partido_losilla_por_numero_o_equipos(fuente_losilla, partido):
    partidos = (((fuente_losilla or {}).get("probabilidades") or {}).get("partidos") or [])
    numero = partido.get("num") or partido.get("numero")
    for item in partidos:
        if numero and int(item.get("numero") or 0) == int(numero):
            return item
    for item in partidos:
        if puntuacion_nombre_equipo(item.get("local", ""), partido.get("local", "")) >= 55 and puntuacion_nombre_equipo(item.get("visitante", ""), partido.get("visitante", "")) >= 55:
            return item
    return {}


def mercado_losilla_signos(fuente_losilla, partido):
    item = partido_losilla_por_numero_o_equipos(fuente_losilla, partido)
    signos = item.get("probabilidades_signo") or {}
    return {"1": float(signos.get("1") if signos.get("1") is not None else item.get("probabilidad_1") or 0), "X": float(signos.get("X") if signos.get("X") is not None else item.get("probabilidad_X") or 0), "2": float(signos.get("2") if signos.get("2") is not None else item.get("probabilidad_2") or 0)}


def sumar_alerta(detalle, alerta, lectura):
    if alerta not in detalle["alertas"]:
        detalle["alertas"].append(alerta)
    if lectura:
        detalle["lecturas"].append(lectura)


def calcular_ajuste_motivacion(partido, clasificaciones_mundial, fuente_losilla):
    """Devuelve ajustes en puntos porcentuales por motivacion competitiva."""
    probs = {s: float((partido.get("probabilidades") or {}).get(s) or 0) for s in ("1", "X", "2")}
    top = signo_top(probs) if any(probs.values()) else "1"
    detalle = {"activo": False, "ajuste_por_signo": {"1": 0.0, "X": 0.0, "2": 0.0}, "alertas": [], "lecturas": [], "sorpresa_potencial": False, "nivel_sorpresa": "", "forzar_cobertura": "", "mercado_losilla": mercado_losilla_signos(fuente_losilla, partido), "casos_aplicados": []}
    local_nombre = partido.get("local", ""); visitante_nombre = partido.get("visitante", "")
    mundial_local = buscar_equipo_mundial(clasificaciones_mundial, local_nombre); mundial_visitante = buscar_equipo_mundial(clasificaciones_mundial, visitante_nombre)
    losilla_local, liga_local, tabla_local = buscar_equipo_losilla(fuente_losilla, local_nombre)
    losilla_visitante, liga_visitante, tabla_visitante = buscar_equipo_losilla(fuente_losilla, visitante_nombre)
    liga_ctx = {"1": contexto_liga_losilla(losilla_local, liga_local, tabla_local), "2": contexto_liga_losilla(losilla_visitante, liga_visitante, tabla_visitante)}
    if top in {"1", "2"}:
        fav_signo = top; rival_signo = "2" if top == "1" else "1"; fav_mundial = mundial_local if fav_signo == "1" else mundial_visitante; rival_mundial = mundial_visitante if fav_signo == "1" else mundial_local
        if es_ya_clasificada(fav_mundial) and es_eliminada(rival_mundial):
            ajuste = min(max((probs[fav_signo] - probs.get(rival_signo, 0)) * 0.18, 8.0), 15.0)
            detalle["ajuste_por_signo"][fav_signo] -= ajuste; detalle["ajuste_por_signo"][rival_signo] += ajuste; detalle["casos_aplicados"].append("A")
            sumar_alerta(detalle, "favorito_relajado_rival_desesperado", "Motivacion: favorito ya clasificado ante rival eliminado; se ataca la relajacion del favorito.")
    if es_ya_clasificada(mundial_local) and es_ya_clasificada(mundial_visitante):
        detalle["ajuste_por_signo"]["1"] -= 5.0; detalle["ajuste_por_signo"]["2"] -= 5.0; detalle["ajuste_por_signo"]["X"] += 10.0; detalle["casos_aplicados"].append("B")
        sumar_alerta(detalle, "ambos_clasificados_sin_tension", "Motivacion: ambos clasificados; sube la X por menor tension competitiva.")
    for signo, equipo in (("1", mundial_local), ("2", mundial_visitante)):
        texto_equipo = normalizar(" ".join(str((equipo or {}).get(k, "")) for k in ("situacion_competitiva", "estado", "lectura", "partido")))
        ultimo = bool((equipo or {}).get("ultimo_partido") or (equipo or {}).get("ultimo_partido_torneo") or "ultimo partido" in texto_equipo)
        if es_eliminada(equipo) and ultimo:
            detalle["ajuste_por_signo"][signo] += 6.5; detalle["ajuste_por_signo"]["X"] += 1.0; detalle["casos_aplicados"].append("C")
            sumar_alerta(detalle, "ultimo_partido_orgullo", "Motivacion: eliminado en ultimo partido; factor orgullo activo.")
    for signo in ("1", "2"):
        ctx = liga_ctx[signo]
        if ctx.get("descenso"):
            detalle["ajuste_por_signo"][signo] += 10.0; detalle["casos_aplicados"].append("E"); sumar_alerta(detalle, "presion_descenso", "Motivacion liga: equipo en zona o a tres puntos del descenso; se juega la vida.")
        if ctx.get("europa_ascenso"):
            detalle["ajuste_por_signo"][signo] += 6.5; detalle["casos_aplicados"].append("F"); sumar_alerta(detalle, "presion_europea_o_ascenso", "Motivacion liga: equipo en pelea europea/ascenso o a tres puntos de entrar.")
        if ctx.get("sin_objetivos"):
            detalle["ajuste_por_signo"][signo] -= 6.5; detalle["ajuste_por_signo"]["X"] += 3.25; detalle["casos_aplicados"].append("G"); sumar_alerta(detalle, "equipo_sin_objetivos", "Motivacion liga: equipo salvado y sin objetivos en tramo final; baja intensidad esperada.")
    if partido_es_derbi(partido):
        detalle["ajuste_por_signo"]["X"] += 10.0
        if top in {"1", "2"}:
            detalle["ajuste_por_signo"][top] -= 5.0; detalle["ajuste_por_signo"]["2" if top == "1" else "1"] += 5.0
        detalle["casos_aplicados"].append("H"); sumar_alerta(detalle, "derbi_todo_puede_pasar", "Motivacion: derbi/rivalidad historica; la forma reciente pierde peso y sube empate/sorpresa.")
    mercado = detalle["mercado_losilla"]
    signo_mercado, valor_mercado = max(mercado.items(), key=lambda item: item[1]) if mercado else ("", 0)
    if valor_mercado > 80 and detalle["alertas"] and int(partido.get("num") or partido.get("numero") or 0) <= 14:
        detalle["sorpresa_potencial"] = True; detalle["nivel_sorpresa"] = "alto"; detalle["forzar_cobertura"] = "TRIPLE" if len(detalle["alertas"]) >= 2 else "DOBLE"; detalle["casos_aplicados"].append("D")
        detalle["lecturas"].append(f"Mercado Losilla muy sesgado ({signo_mercado} {valor_mercado:.1f}%) con alerta motivacional: sorpresa potencial alta.")
    detalle["activo"] = bool(detalle["alertas"] or any(abs(v) > 0 for v in detalle["ajuste_por_signo"].values()))
    detalle["clasificacion_losilla"] = {"local": liga_ctx["1"], "visitante": liga_ctx["2"]}
    detalle = reforzar_ajuste_por_memoria_sorpresas(partido, detalle)
    return detalle



def categoria_sorpresa_desde_alertas_motor(detalle):
    alertas = set((detalle or {}).get("alertas") or [])
    if "derbi_todo_puede_pasar" in alertas:
        return "derbi"
    if alertas & {"equipo_sin_objetivos", "ambos_clasificados_sin_tension"}:
        return "partido_sin_presion"
    if alertas:
        return "motivacion_competitiva"
    return "desconocido"


def reforzar_ajuste_por_memoria_sorpresas(partido, detalle):
    if not detalle or not detalle.get("activo"):
        return detalle
    memoria = cargar_json(SORPRESAS_MERCADO, {"sorpresas": []})
    sorpresas = memoria.get("sorpresas") or []
    categoria = categoria_sorpresa_desde_alertas_motor(detalle)
    alertas = set(detalle.get("alertas") or [])
    if not alertas:
        return detalle
    coincidencias = [
        s for s in sorpresas
        if s.get("categoria_sorpresa") == categoria
        and (s.get("alerta_motivacion_detectada") in alertas or bool(alertas & set(s.get("alertas_motivacion_detectadas") or [])))
    ]
    if len(coincidencias) < 3:
        return detalle
    detalle["ajuste_por_signo"] = {
        signo: round(float(delta or 0) * 1.20, 2)
        for signo, delta in (detalle.get("ajuste_por_signo") or {}).items()
    }
    detalle["refuerzo_memoria_sorpresas_mercado"] = {
        "activo": True,
        "factor": 1.20,
        "coincidencias": len(coincidencias),
        "categoria_sorpresa": categoria,
        "alertas_match": sorted(alertas),
    }
    detalle.setdefault("lecturas", []).append(
        f"Memoria sorpresas mercado: {len(coincidencias)} casos previos con categoria {categoria}; se refuerza motivacion un 20%."
    )
    return detalle

def aplicar_ajuste_motivacion_competitiva(probs, ajuste):
    if not ajuste or not ajuste.get("activo"):
        return probs
    ajustadas = dict(probs)
    for signo, delta in (ajuste.get("ajuste_por_signo") or {}).items():
        if signo in ajustadas:
            ajustadas[signo] = float(ajustadas.get(signo) or 0) + float(delta or 0)
    return normalizar_probs(ajustadas)


def marcador_mas_probable_pleno_losilla(fuente_losilla):
    pleno = (((fuente_losilla or {}).get("probabilidades") or {}).get("pleno_al_15") or {})
    local = pleno.get("probabilidades_goles_local") or {}; visitante = pleno.get("probabilidades_goles_visitante") or {}
    if not local or not visitante:
        return {}
    return {"local": max(local.items(), key=lambda item: float(item[1] or 0))[0], "visitante": max(visitante.items(), key=lambda item: float(item[1] or 0))[0], "fuente": "fuente_losilla.pleno_al_15"}


def ajustar_pleno15_motivacion(pleno15, fuente_losilla, ajuste_pleno):
    salida = dict(pleno15 or {})
    marcador = marcador_mas_probable_pleno_losilla(fuente_losilla)
    if marcador:
        salida["marcador_probable_losilla"] = marcador; salida["pronostico_marcador"] = f"{marcador['local']}-{marcador['visitante']}"
    if ajuste_pleno and ajuste_pleno.get("activo"):
        salida["ajuste_motivacion"] = ajuste_pleno; salida["pronostico_marcador_ajustado"] = salida.get("pronostico_marcador"); salida["lectura_motivacion_pleno15"] = "Marcador del Pleno al 15 revisado por alertas de motivacion."
    return salida

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


def capas_profesionales_relevantes(datos_partido):
    capas = (datos_partido or {}).get("capas_disponibles") or {}
    return {
        "cuotas": bool(capas.get("cuotas")),
        "bajas_estructuradas": bool(capas.get("bajas_estructuradas")),
        "alineaciones_probables": bool(capas.get("alineaciones_probables")),
        "calendario_oficial": bool(capas.get("calendario_oficial")),
        "clasificacion_oficial": bool(capas.get("clasificacion_oficial")),
    }


def resumen_datos_profesionales_partido(datos_partido):
    if not datos_partido:
        return {"activo": False}
    cuotas = datos_partido.get("cuotas") or {}
    bajas = datos_partido.get("bajas") or {}
    alineaciones = datos_partido.get("alineaciones") or {}
    capas = capas_profesionales_relevantes(datos_partido)
    return {
        "activo": any(capas.values()),
        "capas": capas,
        "cuotas": {
            "disponibles": capas["cuotas"],
            "probabilidades_implicitas": cuotas.get("probabilidades_implicitas", {}),
            "overround": cuotas.get("overround"),
            "fuente": cuotas.get("fuente") or cuotas.get("proveedor"),
            "actualizado_en": cuotas.get("actualizado_en"),
        },
        "bajas": {
            lado: {
                "impacto_total": (bajas.get(lado) or {}).get("impacto_total", 0),
                "titulares_afectados": (bajas.get(lado) or {}).get("titulares_afectados", 0),
                "lesiones": len((bajas.get(lado) or {}).get("lesiones", [])),
                "sanciones": len((bajas.get(lado) or {}).get("sanciones", [])),
                "dudas": len((bajas.get(lado) or {}).get("dudas", [])),
            }
            for lado in ("local", "visitante")
        },
        "alineaciones": {
            lado: {
                "confirmada": (alineaciones.get(lado) or {}).get("confirmada", False),
                "confianza": (alineaciones.get(lado) or {}).get("confianza", 0),
                "titulares_probables": len((alineaciones.get(lado) or {}).get("titulares_probables", [])),
                "dudas": len((alineaciones.get(lado) or {}).get("dudas", [])),
            }
            for lado in ("local", "visitante")
        },
    }


PESO_MERCADO_LOSILLA_POR_CALIDAD = {
    "profesional": 0.15,
    "alta": 0.20,
    "media": 0.35,
    "media_baja": 0.45,
    "baja": 0.65,
}
PESO_MERCADO_LOSILLA_DEFECTO = 0.18


def ajustar_por_mercado_losilla(probs, mercado, calidad_datos=None):
    """Integra el consenso publico de eduardolosilla.es (promedio de
    tecnicos/quinielista/LAE/real) como señal de mercado independiente.

    El peso ya no es fijo: depende de "calidad_datos" (el mismo valor que
    calcula trazabilidad_datos_partido -profesional/alta/media/media_baja/
    baja). Si el motor tiene poco o nada propio (fallback puro, calidad
    "baja"), el consenso de mercado pesa mucho mas (0.65) que si el motor
    ya tiene estadistica real de ambos equipos (calidad "alta", 0.20): con
    un prior propio de baja calidad, un peso fijo del 18% no bastaba para
    corregir nada -verificado con datos reales de la jornada 73 (2026-07-17):
    los 4 indicadores de Losilla coincidian en 77-93% para el favorito del
    partido 1 y el motor publicaba igualmente un 43%, practicamente sin
    moverse de su prior de fallback. Si "calidad_datos" no se pasa (o no es
    un valor reconocido), se usa el peso fijo anterior (0.18) como red de
    seguridad para no romper llamadas existentes.

    Ya verificamos con datos reales (jornada 72, DECISION_LOG.md
    2026-07-13/14) que este consenso acierta un 71.4% en ligas donde el
    motor no tiene datos propios, frente al ~35% practicamente plano que da
    el motor sin señal real ahi -de ahi que a menor calidad de dato propio,
    mayor deba ser el peso del mercado.
    """
    total = sum(float((mercado or {}).get(s) or 0) for s in ("1", "X", "2"))
    if total <= 0:
        return probs, 0.0, []

    p = dict(probs)
    peso = PESO_MERCADO_LOSILLA_POR_CALIDAD.get(calidad_datos, PESO_MERCADO_LOSILLA_DEFECTO)
    top_motor = signo_top(p)
    top_mercado = signo_top(mercado)
    p = {
        signo: float(p.get(signo, 0)) * (1 - peso) + float(mercado.get(signo, 0)) * peso
        for signo in ("1", "X", "2")
    }
    riesgo_extra = 0.0
    lecturas = []
    if top_motor != top_mercado:
        riesgo_extra += 6.0
        lecturas.append(
            f"Mercado Losilla: el consenso publico ({top_mercado}) no coincide con el favorito del motor ({top_motor})."
        )
    lecturas.append(f"Mercado Losilla: consenso publico integrado con peso {peso:.2f} (calidad_datos={calidad_datos or 'desconocida'}).")
    return normalizar_probs(p), round(riesgo_extra, 2), lecturas


def buscar_lesiones_equipo(fuente_lesiones, nombre):
    """Busca las bajas de un equipo en fuente_lesiones_laliga.json por
    nombre difuso (mismo matcher que buscar_equipo_losilla). Esta fuente
    solo cubre LaLiga/Hypermotion -si el equipo no aparece (otra liga o
    seleccion), no hay ajuste, sin necesidad de una comprobacion de
    competicion aparte."""
    equipos = (fuente_lesiones or {}).get("equipos") or {}
    mejor = []
    mejor_score = 0
    for equipo, jugadores in equipos.items():
        score = puntuacion_nombre_equipo(equipo, nombre)
        if score > mejor_score:
            mejor = jugadores
            mejor_score = score
    return mejor if mejor_score >= 55 else []


def ajustar_por_lesiones_laliga(probs, lesiones_local, lesiones_visitante):
    """Ajuste pequeño y acotado por bajas reales de LaLiga (FutbolFantasy,
    ver DECISION_LOG.md 2026-07-18). Señal gruesa a proposito: contamos
    jugadores en categoria "lesionado" por equipo, sin poder pesar por
    titularidad/importancia real (no tenemos plantilla ni onces
    probables) -por eso el desplazamiento es pequeño y con tope, no una
    correccion fuerte.
    """
    contar = lambda lesiones: sum(1 for j in (lesiones or []) if (j or {}).get("categoria") == "lesionado")
    bajas_local = contar(lesiones_local)
    bajas_visitante = contar(lesiones_visitante)
    diferencia = bajas_visitante - bajas_local
    if diferencia == 0:
        return probs, 0.0, []

    p = dict(probs)
    peso_por_baja = 1.5
    tope = 6.0
    desplazamiento = max(min(diferencia * peso_por_baja, tope), -tope)
    p["1"] = float(p.get("1", 0)) + desplazamiento
    p["2"] = float(p.get("2", 0)) - desplazamiento
    lado_favorecido = "local" if desplazamiento > 0 else "visitante"
    riesgo_extra = round(min(abs(diferencia) * 2.0, 8.0), 2)
    lecturas = [
        f"Lesiones LaLiga (FutbolFantasy): {bajas_local} baja(s) confirmada(s) en el local, "
        f"{bajas_visitante} en el visitante -favorece ligeramente al {lado_favorecido}. "
        f"Señal gruesa: cuenta bajas, no pesa la importancia real del jugador."
    ]
    return normalizar_probs(p), riesgo_extra, lecturas


def ajustar_por_datos_profesionales(probs, datos_partido):
    if not datos_partido:
        return probs, 0.0, [], resumen_datos_profesionales_partido(None)

    p = dict(probs)
    riesgo_extra = 0.0
    lecturas = []
    cuotas = datos_partido.get("cuotas") or {}
    mercado = cuotas.get("probabilidades_implicitas") or {}
    if all(signo in mercado for signo in ("1", "X", "2")):
        try:
            overround = float(cuotas.get("overround") or 0)
        except (TypeError, ValueError):
            overround = 0.0
        peso = 0.30 if overround <= 8 else 0.22 if overround <= 14 else 0.14
        top_motor = signo_top(p)
        top_mercado = signo_top(mercado)
        p = {
            signo: float(p.get(signo, 0)) * (1 - peso) + float(mercado.get(signo, 0)) * peso
            for signo in ("1", "X", "2")
        }
        if top_motor != top_mercado:
            riesgo_extra += 9.0
            lecturas.append(
                f"Cuotas mercado: el favorito de mercado ({top_mercado}) no coincide con el motor ({top_motor})."
            )
        lecturas.append(f"Cuotas mercado: probabilidades 1X2 integradas con peso {peso:.2f}.")

    bajas = datos_partido.get("bajas") or {}
    impacto_local = float((bajas.get("local") or {}).get("impacto_total") or 0)
    impacto_visitante = float((bajas.get("visitante") or {}).get("impacto_total") or 0)
    if impacto_local:
        ajuste = min(impacto_local * 0.85, 5.0)
        p["1"] -= ajuste
        p["X"] += ajuste * 0.45
        p["2"] += ajuste * 0.55
        riesgo_extra += min(impacto_local * 1.5, 10.0)
        lecturas.append(f"Bajas local: impacto estructurado {impacto_local:.1f}; baja la confianza en el 1.")
    if impacto_visitante:
        ajuste = min(impacto_visitante * 0.85, 5.0)
        p["2"] -= ajuste
        p["X"] += ajuste * 0.45
        p["1"] += ajuste * 0.55
        riesgo_extra += min(impacto_visitante * 1.5, 10.0)
        lecturas.append(f"Bajas visitante: impacto estructurado {impacto_visitante:.1f}; baja la confianza en el 2.")

    alineaciones = datos_partido.get("alineaciones") or {}
    for lado, signo in (("local", "1"), ("visitante", "2")):
        alineacion = alineaciones.get(lado) or {}
        dudas = len(alineacion.get("dudas") or [])
        titulares = len(alineacion.get("titulares_probables") or [])
        confianza = float(alineacion.get("confianza") or 0)
        if dudas or (titulares and titulares < 10) or (confianza and confianza < 0.70):
            ajuste = 1.4 + min(dudas * 0.35, 1.2)
            rival = "2" if signo == "1" else "1"
            p[signo] -= ajuste
            p["X"] += ajuste * 0.55
            p[rival] += ajuste * 0.45
            riesgo_extra += 3.5 + dudas
            lecturas.append(
                f"Alineacion {lado}: once probable con dudas o baja confianza; sube la cobertura."
            )

    return normalizar_probs(p), round(riesgo_extra, 2), lecturas, resumen_datos_profesionales_partido(datos_partido)


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


def trazabilidad_datos_partido(
    local,
    visitante,
    contexto_local,
    contexto_visitante,
    local_comp,
    visitante_comp,
    datos_profesionales=None,
):
    memoria_local = bool(local)
    memoria_visitante = bool(visitante)
    noticias_local = bool((contexto_local or {}).get("noticias"))
    noticias_visitante = bool((contexto_visitante or {}).get("noticias"))
    competitivo_local = bool(local_comp)
    competitivo_visitante = bool(visitante_comp)
    capas_profesionales = capas_profesionales_relevantes(datos_profesionales)
    profesional_predictivo = any(
        capas_profesionales.get(clave)
        for clave in ("cuotas", "bajas_estructuradas", "alineaciones_probables", "clasificacion_oficial")
    )

    if profesional_predictivo and memoria_local and memoria_visitante:
        origen = "estadistica_equipos+datos_profesionales"
        calidad = "profesional"
    elif memoria_local and memoria_visitante:
        origen = "estadistica_equipos"
        calidad = "alta"
    elif profesional_predictivo:
        origen = "datos_profesionales_con_fallback"
        calidad = "media"
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
        "datos_profesionales": capas_profesionales,
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
    if partido.get("forzar_cobertura_motivacion") == "TRIPLE":
        score += 180
    elif partido.get("forzar_cobertura_motivacion") == "DOBLE":
        score += 85
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
    if partido.get("forzar_cobertura_motivacion") in {"DOBLE", "TRIPLE"}:
        score += 120
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
    datos_profesionales = cargar_json(DATOS_PROFESIONALES, {})
    contexto_competitivo = cargar_json(CONTEXTO_COMPETITIVO, {})
    patrones_competitivos = cargar_json(PATRONES_COMPETITIVOS, {})
    perfiles_autonomos = cargar_json(PERFILES_EQUIPOS, {})
    clasificaciones_mundial = cargar_json(CLASIFICACIONES_MUNDIAL, {})
    fuente_losilla = cargar_json(FUENTE_LOSILLA, {})
    fuente_lesiones_laliga = cargar_json(FUENTE_LESIONES_LALIGA, {})
    fuente_lesiones_respaldo = cargar_json(FUENTE_LESIONES_RESPALDO, {})
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
        datos_profesionales_partido = buscar_datos_profesionales_partido(datos_profesionales, jornada, partido)
        probs, riesgo_datos_profesionales, lecturas_datos_profesionales, resumen_profesional = ajustar_por_datos_profesionales(
            probs,
            datos_profesionales_partido,
        )
        lecturas_motivacion.extend(lecturas_datos_profesionales)
        # trazabilidad se calcula aqui (antes de ajustar_por_mercado_losilla,
        # no despues) porque su calidad_datos decide el peso que se le da al
        # mercado Losilla frente al prior propio del motor -con un prior de
        # "baja" calidad (fallback puro), el mercado debe pesar mucho mas que
        # con uno de "alta" calidad (estadistica real de ambos equipos).
        trazabilidad = trazabilidad_datos_partido(
            local,
            visitante,
            contexto_local,
            contexto_visitante,
            local_comp,
            visitante_comp,
            datos_profesionales_partido,
        )
        trazabilidad["modelo_entrenado"] = ajuste_modelo_entrenado
        if ajuste_modelo_entrenado.get("activo"):
            trazabilidad["origen_probabilidades"] = f"{trazabilidad['origen_probabilidades']}+modelo_entrenado"
        mercado_losilla_partido = mercado_losilla_signos(fuente_losilla, partido)
        probs, riesgo_mercado_losilla, lecturas_mercado_losilla = ajustar_por_mercado_losilla(
            probs, mercado_losilla_partido, calidad_datos=trazabilidad["calidad_datos"]
        )
        lecturas_motivacion.extend(lecturas_mercado_losilla)
        # jornadaperfecta.com es respaldo -solo se consulta cuando la
        # fuente principal (FutbolFantasy) no tiene datos de ese equipo
        # concreto (buscar_lesiones_equipo devuelve [] si no lo encuentra).
        lesiones_laliga_local = buscar_lesiones_equipo(fuente_lesiones_laliga, partido.get("local", "")) or \
            buscar_lesiones_equipo(fuente_lesiones_respaldo, partido.get("local", ""))
        lesiones_laliga_visitante = buscar_lesiones_equipo(fuente_lesiones_laliga, partido.get("visitante", "")) or \
            buscar_lesiones_equipo(fuente_lesiones_respaldo, partido.get("visitante", ""))
        probs, riesgo_lesiones_laliga, lecturas_lesiones_laliga = ajustar_por_lesiones_laliga(
            probs, lesiones_laliga_local, lesiones_laliga_visitante
        )
        lecturas_motivacion.extend(lecturas_lesiones_laliga)
        ajuste_motivacion_competitiva = calcular_ajuste_motivacion({**partido, "probabilidades": probs}, clasificaciones_mundial, fuente_losilla)
        probs = aplicar_ajuste_motivacion_competitiva(probs, ajuste_motivacion_competitiva)
        riesgo_motivacion_competitiva = 0.0
        if ajuste_motivacion_competitiva.get("activo"):
            riesgo_motivacion_competitiva = min(sum(abs(v) for v in ajuste_motivacion_competitiva.get("ajuste_por_signo", {}).values()), 35.0)
            lecturas_motivacion.extend(ajuste_motivacion_competitiva.get("lecturas", []))
        inc = incertidumbre(
            probs,
            local,
            visitante,
            diff,
            riesgo_contexto
            + riesgo_perfiles
            + riesgo_motivacion
            + riesgo_patrones
            + riesgo_aprendizaje
            + riesgo_pesos_dinamicos
            + riesgo_datos_profesionales
            + riesgo_mercado_losilla
            + riesgo_lesiones_laliga
            + riesgo_motivacion_competitiva,
        )
        sorpresa = probabilidad_sorpresa(probs, inc)
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
            "datos_profesionales": resumen_profesional,
            "ajuste_datos_profesionales": {
                "activo": bool(lecturas_datos_profesionales),
                "riesgo_extra": riesgo_datos_profesionales,
                "lecturas": lecturas_datos_profesionales,
            },
            "mercado_losilla": mercado_losilla_partido,
            "ajuste_mercado_losilla": {
                "activo": bool(lecturas_mercado_losilla),
                "riesgo_extra": riesgo_mercado_losilla,
                "lecturas": lecturas_mercado_losilla,
            },
            "lesiones_laliga_local": lesiones_laliga_local,
            "lesiones_laliga_visitante": lesiones_laliga_visitante,
            "ajuste_lesiones_laliga": {
                "activo": bool(lecturas_lesiones_laliga),
                "riesgo_extra": riesgo_lesiones_laliga,
                "lecturas": lecturas_lesiones_laliga,
            },
            "ajuste_motivacion": ajuste_motivacion_competitiva,
            "alertas_motivacion": ajuste_motivacion_competitiva.get("alertas", []),
            "sorpresa_potencial": bool(ajuste_motivacion_competitiva.get("sorpresa_potencial")),
            "nivel_sorpresa": ajuste_motivacion_competitiva.get("nivel_sorpresa", ""),
            "forzar_cobertura_motivacion": ajuste_motivacion_competitiva.get("forzar_cobertura", ""),
            "trazabilidad_datos": trazabilidad,
            "_local": local,
            "_visitante": visitante,
            "_diff": diff,
        }
        indice_sorpresa = indice_sorpresa_quinielistica(evaluado, patrones_competitivos)
        if ajuste_motivacion_competitiva.get("sorpresa_potencial"):
            indice_sorpresa["indice"] = max(float(indice_sorpresa.get("indice") or 0), 60.0)
            indice_sorpresa["categoria"] = "alta"
            indice_sorpresa["favorito_atacable"] = True
            indice_sorpresa["cobertura_sugerida"] = ajuste_motivacion_competitiva.get("forzar_cobertura") or "DOBLE"
            indice_sorpresa.setdefault("motivos", []).append("alerta motivacional con mercado Losilla superior al 80%")
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
            "datos_profesionales": partido["datos_profesionales"],
            "ajuste_datos_profesionales": partido["ajuste_datos_profesionales"],
            "mercado_losilla": partido["mercado_losilla"],
            "ajuste_mercado_losilla": partido["ajuste_mercado_losilla"],
            "lesiones_laliga_local": partido["lesiones_laliga_local"],
            "lesiones_laliga_visitante": partido["lesiones_laliga_visitante"],
            "ajuste_lesiones_laliga": partido["ajuste_lesiones_laliga"],
            "ajuste_motivacion": partido["ajuste_motivacion"],
            "alertas_motivacion": partido["alertas_motivacion"],
            "sorpresa_potencial": partido["sorpresa_potencial"],
            "nivel_sorpresa": partido["nivel_sorpresa"],
            "forzar_cobertura_motivacion": partido["forzar_cobertura_motivacion"],
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
    pleno15_base = data.get("pleno15") or {}
    ajuste_pleno15 = calcular_ajuste_motivacion({**pleno15_base, "num": 15, "probabilidades": {"1": 33.3, "X": 33.3, "2": 33.3}}, clasificaciones_mundial, fuente_losilla)
    pleno15_ajustado = ajustar_pleno15_motivacion(pleno15_base, fuente_losilla, ajuste_pleno15)
    resumen_profesional_boleto = {
        "estado_global": datos_profesionales.get("estado_global"),
        "temporada_objetivo": datos_profesionales.get("temporada_objetivo"),
        "generado_en": datos_profesionales.get("generado_en"),
        "resumen_fuente": datos_profesionales.get("resumen", {}),
        "partidos_con_cuotas": sum(
            1 for p in partidos if ((p.get("datos_profesionales") or {}).get("capas") or {}).get("cuotas")
        ),
        "partidos_con_bajas_estructuradas": sum(
            1
            for p in partidos
            if ((p.get("datos_profesionales") or {}).get("capas") or {}).get("bajas_estructuradas")
        ),
        "partidos_con_alineaciones": sum(
            1
            for p in partidos
            if ((p.get("datos_profesionales") or {}).get("capas") or {}).get("alineaciones_probables")
        ),
        "partidos_con_clasificacion_oficial": sum(
            1
            for p in partidos
            if ((p.get("datos_profesionales") or {}).get("capas") or {}).get("clasificacion_oficial")
        ),
    }

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
        "datos_profesionales": resumen_profesional_boleto,
        "pleno15": pleno15_ajustado,
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
