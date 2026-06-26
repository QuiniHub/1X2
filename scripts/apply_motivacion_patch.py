from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "motor_prediccion_quiniela.py"
text = path.read_text(encoding="utf-8")
original = text

if "calcular_ajuste_motivacion(partido, clasificaciones_mundial, fuente_losilla)" not in text:
    text = text.replace(
        'PERFILES_EQUIPOS = DATA / "memoria_ia" / "perfiles_equipos.json"\n',
        'PERFILES_EQUIPOS = DATA / "memoria_ia" / "perfiles_equipos.json"\n'
        'CLASIFICACIONES_MUNDIAL = DATA / "memoria_ia" / "clasificaciones_mundial_2026.json"\n'
        'FUENTE_LOSILLA = DATA / "memoria_ia" / "fuente_losilla.json"\n',
    )

    helper = r'''
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
'''
    text = text.replace('\ndef ajustar_por_motivacion(probs, local_comp, visitante_comp):', '\n' + helper + '\ndef ajustar_por_motivacion(probs, local_comp, visitante_comp):')
    text = text.replace('    perfiles_autonomos = cargar_json(PERFILES_EQUIPOS, {})\n', '    perfiles_autonomos = cargar_json(PERFILES_EQUIPOS, {})\n    clasificaciones_mundial = cargar_json(CLASIFICACIONES_MUNDIAL, {})\n    fuente_losilla = cargar_json(FUENTE_LOSILLA, {})\n')
    text = text.replace('        lecturas_motivacion.extend(lecturas_datos_profesionales)\n        inc = incertidumbre(\n', '        lecturas_motivacion.extend(lecturas_datos_profesionales)\n        ajuste_motivacion_competitiva = calcular_ajuste_motivacion({**partido, "probabilidades": probs}, clasificaciones_mundial, fuente_losilla)\n        probs = aplicar_ajuste_motivacion_competitiva(probs, ajuste_motivacion_competitiva)\n        riesgo_motivacion_competitiva = 0.0\n        if ajuste_motivacion_competitiva.get("activo"):\n            riesgo_motivacion_competitiva = min(sum(abs(v) for v in ajuste_motivacion_competitiva.get("ajuste_por_signo", {}).values()), 35.0)\n            lecturas_motivacion.extend(ajuste_motivacion_competitiva.get("lecturas", []))\n        inc = incertidumbre(\n')
    text = text.replace('            + riesgo_datos_profesionales,\n', '            + riesgo_datos_profesionales\n            + riesgo_motivacion_competitiva,\n')
    text = text.replace('                "lecturas": lecturas_datos_profesionales,\n            },\n            "trazabilidad_datos": trazabilidad,\n', '                "lecturas": lecturas_datos_profesionales,\n            },\n            "ajuste_motivacion": ajuste_motivacion_competitiva,\n            "alertas_motivacion": ajuste_motivacion_competitiva.get("alertas", []),\n            "sorpresa_potencial": bool(ajuste_motivacion_competitiva.get("sorpresa_potencial")),\n            "nivel_sorpresa": ajuste_motivacion_competitiva.get("nivel_sorpresa", ""),\n            "forzar_cobertura_motivacion": ajuste_motivacion_competitiva.get("forzar_cobertura", ""),\n            "trazabilidad_datos": trazabilidad,\n')
    text = text.replace('        indice_sorpresa = indice_sorpresa_quinielistica(evaluado, patrones_competitivos)\n', '        indice_sorpresa = indice_sorpresa_quinielistica(evaluado, patrones_competitivos)\n        if ajuste_motivacion_competitiva.get("sorpresa_potencial"):\n            indice_sorpresa["indice"] = max(float(indice_sorpresa.get("indice") or 0), 60.0)\n            indice_sorpresa["categoria"] = "alta"\n            indice_sorpresa["favorito_atacable"] = True\n            indice_sorpresa["cobertura_sugerida"] = ajuste_motivacion_competitiva.get("forzar_cobertura") or "DOBLE"\n            indice_sorpresa.setdefault("motivos", []).append("alerta motivacional con mercado Losilla superior al 80%")\n')
    text = text.replace('    score = prioridad_cobertura(partido)\n    detalle_indice = partido.get("_indice_sorpresa_quinielistica") or {}\n', '    score = prioridad_cobertura(partido)\n    if partido.get("forzar_cobertura_motivacion") == "TRIPLE":\n        score += 180\n    elif partido.get("forzar_cobertura_motivacion") == "DOBLE":\n        score += 85\n    detalle_indice = partido.get("_indice_sorpresa_quinielistica") or {}\n', 1)
    text = text.replace('    score = prioridad_cobertura(partido)\n    detalle_indice = partido.get("_indice_sorpresa_quinielistica") or {}\n', '    score = prioridad_cobertura(partido)\n    if partido.get("forzar_cobertura_motivacion") in {"DOBLE", "TRIPLE"}:\n        score += 120\n    detalle_indice = partido.get("_indice_sorpresa_quinielistica") or {}\n', 1)
    text = text.replace('            "ajuste_datos_profesionales": partido["ajuste_datos_profesionales"],\n            "elige8": False,\n', '            "ajuste_datos_profesionales": partido["ajuste_datos_profesionales"],\n            "ajuste_motivacion": partido["ajuste_motivacion"],\n            "alertas_motivacion": partido["alertas_motivacion"],\n            "sorpresa_potencial": partido["sorpresa_potencial"],\n            "nivel_sorpresa": partido["nivel_sorpresa"],\n            "forzar_cobertura_motivacion": partido["forzar_cobertura_motivacion"],\n            "elige8": False,\n')
    text = text.replace('    resumen_profesional_boleto = {\n', '    pleno15_base = data.get("pleno15") or {}\n    ajuste_pleno15 = calcular_ajuste_motivacion({**pleno15_base, "num": 15, "probabilidades": {"1": 33.3, "X": 33.3, "2": 33.3}}, clasificaciones_mundial, fuente_losilla)\n    pleno15_ajustado = ajustar_pleno15_motivacion(pleno15_base, fuente_losilla, ajuste_pleno15)\n    resumen_profesional_boleto = {\n')
    text = text.replace('        "pleno15": data.get("pleno15"),\n', '        "pleno15": pleno15_ajustado,\n')

if text == original:
    print("Sin cambios: el parche de motivacion ya estaba aplicado o no encontro anclas.")
else:
    path.write_text(text, encoding="utf-8")
    print("Parche de motivacion competitiva aplicado en motor_prediccion_quiniela.py")
