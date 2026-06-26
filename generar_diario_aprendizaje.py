"""Genera el diario de aprendizaje comparando resultados contra la quiniela real jugada."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
PREDICCIONES = DATA / "predicciones"
SALIDA = DATA / "memoria_ia" / "diario_aprendizaje.json"
SIGNOS = {"1", "X", "2"}


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ahora_iso():
    return datetime.now(timezone.utc).isoformat()


def numero_jornada(path):
    m = re.search(r"(\d+)", path.stem)
    return int(m.group(1)) if m else 0


def normalizar_signo(valor):
    signo = str(valor or "").strip().upper()
    return signo if signo in SIGNOS else ""


def signos_pronostico(valor):
    texto = str(valor or "").strip().upper()
    return {s for s in ("1", "X", "2") if s in texto}


def pronostico_valido(valor):
    return bool(signos_pronostico(valor)) and str(valor or "").strip().upper() not in {"NO JUGADA", "NO VALIDADA", "PENDIENTE"}


def signo_resultado(resultado):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(resultado or ""))
    if not m:
        return ""
    local, visitante = int(m.group(1)), int(m.group(2))
    return "1" if local > visitante else "X" if local == visitante else "2"


def signo_oficial(partido):
    return normalizar_signo(partido.get("signo_oficial")) or signo_resultado(partido.get("resultado"))


def tipo_pronostico(valor):
    total = len(signos_pronostico(valor))
    return "TRIPLE" if total >= 3 else "DOBLE" if total == 2 else "FIJO" if total == 1 else "NO_VALIDO"


def signo_prediccion(pred):
    for campo in ("signo_final", "signo_base", "signo", "pronostico_ia", "signo_recomendado"):
        valor = pred.get(campo)
        if pronostico_valido(valor):
            return str(valor).strip().upper()
    return ""


def to_float(valor, defecto=0.0):
    try:
        if valor in (None, ""):
            return defecto
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def probabilidades(pred):
    raw = pred.get("probabilidades") or {}
    return {s: to_float(raw.get(s), 0.0) for s in ("1", "X", "2")}


def favorito(pred, probs):
    fav = normalizar_signo(pred.get("favorito"))
    return fav or (max(probs, key=lambda s: probs.get(s, 0.0)) if probs else "")


def score_sorpresa(pred):
    for campo in ("surprise_score", "categoria_score", "indice_sorpresa_quinielistica", "probabilidad_sorpresa"):
        if campo in pred:
            return round(to_float(pred.get(campo), 0.0), 2)
    return 0.0


def categoria_sorpresa(pred, score):
    categoria = str(pred.get("categoria_sorpresa") or "").strip()
    if categoria:
        return categoria
    return "sorpresa_alta" if score >= 75 else "sorpresa_vigilada" if score >= 55 else "riesgo_medio" if score >= 35 else "riesgo_bajo"


def margen(probs):
    vals = sorted((to_float(v) for v in probs.values()), reverse=True)
    return round(vals[0] - vals[1], 2) if len(vals) >= 2 else 0.0


def tercera_prob(probs):
    vals = sorted((to_float(v) for v in probs.values()), reverse=True)
    return round(vals[2], 2) if len(vals) >= 3 else 0.0


def alertas_motivacion_diario(pred):
    ajuste = (pred or {}).get("ajuste_motivacion") or {}
    alertas = ajuste.get("alertas") or (pred or {}).get("alertas_motivacion") or []
    if isinstance(alertas, str):
        alertas = [alertas]
    return [str(a).strip() for a in alertas if str(a).strip()]


def explicacion_alerta(alertas):
    return "Alerta de motivacion detectada: " + ", ".join(alertas) + "." if alertas else "Revisar factores contextuales no capturados."


def explicar(pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera):
    cubiertos = signos_pronostico(pron)
    prob_cubierta = max((probs.get(s, 0.0) for s in cubiertos), default=0.0)
    partes = []
    if ok:
        partes.append(f"Acierto con {tipo}: la quiniela jugada cubrio el signo real {real}.")
    else:
        partes.append(f"Fallo con {tipo}: la quiniela jugada ({pron}) no cubrio el signo real {real}.")
    if fav and fav != real:
        partes.append(f"El favorito probabilistico era {fav}, pero salio {real}; fue una sorpresa contra favorito.")
    elif fav:
        partes.append(f"El resultado no contradijo al favorito probabilistico principal ({fav}).")
    partes.append(f"Score de sorpresa: {score} ({categoria}).")
    if margen_val < 12:
        partes.append(f"Margen corto entre signos ({margen_val} puntos).")
    if tercera >= 20 and tipo != "TRIPLE":
        partes.append(f"La tercera opcion tenia peso relevante ({tercera}%).")
    if prob_cubierta:
        partes.append(f"Mejor probabilidad cubierta por lo jugado: {round(prob_cubierta, 2)}%.")
    return " ".join(partes)


def explicacion_especifica(partido, pred, pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera):
    prefijo = "[ALERTA SORPRESA ACTIVA] " if pred.get("sorpresa_potencial") is True else ""
    if not ok and tipo == "FIJO":
        return prefijo + "Fijo fallado en la quiniela real jugada. " + explicacion_alerta(alertas_motivacion_diario(pred))
    if not ok and tipo in {"DOBLE", "TRIPLE"} and real not in signos_pronostico(pron):
        return prefijo + f"Cobertura insuficiente en la quiniela real jugada: {pron}. El signo real fue {real}."
    return prefijo + explicar(pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera)


def ajuste_recomendado_especifico(partido, pred, pron, tipo, real, ok, probs, fav, score, margen_val, tercera):
    if ok:
        return "Mantener como muestra positiva: la quiniela real jugada cubrio el signo oficial."
    if tipo == "FIJO":
        return "Revisar fijos fallados y subir cobertura cuando haya margen corto, alerta o sorpresa potencial."
    if real not in signos_pronostico(pron):
        return f"Ampliar cobertura para incluir {real} en perfiles similares."
    return "Mantener el caso como muestra calibrada sin ajuste fuerte adicional."


def aprendizaje(pron, tipo, real, ok, fav, score, margen_val, tercera):
    aprende = []
    if not ok and tipo == "FIJO":
        aprende.append("Rebajar confianza en fijos cuando el margen sea corto o el score de sorpresa sea alto.")
    elif not ok and tipo == "DOBLE":
        aprende.append("Elevar a TRIPLE partidos donde la tercera via tenga peso suficiente.")
    elif ok and tipo == "TRIPLE":
        aprende.append("Mantener TRIPLE en escenarios de incertidumbre alta: la cobertura amplia funciono.")
    elif ok and tipo == "DOBLE":
        aprende.append("Reforzar DOBLE en partidos de riesgo medio cuando la alternativa cubierta tenga sustento.")
    elif ok and tipo == "FIJO":
        aprende.append("Mantener FIJO si la ventaja probabilistica es clara y no hay alerta fuerte de sorpresa.")
    if fav and fav != real:
        aprende.append("Penalizar favoritos atacables en perfiles similares y subir cobertura contra favorito.")
    if score >= 70 and tipo == "FIJO":
        aprende.append("No tratar como fijo tranquilo un partido con score de sorpresa alto.")
    if margen_val < 12:
        aprende.append("En margenes cortos, exigir mas cobertura salvo senales externas muy solidas.")
    if tercera >= 20 and tipo != "TRIPLE":
        aprende.append("Reservar triples cuando la tercera opcion tenga peso medio o alto.")
    return aprende or ["Caso sin sesgo fuerte: mantener como muestra para calibracion acumulada."]


def jornada_cerrada(data):
    partidos = data.get("partidos") or []
    return bool(partidos) and all(signo_oficial(p) in SIGNOS for p in partidos)


def construir_entrada(jornada, jornada_data, pred_data):
    pred_por_num = {int(p.get("num") or 0): p for p in pred_data.get("partidos", []) if str(p.get("num") or "").isdigit()}
    partidos = []
    aciertos = 0
    fallos = 0

    # Cargar quiniela real jugada desde historial
    HISTORIAL = DATA / "historial_quinielas.json"
    historial = cargar_json(HISTORIAL, {})
    quiniela_jugada = ""
    pleno15_jugado = ""
    for j in historial.get("jornadas", []):
        if int(j.get("jornada", 0)) == jornada:
            quiniela_jugada = str(j.get("nuestra_quiniela", "") or "").strip()
            pleno15_jugado = str(j.get("pleno15_nuestro", "") or "").strip()
            break

    # Parsear la quiniela jugada en lista de signos por posición
    # Formato: "1X 2 X2 X2 2 12 1 1X 2 2 1X X 1X 2" (separado por espacios)
    signos_jugados = quiniela_jugada.split() if quiniela_jugada and quiniela_jugada != "No validada" else []

    for partido in jornada_data.get("partidos", []):
        num = int(partido.get("num") or 0)
        pred = pred_por_num.get(num, {})
        real = signo_oficial(partido)

        # Usar la quiniela real jugada si está disponible
        idx_partido = num - 1  # num es 1-based
        if signos_jugados and 0 <= idx_partido < len(signos_jugados):
            pron = signos_jugados[idx_partido].upper().strip()
        else:
            pron = signo_prediccion(pred)

        jugado = real in SIGNOS and pronostico_valido(pron)
        if not jugado:
            if pronostico_valido(pron) or pron:
                partidos.append(crear_item_pendiente(num, partido, pred, pron))
            continue

        tipo = tipo_pronostico(pron)
        ok = real in signos_pronostico(pron)
        probs = probabilidades(pred)
        fav = favorito(pred, probs)
        score = score_sorpresa(pred)
        categoria = categoria_sorpresa(pred, score)
        margen_val = to_float(pred.get("margen_probabilidad"), margen(probs))
        tercera = to_float(pred.get("tercera_probabilidad"), tercera_prob(probs))
        aciertos += int(ok)
        fallos += int(not ok)
        partidos.append(crear_item_jugado(num, partido, pred, pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera, bool(signos_jugados)))

    agregar_pleno15(partidos, jornada_data, pred_data, pleno15_jugado)
    partidos = sorted(partidos, key=lambda p: p.get("num", 99))
    return {
        "jornada": jornada,
        "actualizado_en": ahora_iso(),
        "origen_prediccion": str(PREDICCIONES / f"jornada_{jornada}.json"),
        "resumen": {
            "partidos": len(partidos),
            "aciertos": aciertos,
            "fallos": fallos,
            "precision": round(aciertos / max(aciertos + fallos, 1) * 100, 2),
        },
        "partidos": partidos,
    }


def crear_item_pendiente(num, partido, pred, pron):
    return {
        "num": num,
        "partido": f"{num}. {partido.get('local', '')} - {partido.get('visitante', '')}",
        "local": partido.get("local"),
        "visitante": partido.get("visitante"),
        "fecha": str(partido.get("fecha") or ""),
        "hora": str(partido.get("hora") or ""),
        "es_pleno15": False,
        "pronostico_jugado": pron if pron else "Pendiente",
        "signo_real": None,
        "resultado": "Pendiente",
        "acierto": None,
        "tipo_apuesta": tipo_pronostico(pron) if pron else "-",
        "es_elige8": bool(pred.get("en_elige8") or pred.get("elige8")),
        "partido_sorpresa": False,
        "riesgo_necesidad": False,
        "calidad_datos": "pendiente",
        "explicacion": "Partido pendiente de jugarse.",
        "categoria_fallo": "",
        "ajuste_recomendado": "",
        "origen": "pendiente",
    }


def crear_item_jugado(num, partido, pred, pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera, desde_historial):
    return {
        "num": num,
        "partido": f"{num}. {partido.get('local', '')} - {partido.get('visitante', '')}",
        "local": partido.get("local"),
        "visitante": partido.get("visitante"),
        "fecha": str(partido.get("fecha") or ""),
        "hora": str(partido.get("hora") or ""),
        "es_pleno15": False,
        "pronostico_jugado": pron,
        "signo_real": real,
        "resultado": partido.get("resultado") or "",
        "acierto": ok,
        "tipo_apuesta": tipo,
        "es_elige8": bool(pred.get("en_elige8") or pred.get("elige8")),
        "partido_sorpresa": bool(pred.get("sorpresa_potencial")),
        "riesgo_necesidad": bool(pred.get("riesgo_necesidad")),
        "calidad_datos": str(pred.get("calidad_datos") or "alta"),
        "explicacion": explicacion_especifica(partido, pred, pron, tipo, real, ok, probs, fav, score_sorpresa(pred), categoria, margen_val, tercera),
        "categoria_fallo": "acierto" if ok else "fallo",
        "ajuste_recomendado": ajuste_recomendado_especifico(partido, pred, pron, tipo, real, ok, probs, fav, score, margen_val, tercera),
        "origen": "historial_quinielas" if desde_historial else "generar_diario_aprendizaje",
        "prediccion": {
            "signo_final": pron,
            "tipo": tipo,
            "probabilidades": probs,
            "surprise_score": score,
            "categoria_sorpresa": categoria,
            "favorito": fav,
            "margen_probabilidad": margen_val,
            "tercera_probabilidad": tercera,
        },
        "resultado_real": {"signo_oficial": real, "resultado": partido.get("resultado")},
        "acertado": ok,
        "aprendizaje": aprendizaje(pron, tipo, real, ok, fav, score, margen_val, tercera),
    }


def agregar_pleno15(partidos, jornada_data, pred_data, pleno15_jugado=""):
    pleno = jornada_data.get("pleno15") or {}
    if not pleno:
        return
    pleno_pred = next((p for p in pred_data.get("partidos", []) if int(p.get("num") or 0) == 15), {}) or pred_data.get("pleno15") or {}
    resultado_pleno = str(pleno.get("resultado") or "Pendiente")
    signo_pleno = str(pleno.get("signo_oficial") or "Pendiente")
    local_pleno = pleno.get("local", "")
    visitante_pleno = pleno.get("visitante", "")
    pronostico_pleno = str(
        pleno15_jugado if pleno15_jugado and pleno15_jugado != "No validada" else
        pleno_pred.get("signo_final") or pleno_pred.get("signo_base") or pleno_pred.get("pronostico_ia") or pleno.get("signo_nuestro") or "Pendiente"
    )
    jugado_pleno = "-" in resultado_pleno and signo_pleno in SIGNOS
    partidos.append({
        "num": 15,
        "partido": f"PLENO AL 15: {local_pleno} - {visitante_pleno}",
        "local": local_pleno,
        "visitante": visitante_pleno,
        "fecha": str(pleno.get("fecha") or ""),
        "hora": str(pleno.get("hora") or ""),
        "es_pleno15": True,
        "pronostico_jugado": pronostico_pleno,
        "signo_real": signo_pleno if jugado_pleno else None,
        "resultado": resultado_pleno if jugado_pleno else "Pendiente",
        "acierto": None,
        "tipo_apuesta": "PLENO15",
        "es_elige8": False,
        "partido_sorpresa": False,
        "riesgo_necesidad": False,
        "calidad_datos": "alta" if jugado_pleno else "pendiente",
        "explicacion": f"Pleno al 15: {local_pleno} vs {visitante_pleno}. " + (f"Resultado: {resultado_pleno}" if jugado_pleno else "Partido pendiente de jugarse."),
        "categoria_fallo": "",
        "ajuste_recomendado": "",
        "origen": "historial_quinielas" if pleno15_jugado and pleno15_jugado != "No validada" else "jornada_data",
    })


def comparable(entry):
    clean = dict(entry or {})
    clean.pop("actualizado_en", None)
    return clean


def actualizar_diario():
    diario = cargar_json(SALIDA, {"version": "1.0", "entradas": []})
    entradas_previas = [e for e in diario.get("entradas", []) if str(e.get("jornada") or "") != "70"]
    jornadas = []
    nuevas_entradas = []
    for path in sorted(JORNADAS.glob("jornada_*.json"), key=numero_jornada):
        jornada = numero_jornada(path)
        jornada_data = cargar_json(path, {})
        pred_data = cargar_json(PREDICCIONES / f"jornada_{jornada}.json", {})
        if not pred_data.get("partidos"):
            continue
        if not jornada_cerrada(jornada_data) and jornada != 70:
            continue
        entrada = construir_entrada(jornada, jornada_data, pred_data)
        if not entrada["partidos"]:
            continue
        jornadas.append(entrada)
        for partido in entrada["partidos"]:
            item = dict(partido)
            item["jornada"] = jornada
            nuevas_entradas.append(item)
    entradas_por_clave = {}
    for item in entradas_previas + nuevas_entradas:
        clave = (int(item.get("jornada") or 0), int(item.get("num") or 0) or 99, item.get("partido") or "")
        entradas_por_clave[clave] = item
    entradas = [entradas_por_clave[k] for k in sorted(entradas_por_clave)]
    salida = {
        "version": "1.0",
        "generado_en": ahora_iso(),
        "actualizado_en": ahora_iso(),
        "total_entradas": len(entradas),
        "entradas": entradas,
        "jornadas": jornadas,
    }
    guardar_json(SALIDA, salida)
    print(f"Diario de aprendizaje actualizado: {len(jornadas)} jornada(s), {len(entradas)} entrada(s).")
    return len(jornadas)


if __name__ == "__main__":
    actualizar_diario()
