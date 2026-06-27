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
NO_JUGADA = {"NO JUGADA", "NO VALIDADA", "PENDIENTE", ""}


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


def resultado_normalizado(resultado):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(resultado or ""))
    if not m:
        return ""
    return f"{int(m.group(1))}-{int(m.group(2))}"


def signo_resultado(resultado):
    normalizado = resultado_normalizado(resultado)
    if not normalizado:
        return ""
    g1, g2 = [int(x) for x in normalizado.split("-")]
    return "1" if g1 > g2 else "X" if g1 == g2 else "2"


def signos_pronostico(valor):
    texto = str(valor or "").strip().upper()
    if texto in NO_JUGADA or resultado_normalizado(texto):
        return set()
    return {s for s in ("1", "X", "2") if s in texto}


def pronostico_valido(valor):
    texto = str(valor or "").strip().upper()
    return texto not in NO_JUGADA and bool(signos_pronostico(texto))


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


def margen(probs):
    vals = sorted((to_float(v) for v in probs.values()), reverse=True)
    return round(vals[0] - vals[1], 2) if len(vals) >= 2 else 0.0


def tercera_prob(probs):
    vals = sorted((to_float(v) for v in probs.values()), reverse=True)
    return round(vals[2], 2) if len(vals) >= 3 else 0.0


def categoria_sorpresa(score):
    return "sorpresa_alta" if score >= 75 else "sorpresa_vigilada" if score >= 55 else "riesgo_medio" if score >= 35 else "riesgo_bajo"


def aprendizaje(pron, tipo, real, ok):
    if ok:
        return [f"La quiniela jugada cubrio el signo real {real} con {tipo}."]
    if tipo == "FIJO":
        return ["Revisar fijos fallados y subir cobertura en perfiles parecidos."]
    return [f"Ampliar cobertura para incluir {real} en perfiles parecidos."]


def jornada_cerrada(data):
    partidos = data.get("partidos") or []
    return bool(partidos) and all(signo_oficial(p) in SIGNOS for p in partidos)


def construir_entrada(jornada, jornada_data, pred_data):
    pred_por_num = {int(p.get("num") or 0): p for p in pred_data.get("partidos", []) if str(p.get("num") or "").isdigit()}
    partidos = []
    aciertos = 0
    fallos = 0

    HISTORIAL = DATA / "historial_quinielas.json"
    historial = cargar_json(HISTORIAL, {})
    quiniela_jugada = ""
    for j in historial.get("jornadas", []):
        if int(j.get("jornada", 0)) == jornada:
            quiniela_jugada = str(j.get("nuestra_quiniela", "") or "").strip()
            break

    signos_jugados = quiniela_jugada.split() if quiniela_jugada and quiniela_jugada != "No validada" else []

    # Leer el pronóstico del Pleno al 15 (partido 15)
    pleno15_nuestro = ""
    for j in historial.get("jornadas", []):
        if int(j.get("jornada", 0)) == jornada:
            pleno15_nuestro = str(j.get("pleno15_nuestro") or j.get("pleno15_jugado") or "").strip()
            break

    # Añadir el pronóstico del pleno al final de signos_jugados
    # para que el partido 15 tenga su signo (índice 14)
    if pleno15_nuestro and pleno15_nuestro != "No jugada":
        signos_jugados.append(pleno15_nuestro)

    for partido in jornada_data.get("partidos", []):
        num = int(partido.get("num") or 0)
        pred = pred_por_num.get(num, {})
        real = signo_oficial(partido)
        idx_partido = num - 1
        pron = signos_jugados[idx_partido].upper().strip() if signos_jugados and 0 <= idx_partido < len(signos_jugados) else signo_prediccion(pred)
        if real not in SIGNOS or not pronostico_valido(pron):
            if pronostico_valido(pron) or pron:
                partidos.append(crear_item_pendiente(num, partido, pred, pron))
            continue

        tipo = tipo_pronostico(pron)
        ok = real in signos_pronostico(pron)
        probs = probabilidades(pred)
        fav = favorito(pred, probs)
        score = score_sorpresa(pred)
        margen_val = to_float(pred.get("margen_probabilidad"), margen(probs))
        tercera = to_float(pred.get("tercera_probabilidad"), tercera_prob(probs))
        aciertos += int(ok)
        fallos += int(not ok)
        partidos.append(crear_item_jugado(num, partido, pred, pron, tipo, real, ok, probs, fav, score, margen_val, tercera, bool(signos_jugados)))

    agregar_pleno15(partidos, jornada_data, pred_data, pleno15_nuestro)
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


