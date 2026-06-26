# trigger workflow after workflow file exists
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_file(path, patcher):
    text = path.read_text(encoding="utf-8")
    new_text = patcher(text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        print(f"PATCHED {path.relative_to(ROOT)}")
    else:
        print(f"UNCHANGED {path.relative_to(ROOT)}")


def patch_actualizar(text):
    if "SORPRESAS_MERCADO" not in text:
        text = text.replace(
            'HISTORIAL_PREMIOS = DATA / "premios" / "historial_premios.json"\n',
            'HISTORIAL_PREMIOS = DATA / "premios" / "historial_premios.json"\n'
            'FUENTE_LOSILLA = DATA / "memoria_ia" / "fuente_losilla.json"\n'
            'SORPRESAS_MERCADO = DATA / "memoria_ia" / "sorpresas_mercado.json"\n',
        )

    if "def registrar_sorpresas_mercado" not in text:
        helper = r'''

def mercado_partido_losilla(fuente_losilla, numero_partido):
    partidos = (((fuente_losilla or {}).get("probabilidades") or {}).get("partidos") or [])
    for item in partidos:
        try:
            if int(item.get("numero") or 0) == int(numero_partido):
                signos = item.get("probabilidades_signo") or {}
                valores = {
                    "1": float(signos.get("1") if signos.get("1") is not None else item.get("probabilidad_1") or 0),
                    "X": float(signos.get("X") if signos.get("X") is not None else item.get("probabilidad_X") or 0),
                    "2": float(signos.get("2") if signos.get("2") is not None else item.get("probabilidad_2") or 0),
                }
                favorito = max(valores, key=lambda signo: valores.get(signo, 0.0))
                return favorito, valores[favorito], valores
        except Exception:
            continue
    return "", 0.0, {}


def alertas_motivacion_prediccion(prediccion):
    ajuste = (prediccion or {}).get("ajuste_motivacion") or {}
    alertas = ajuste.get("alertas") or (prediccion or {}).get("alertas_motivacion") or []
    if isinstance(alertas, str):
        alertas = [alertas]
    return [str(a).strip() for a in alertas if str(a).strip()]


def categoria_sorpresa_mercado(prediccion):
    alertas = alertas_motivacion_prediccion(prediccion)
    if "derbi_todo_puede_pasar" in alertas:
        return "derbi"
    if any(a in alertas for a in ("equipo_sin_objetivos", "ambos_clasificados_sin_tension")):
        return "partido_sin_presion"
    if alertas:
        return "motivacion_competitiva"
    texto = json.dumps(prediccion or {}, ensure_ascii=False).lower()
    if "racha" in texto or "racha_rota" in texto:
        return "racha_rota"
    return "desconocido"


def inicializar_sorpresas_mercado():
    if not SORPRESAS_MERCADO.exists():
        guardar_json(SORPRESAS_MERCADO, {"version": "1.0", "sorpresas": []})


def registrar_sorpresas_mercado(jornada_num, jornada_data, pred_info):
    fuente_losilla = cargar_json(FUENTE_LOSILLA, {})
    memoria = cargar_json(SORPRESAS_MERCADO, {"version": "1.0", "sorpresas": []})
    sorpresas = memoria.setdefault("sorpresas", [])
    existentes = {
        (
            int(item.get("jornada") or 0),
            int(item.get("numero_partido") or 0),
            str(item.get("signo_favorito_mercado") or ""),
            str(item.get("signo_real") or ""),
        )
        for item in sorpresas
        if str(item.get("jornada") or "").isdigit() and str(item.get("numero_partido") or "").isdigit()
    }
    pred_por_num = (pred_info or {}).get("partidos") or {}
    nuevas = 0
    for partido in jornada_data.get("partidos", []):
        num = partido.get("num")
        if not str(num or "").isdigit():
            continue
        num = int(num)
        real = signo_oficial_partido(partido)
        if real not in SIGNOS_VALIDOS:
            continue
        signo_fav, prob_fav, mercado = mercado_partido_losilla(fuente_losilla, num)
        if not signo_fav or prob_fav <= 75.0 or signo_fav == real:
            continue
        prediccion = pred_por_num.get(num, {})
        alertas = alertas_motivacion_prediccion(prediccion)
        clave = (int(jornada_num), num, signo_fav, real)
        if clave in existentes:
            continue
        entrada = {
            "jornada": int(jornada_num),
            "numero_partido": num,
            "local": partido.get("local"),
            "visitante": partido.get("visitante"),
            "probabilidad_mercado_favorito": round(float(prob_fav), 2),
            "signo_favorito_mercado": signo_fav,
            "signo_real": real,
            "alerta_motivacion_detectada": alertas[0] if alertas else "",
            "alertas_motivacion_detectadas": alertas,
            "categoria_sorpresa": categoria_sorpresa_mercado(prediccion),
            "fecha": partido.get("fecha") or ahora_iso(),
            "mercado_losilla": mercado,
            "origen_prediccion": str((pred_info or {}).get("path") or ""),
        }
        sorpresas.append(entrada)
        existentes.add(clave)
        nuevas += 1
    if nuevas or not SORPRESAS_MERCADO.exists():
        memoria["actualizado_en"] = ahora_iso()
        memoria["total_sorpresas"] = len(sorpresas)
        guardar_json(SORPRESAS_MERCADO, memoria)
    return nuevas
'''
        text = text.replace('\ndef construir_salida(resumen, fuentes_jugadas):', helper + '\ndef construir_salida(resumen, fuentes_jugadas):')

    if "inicializar_sorpresas_mercado()" not in text:
        text = text.replace(
            '    registros_premios = {}\n    jornadas_cerradas_actualizadas = 0\n',
            '    registros_premios = {}\n    jornadas_cerradas_actualizadas = 0\n    inicializar_sorpresas_mercado()\n',
        )

    if "registrar_sorpresas_mercado(int(jornada_num)" not in text:
        text = text.replace(
            '        if comparacion_cierre:\n            registros_premios[int(jornada_num)] = construir_registro_premios(int(jornada_num), pred_info, comparacion_cierre)\n            jornadas_cerradas_actualizadas += 1\n            data = cargar_json(path, data)\n',
            '        if comparacion_cierre:\n            registros_premios[int(jornada_num)] = construir_registro_premios(int(jornada_num), pred_info, comparacion_cierre)\n            registrar_sorpresas_mercado(int(jornada_num), data, pred_info)\n            jornadas_cerradas_actualizadas += 1\n            data = cargar_json(path, data)\n',
        )
    return text


def patch_motor(text):
    if "SORPRESAS_MERCADO = DATA / \"memoria_ia\" / \"sorpresas_mercado.json\"" not in text:
        text = text.replace(
            'FUENTE_LOSILLA = DATA / "memoria_ia" / "fuente_losilla.json"\n',
            'FUENTE_LOSILLA = DATA / "memoria_ia" / "fuente_losilla.json"\n'
            'SORPRESAS_MERCADO = DATA / "memoria_ia" / "sorpresas_mercado.json"\n',
        )

    if "def reforzar_ajuste_por_memoria_sorpresas" not in text:
        helper = r'''

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
'''
        text = text.replace('\ndef aplicar_ajuste_motivacion_competitiva(probs, ajuste):', helper + '\ndef aplicar_ajuste_motivacion_competitiva(probs, ajuste):')

    if "reforzar_ajuste_por_memoria_sorpresas(partido, detalle)" not in text:
        text = text.replace(
            '    detalle["activo"] = bool(detalle["alertas"] or any(abs(v) > 0 for v in detalle["ajuste_por_signo"].values()))\n    detalle["clasificacion_losilla"] = {"local": liga_ctx["1"], "visitante": liga_ctx["2"]}\n    return detalle\n',
            '    detalle["activo"] = bool(detalle["alertas"] or any(abs(v) > 0 for v in detalle["ajuste_por_signo"].values()))\n    detalle["clasificacion_losilla"] = {"local": liga_ctx["1"], "visitante": liga_ctx["2"]}\n    detalle = reforzar_ajuste_por_memoria_sorpresas(partido, detalle)\n    return detalle\n',
        )
    return text


def patch_diario(text):
    if "def explicacion_especifica" not in text:
        helper = r'''

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
'''
        text = text.replace('\ndef explicar(pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera):', helper + '\ndef explicar(pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera):')

    if "explicacion_especifica(partido, pred" not in text:
        text = text.replace(
            '            "explicacion": explicar(pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera),\n            "aprendizaje": aprendizaje(pron, tipo, real, ok, fav, score, margen_val, tercera),\n',
            '            "explicacion": explicacion_especifica(partido, pred, pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera),\n            "ajuste_recomendado": ajuste_recomendado_especifico(partido, pred, pron, tipo, real, ok, probs, fav, score, margen_val, tercera),\n            "aprendizaje": aprendizaje(pron, tipo, real, ok, fav, score, margen_val, tercera),\n',
        )
    return text


patch_file(ROOT / "actualizar_aprendizaje_ia.py", patch_actualizar)
patch_file(ROOT / "motor_prediccion_quiniela.py", patch_motor)
patch_file(ROOT / "generar_diario_aprendizaje.py", patch_diario)

sorpresas = ROOT / "data" / "memoria_ia" / "sorpresas_mercado.json"
if not sorpresas.exists():
    sorpresas.parent.mkdir(parents=True, exist_ok=True)
    sorpresas.write_text('''{
  "version": "1.0",
  "sorpresas": []
}
''', encoding="utf-8")
    print("CREATED data/memoria_ia/sorpresas_mercado.json")
