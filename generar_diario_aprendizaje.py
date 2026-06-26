"""Genera el diario de aprendizaje por jornada cerrada.

Lee data/jornadas/jornada_X.json y data/predicciones/jornada_X.json.
Cuando todos los partidos tienen signo_oficial valido, compara la prediccion
con el resultado real y actualiza data/memoria_ia/diario_aprendizaje.json.

No usa API externa: todo el razonamiento sale de probabilidades, tipo de
cobertura, surprise_score/categoria_sorpresa y resultado final.
"""

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
    return bool(signos_pronostico(valor)) and str(valor or "").strip().upper() not in {
        "NO JUGADA", "NO VALIDADA", "PENDIENTE"
    }


def signo_resultado(resultado):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(resultado or ""))
    if not m:
        return ""
    local, visitante = int(m.group(1)), int(m.group(2))
    if local > visitante:
        return "1"
    if local == visitante:
        return "X"
    return "2"


def signo_oficial(partido):
    return normalizar_signo(partido.get("signo_oficial")) or signo_resultado(partido.get("resultado"))


def tipo_pronostico(valor):
    total = len(signos_pronostico(valor))
    if total >= 3:
        return "TRIPLE"
    if total == 2:
        return "DOBLE"
    if total == 1:
        return "FIJO"
    return "NO_VALIDO"


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
    if fav:
        return fav
    if not probs:
        return ""
    return max(probs, key=lambda s: probs.get(s, 0.0))


def score_sorpresa(pred):
    for campo in ("surprise_score", "categoria_score", "indice_sorpresa_quinielistica", "probabilidad_sorpresa"):
        if campo in pred:
            return round(to_float(pred.get(campo), 0.0), 2)
    return 0.0


def categoria_sorpresa(pred, score):
    categoria = str(pred.get("categoria_sorpresa") or "").strip()
    if categoria:
        return categoria
    if score >= 75:
        return "sorpresa_alta"
    if score >= 55:
        return "sorpresa_vigilada"
    if score >= 35:
        return "riesgo_medio"
    return "riesgo_bajo"


def margen(probs):
    vals = sorted((to_float(v) for v in probs.values()), reverse=True)
    return round(vals[0] - vals[1], 2) if len(vals) >= 2 else 0.0


def tercera_prob(probs):
    vals = sorted((to_float(v) for v in probs.values()), reverse=True)
    return round(vals[2], 2) if len(vals) >= 3 else 0.0



def nombre_equipo_por_signo(partido, signo):
    if signo == "1":
        return partido.get("local") or "Local"
    if signo == "2":
        return partido.get("visitante") or "Visitante"
    return "Empate"


def alertas_motivacion_diario(pred):
    ajuste = (pred or {}).get("ajuste_motivacion") or {}
    alertas = ajuste.get("alertas") or (pred or {}).get("alertas_motivacion") or []
    if isinstance(alertas, str):
        alertas = [alertas]
    return [str(a).strip() for a in alertas if str(a).strip()]


def explicacion_alerta(alertas):
    if not alertas:
        return "Revisar factores contextuales no capturados."
    return "Alerta de motivacion detectada: " + ", ".join(alertas) + "."


def explicacion_especifica(partido, pred, pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera):
    cubiertos = signos_pronostico(pron)
    fav_prob = round(to_float(probs.get(fav), 0.0), 1) if fav else 0.0
    real_prob = round(to_float(probs.get(real), 0.0), 1)
    fav_nombre = nombre_equipo_por_signo(partido, fav)
    alertas = alertas_motivacion_diario(pred)
    prefijo = "[ALERTA SORPRESA ACTIVA] " if pred.get("sorpresa_potencial") is True else ""

    if ok and tipo == "FIJO" and fav_prob > 65:
        return prefijo + f"Pronostico solido confirmado. {fav_nombre} era favorito claro con {fav_prob}% y cumplio."
    if ok and real_prob < 40:
        return prefijo + f"Sorpresa acertada. El mercado daba {fav_prob}% al favorito pero detectamos factores de riesgo. Reforzar este patron."
    if not ok and tipo == "FIJO":
        return prefijo + f"Fijo fallado. {fav_nombre} tenia {fav_prob}% pero no gano. {explicacion_alerta(alertas)}"
    if not ok and tipo in {"DOBLE", "TRIPLE"} and real not in cubiertos:
        cubiertos_txt = "".join(s for s in ("1", "X", "2") if s in cubiertos) or pron
        return prefijo + f"Cobertura insuficiente. El signo {real} no estaba en nuestra cobertura {cubiertos_txt}. Considerar ampliar cobertura en situaciones similares."
    return prefijo + explicar(pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera)