def crear_item_jugado(num, partido, pred, pron, tipo, real, ok, probs, fav, score, margen_val, tercera, desde_historial):
    categoria = str(pred.get("categoria_sorpresa") or categoria_sorpresa(score))
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
        "explicacion": (f"Acierto con {tipo}" if ok else f"Fallo con {tipo}") + f": pronostico {pron}, signo real {real}.",
        "categoria_fallo": "acierto" if ok else "fallo",
        "ajuste_recomendado": "Mantener" if ok else f"Revisar cobertura para incluir {real}.",
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
        "aprendizaje": aprendizaje(pron, tipo, real, ok),
    }


def acierto_pleno15(pronostico, resultado_real, signo_real):
    pron = str(pronostico or "").strip().upper()
    resultado_pron = resultado_normalizado(pron)
    resultado_real_norm = resultado_normalizado(resultado_real)
    if resultado_pron and resultado_real_norm:
        return resultado_pron == resultado_real_norm
    if pronostico_valido(pron) and signo_real in SIGNOS:
        return signo_real in signos_pronostico(pron)
    return None


def agregar_pleno15(partidos, jornada_data, pred_data, pleno15_nuestro=""):
    pleno = jornada_data.get("pleno15") or {}
    if not pleno:
        return
    pleno_pred = next((p for p in pred_data.get("partidos", []) if int(p.get("num") or 0) == 15), {}) or pred_data.get("pleno15") or {}
    resultado_pleno = str(pleno.get("resultado") or "Pendiente")
    signo_pleno = signo_resultado(resultado_pleno) or normalizar_signo(pleno.get("signo_oficial")) or "Pendiente"
    local_pleno = pleno.get("local", "")
    visitante_pleno = pleno.get("visitante", "")
    pleno_historial_valido = str(pleno15_nuestro or "").strip().upper() not in NO_JUGADA
    pronostico_pleno = str(
        pleno15_nuestro if pleno_historial_valido else
        pleno_pred.get("signo_final") or pleno_pred.get("signo_base") or pleno_pred.get("pronostico_ia") or pleno.get("signo_nuestro") or "Pendiente"
    ).strip().upper()
    jugado_pleno = bool(resultado_normalizado(resultado_pleno)) and signo_pleno in SIGNOS
    ok_pleno = acierto_pleno15(pronostico_pleno, resultado_pleno, signo_pleno) if jugado_pleno else None
    explicacion = f"Pleno al 15: {local_pleno} vs {visitante_pleno}. "
    if jugado_pleno:
        explicacion += f"Resultado: {resultado_pleno}."
        if ok_pleno is True:
            explicacion += " Pronostico del Pleno al 15 acertado."
        elif ok_pleno is False:
            explicacion += " Pronostico del Pleno al 15 fallado."
    else:
        explicacion += "Partido pendiente de jugarse."
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
        "acierto": ok_pleno,
        "tipo_apuesta": "PLENO15",
        "es_elige8": False,
        "partido_sorpresa": False,
        "riesgo_necesidad": False,
        "calidad_datos": "alta" if jugado_pleno else "pendiente",
        "explicacion": explicacion,
        "categoria_fallo": "acierto" if ok_pleno is True else "fallo" if ok_pleno is False else "",
        "ajuste_recomendado": "",
        "origen": "historial_quinielas" if pleno_historial_valido else "jornada_data",
    })


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