def ajuste_recomendado_especifico(partido, pred, pron, tipo, real, ok, probs, fav, score, margen_val, tercera):
    cubiertos = signos_pronostico(pron)
    fav_prob = round(to_float(probs.get(fav), 0.0), 1) if fav else 0.0
    real_prob = round(to_float(probs.get(real), 0.0), 1)
    alertas = alertas_motivacion_diario(pred)
    if ok and tipo == "FIJO" and fav_prob > 65:
        return "Mantener fijo limpio cuando el favorito supere 65% y no existan alertas fuertes de motivacion."
    if ok and real_prob < 40:
        return "Reforzar patron de sorpresa acertada: subir cobertura cuando el signo ganador tenga menos del 40% pero haya riesgo contextual."
    if not ok and tipo == "FIJO":
        if alertas:
            return "No dejar como FIJO partidos con alerta de motivacion activa; subir minimo a DOBLE si el mercado esta sesgado."
        return "Revisar variables contextuales no capturadas y rebajar umbral de confianza del fijo en perfiles similares."
    if not ok and tipo in {"DOBLE", "TRIPLE"} and real not in cubiertos:
        return f"Ampliar cobertura para incluir {real} cuando el tercer signo conserve valor o haya sorpresa_potencial."
    if pred.get("sorpresa_potencial") is True:
        return "Mantener alerta sorpresa activa y validar si la cobertura elegida fue suficiente."
    if score >= 60:
        return "Elevar cobertura en partidos con indice de sorpresa igual o superior a 60."
    return "Mantener el caso como muestra calibrada sin ajuste fuerte adicional."

def explicar(pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera):
    cubiertos = signos_pronostico(pron)
    prob_cubierta = max((probs.get(s, 0.0) for s in cubiertos), default=0.0)
    favorito_perdio = bool(fav and fav != real)
    partes = []

    if ok and tipo == "TRIPLE":
        partes.append("Acierto con TRIPLE: la incertidumbre estaba bien gestionada porque se cubrieron los tres desenlaces.")
    elif ok and tipo == "DOBLE":
        partes.append("Acierto con DOBLE: la cobertura elegida protegió el signo real en un partido con riesgo.")
    elif ok and tipo == "FIJO":
        partes.append("Acierto con FIJO: la confianza principal fue suficiente y el signo previsto coincidió con el resultado.")
    elif not ok and tipo == "FIJO":
        partes.append("Fallo con FIJO: hubo demasiada confianza en un solo signo y no se cubrió la alternativa real.")
    elif not ok and tipo == "DOBLE":
        partes.append("Fallo con DOBLE: la cobertura fue insuficiente; el tercer signo seguía vivo y acabó saliendo.")
    else:
        partes.append("Fallo con cobertura amplia: revisar coherencia entre tipo, signo final y resultado oficial.")

    if favorito_perdio:
        partes.append(f"El favorito probabilístico era {fav}, pero salió {real}; fue una sorpresa contra favorito.")
    elif fav:
        partes.append(f"El resultado no contradijo al favorito probabilístico principal ({fav}).")

    if score >= 70:
        partes.append(f"El score de sorpresa era alto ({score}, {categoria}), señal de prudencia y cobertura.")
    elif score >= 50:
        partes.append(f"El score de sorpresa era medio/alto ({score}, {categoria}), con riesgo que debía vigilarse.")
    else:
        partes.append(f"El score de sorpresa era bajo o moderado ({score}, {categoria}).")

    if margen_val < 12:
        partes.append(f"El margen entre signos era corto ({margen_val} puntos), por lo que el partido era abierto.")
    if tercera >= 20 and tipo != "TRIPLE":
        partes.append(f"La tercera opción tenía peso relevante ({tercera}%), lo que justificaba valorar TRIPLE.")
    if prob_cubierta:
        partes.append(f"La mejor probabilidad cubierta por nuestra predicción era {round(prob_cubierta, 2)}%.")
    return " ".join(partes)


def aprendizaje(pron, tipo, real, ok, fav, score, margen_val, tercera):
    aprende = []
    favorito_perdio = bool(fav and fav != real)

    if not ok and tipo == "FIJO":
        aprende.append("Rebajar confianza en fijos cuando el margen sea corto o el score de sorpresa sea alto.")
        if real == "X" and "X" not in signos_pronostico(pron):
            aprende.append("Subir peso del empate en partidos equilibrados que quedaron sin X cubierta.")
    elif not ok and tipo == "DOBLE":
        aprende.append("Elevar a TRIPLE partidos donde la tercera vía tenga peso suficiente.")
    elif ok and tipo == "TRIPLE":
        aprende.append("Mantener TRIPLE en escenarios de incertidumbre alta: la cobertura amplia funcionó.")
    elif ok and tipo == "DOBLE":
        aprende.append("Reforzar DOBLE en partidos de riesgo medio cuando la alternativa cubierta tenga sustento.")
    elif ok and tipo == "FIJO":
        aprende.append("Mantener FIJO si la ventaja probabilística es clara y no hay alerta fuerte de sorpresa.")

    if favorito_perdio:
        aprende.append("Penalizar favoritos atacables en perfiles similares y subir cobertura contra favorito.")
    if score >= 70 and tipo == "FIJO":
        aprende.append("No tratar como fijo tranquilo un partido con score de sorpresa alto.")
    if margen_val < 12:
        aprende.append("En márgenes cortos, exigir más cobertura salvo señales externas muy sólidas.")
    if tercera >= 20 and tipo != "TRIPLE":
        aprende.append("Reservar triples cuando la tercera opción tenga peso medio o alto.")

    return aprende or ["Caso sin sesgo fuerte: mantener como muestra para calibración acumulada."]


def jornada_cerrada(data):
    partidos = data.get("partidos") or []
    return bool(partidos) and all(signo_oficial(p) in SIGNOS for p in partidos)


def construir_entrada(jornada, jornada_data, pred_data):
    pred_por_num = {int(p.get("num") or 0): p for p in pred_data.get("partidos", []) if str(p.get("num") or "").isdigit()}
    partidos = []
    aciertos = 0
    fallos = 0

    for partido in jornada_data.get("partidos", []):
        num = int(partido.get("num") or 0)
        pred = pred_por_num.get(num, {})
        real = signo_oficial(partido)
        pron = signo_prediccion(pred)
        jugado = real in SIGNOS and pronostico_valido(pron)
        
        if not jugado:
            # Partido pendiente: incluirlo sin resultado
            if pronostico_valido(pron) or pron:
                partidos.append({
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
                    "tipo_apuesta": str(pred.get("tipo") or tipo_pronostico(pron)).upper() if pron else "-",
                    "es_elige8": bool(pred.get("en_elige8") or pred.get("elige8")),
                    "partido_sorpresa": False,
                    "riesgo_necesidad": False,
                    "calidad_datos": "pendiente",
                    "explicacion": "Partido pendiente de jugarse.",
                    "categoria_fallo": "",
                    "ajuste_recomendado": "",
                    "origen": "pendiente",
                })
            continue

        tipo = str(pred.get("tipo") or tipo_pronostico(pron)).upper()
        ok = real in signos_pronostico(pron)
        probs = probabilidades(pred)
        fav = favorito(pred, probs)
        score = score_sorpresa(pred)
        categoria = categoria_sorpresa(pred, score)
        margen_val = to_float(pred.get("margen_probabilidad"), margen(probs))
        tercera = to_float(pred.get("tercera_probabilidad"), tercera_prob(probs))
        aciertos += int(ok)
        fallos += int(not ok)
        explicacion = explicacion_especifica(partido, pred, pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera)
        ajuste = ajuste_recomendado_especifico(partido, pred, pron, tipo, real, ok, probs, fav, score, margen_val, tercera)
        partidos.append({
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
            "explicacion": explicacion,
            "categoria_fallo": "acierto" if ok else "fallo",
            "ajuste_recomendado": ajuste,
            "origen": "generar_diario_aprendizaje",
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
            "resultado_real": {
                "signo_oficial": real,
                "resultado": partido.get("resultado"),
            },
            "acertado": ok,
            "aprendizaje": aprendizaje(pron, tipo, real, ok, fav, score, margen_val, tercera),
        })

    # Procesar Pleno al 15
    pleno = jornada_data.get("pleno15") or {}
    pleno_pred = {}
    for p_pred in pred_data.get("partidos", []):
        if int(p_pred.get("num") or 0) == 15:
            pleno_pred = p_pred
            break
    if not pleno_pred and pred_data.get("pleno15"):
        pleno_pred = pred_data["pleno15"]

    if pleno:
        resultado_pleno = str(pleno.get("resultado") or "Pendiente")
        signo_pleno = str(pleno.get("signo_oficial") or "Pendiente")
        local_pleno = pleno.get("local", "")
        visitante_pleno = pleno.get("visitante", "")
        fecha_pleno = str(pleno.get("fecha") or "")
        hora_pleno = str(pleno.get("hora") or "")
        pronostico_pleno = str(
            pleno_pred.get("signo_final") or
            pleno_pred.get("signo_base") or
            pleno_pred.get("pronostico_ia") or
            pleno.get("signo_nuestro") or
            "Pendiente"
        )
        jugado_pleno = "-" in resultado_pleno and signo_pleno in SIGNOS
        partidos.append({
            "num": 15,
            "partido": f"PLENO AL 15: {local_pleno} - {visitante_pleno}",
            "local": local_pleno,
            "visitante": visitante_pleno,
            "fecha": fecha_pleno,
            "hora": hora_pleno,
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
            "origen": "jornada_data",
        })

    partidos = sorted(partidos, key=lambda p: p.get("num", 99))

    total = len(partidos)
    return {
        "jornada": jornada,
        "actualizado_en": ahora_iso(),
        "origen_prediccion": str(PREDICCIONES / f"jornada_{jornada}.json"),
        "resumen": {
            "partidos": total,
            "aciertos": aciertos,
            "fallos": fallos,
            "precision": round(aciertos / max(aciertos + fallos, 1) * 100, 2),
        },
        "partidos": partidos,
    }


def comparable(entry):
    clean = dict(entry or {})
    clean.pop("actualizado_en", None)
    return clean


def actualizar_diario():
    diario = cargar_json(SALIDA, {"version": "1.0", "entradas": []})
    entradas_previas = [
        e for e in diario.get("entradas", [])
        if str(e.get("jornada") or "") != "70"
    ]
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
