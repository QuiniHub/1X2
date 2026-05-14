import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORIA = DATA / "memoria_ia"
PREDICCIONES = DATA / "predicciones"
JORNADAS = DATA / "jornadas"


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


def normalizar_nombre(nombre):
    texto = unicodedata.normalize("NFKD", reparar_mojibake(nombre))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = re.sub(r"\b(cf|fc|rc|cd|ud|sd|club|real|de|del|la|el|balompie|futbol)\b", "", texto)
    return re.sub(r"[^a-z0-9]", "", texto)


def crear_indice_competitivo(contexto):
    indice = {}
    for liga in ("primera", "segunda"):
        for equipo in ((contexto.get(liga) or {}).get("equipos") or []):
            registro = {**equipo, "liga": liga}
            claves = {equipo.get("clave"), normalizar_nombre(equipo.get("equipo"))}
            for clave in claves:
                if clave:
                    indice[clave] = registro
    return indice


def buscar_contexto_equipo(nombre, indice):
    clave = normalizar_nombre(nombre)
    if not clave:
        return None
    if clave in indice:
        return indice[clave]
    for clave_indice, equipo in indice.items():
        if len(clave) >= 4 and (clave in clave_indice or clave_indice in clave):
            return equipo
    return None


def signo_resultado(resultado):
    try:
        gl, gv = [int(x) for x in str(resultado).split("-")]
    except Exception:
        return None
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def pleno15_cerrado(pleno):
    if not pleno:
        return False
    resultado = str(pleno.get("resultado") or pleno.get("signo_oficial") or "").strip()
    if not resultado or resultado.lower() == "pendiente":
        return False
    return bool(re.match(r"^\d+\s*-\s*\d+$", resultado))


def top_probabilidad(partido):
    probs = partido.get("probabilidades") or {}
    orden = sorted(((signo, float(valor)) for signo, valor in probs.items()), key=lambda x: x[1], reverse=True)
    return orden[0] if orden else ("", 0.0)


def margen_probabilidad(partido):
    probs = sorted([float(v) for v in (partido.get("probabilidades") or {}).values()], reverse=True)
    if len(probs) < 2:
        return 0
    return round(probs[0] - probs[1], 2)


def leer_jornada_actual():
    candidatas = []
    for path in JORNADAS.glob("jornada_*.json"):
        data = cargar_json(path, {})
        numero = data.get("jornada")
        if not isinstance(numero, int):
            continue
        cerrados = sum(1 for p in data.get("partidos", []) if str(p.get("signo_oficial", "")).upper() in ("1", "X", "2"))
        pendientes = sum(1 for p in data.get("partidos", []) if str(p.get("signo_oficial", "")).lower() == "pendiente")
        if pendientes:
            candidatas.append((numero, cerrados, data))
    if not candidatas:
        return cargar_json(JORNADAS / "jornada_62.json", {})
    en_juego = [c for c in candidatas if c[1] > 0]
    if en_juego:
        return sorted(en_juego, key=lambda x: (x[0], x[1]), reverse=True)[0][2]
    return sorted(candidatas, key=lambda x: (x[0], x[1]), reverse=True)[0][2]


def cambios_jornada_actual(jornada, indice_competitivo=None):
    indice_competitivo = indice_competitivo or {}
    cambios = []
    signos = Counter()
    cerrados = 0
    pendientes = 0
    for partido in jornada.get("partidos", []):
        oficial = str(partido.get("signo_oficial", "")).upper()
        if oficial in ("1", "X", "2"):
            cerrados += 1
            signos[oficial] += 1
            cambios.append({
                "num": partido.get("num"),
                "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
                "resultado": partido.get("resultado"),
                "signo": oficial,
                "lectura": lectura_resultado(partido, oficial, indice_competitivo),
            })
        else:
            pendientes += 1
    pleno = jornada.get("pleno15") or {}
    pleno_cerrado = pleno15_cerrado(pleno)
    pleno_estado = "cerrado" if pleno_cerrado else "pendiente" if pleno else "sin_datos"
    return {
        "jornada": jornada.get("jornada"),
        "partidos": len(jornada.get("partidos", [])),
        "cerrados": cerrados,
        "pendientes": pendientes,
        "pendientes_totales_con_pleno15": pendientes + (0 if pleno_cerrado or not pleno else 1),
        "pleno15": {
            "estado": pleno_estado,
            "partido": f"{pleno.get('local', '')} - {pleno.get('visitante', '')}".strip(" -"),
            "resultado": pleno.get("resultado") or "Pendiente",
        },
        "distribucion_signos": {k: signos[k] for k in ("1", "X", "2")},
        "resultados_nuevos_o_vigentes": cambios[-8:],
    }


def objetivo_principal(equipo):
    if not equipo:
        return None
    prioridad = {
        "riesgo_descenso": 100,
        "en_descenso_con_opciones": 95,
        "permanencia_por_cerrar": 90,
        "descenso_muy_complicado": 80,
        "defiende_liderato": 75,
        "defiende_plaza": 70,
        "aspira_matematicamente": 65,
        "ventaja_por_permanencia": 45,
        "campeon_matematico": 20,
        "asegurado_matematicamente": 15,
    }
    objetivos = equipo.get("objetivos") or []
    if not objetivos:
        return None
    return sorted(objetivos, key=lambda obj: prioridad.get(obj.get("estado"), 0), reverse=True)[0]


def motivacion_texto(equipo):
    if not equipo:
        return "sin contexto competitivo claro"
    objetivo = objetivo_principal(equipo)
    motivacion = equipo.get("motivacion_competitiva", "baja")
    nombre = reparar_mojibake(equipo.get("equipo"))
    base = f"{nombre} tiene motivacion {motivacion}"
    if objetivo:
        objetivo_txt = str(objetivo.get("objetivo", "")).replace("_", " ")
        estado_txt = str(objetivo.get("estado", "")).replace("_", " ")
        lectura = reparar_mojibake(objetivo.get("lectura"))
        return f"{base}: {objetivo_txt} ({estado_txt}); {lectura}"
    return base


def resumen_objetivo(objetivo):
    return {
        "objetivo": objetivo.get("objetivo"),
        "estado": objetivo.get("estado"),
        "lectura": reparar_mojibake(objetivo.get("lectura")),
    }


def lectura_resultado(partido, signo, indice_competitivo=None):
    resultado = partido.get("resultado", "")
    local_ctx = buscar_contexto_equipo(partido.get("local"), indice_competitivo or {})
    visitante_ctx = buscar_contexto_equipo(partido.get("visitante"), indice_competitivo or {})
    local_valor = valor_motivacion(local_ctx)
    visitante_valor = valor_motivacion(visitante_ctx)

    if signo == "2":
        base = f"Victoria visitante ({resultado}); aumenta la cautela con favoritos locales y partidos de inercia rota."
    elif signo == "X":
        base = f"Empate ({resultado}); refuerza peso de equilibrio, rachas de empate y marcadores cerrados."
    else:
        base = f"Victoria local ({resultado}); el factor casa puede ayudar, pero no basta como explicacion."

    if not local_ctx and not visitante_ctx:
        return base

    motivacion = f" Contexto competitivo: {motivacion_texto(local_ctx)}. {motivacion_texto(visitante_ctx)}."
    if local_valor > visitante_valor and signo == "1":
        motivacion += " Lectura IA: la necesidad del local pesa y puede explicar una victoria que no debe leerse solo como factor campo."
    elif visitante_valor > local_valor and signo == "2":
        motivacion += " Lectura IA: la necesidad del visitante pesa y puede explicar que rompa el pronostico local."
    elif abs(local_valor - visitante_valor) >= 2:
        motivacion += " Lectura IA: hay descompensacion de urgencia; debo subir peso de motivacion en partidos similares."
    else:
        motivacion += " Lectura IA: motivacion parecida; debo apoyarme mas en forma, goles y empates."
    return base + motivacion


def analizar_prediccion(prediccion, contexto_competitivo=None):
    partidos = prediccion.get("partidos", [])
    orden_riesgo = sorted(partidos, key=lambda p: float(p.get("incertidumbre", 0)), reverse=True)
    orden_seguridad = sorted(partidos, key=lambda p: (float(p.get("incertidumbre", 999)), -margen_probabilidad(p)))
    indice_competitivo = crear_indice_competitivo(contexto_competitivo or {})

    seguros = []
    trampas = []
    dudas = []
    for p in orden_seguridad[:5]:
        signo, prob = top_probabilidad(p)
        seguros.append({
            "num": p.get("num"),
            "partido": f"{p.get('local', '')} - {p.get('visitante', '')}",
            "signo": p.get("signo_final") or signo,
            "probabilidad_top": prob,
            "incertidumbre": p.get("incertidumbre"),
            "motivo": "Baja incertidumbre relativa y margen de probabilidad superior al resto del boleto.",
        })
    for p in orden_riesgo[:5]:
        signo, prob = top_probabilidad(p)
        trampas.append({
            "num": p.get("num"),
            "partido": f"{p.get('local', '')} - {p.get('visitante', '')}",
            "signo_base": p.get("signo_final") or signo,
            "probabilidad_top": prob,
            "incertidumbre": p.get("incertidumbre"),
            "probabilidad_sorpresa": p.get("probabilidad_sorpresa"),
            "motivo": motivo_trampa(p),
        })
    for p in orden_riesgo[:4]:
        dudas.append({
            "num": p.get("num"),
            "partido": f"{p.get('local', '')} - {p.get('visitante', '')}",
            "pregunta": duda_partido(p),
        })

    resumen = prediccion.get("resumen") or {}
    return {
        "jornada": prediccion.get("jornada"),
        "configuracion_actual": resumen,
        "partidos_mas_seguros": seguros,
        "partidos_trampa_o_sorpresa": trampas,
        "dudas_abiertas": dudas,
        "partidos_con_motivacion": analizar_motivacion_prediccion(partidos, indice_competitivo),
    }


def resumen_contexto_equipo(equipo):
    if not equipo:
        return None
    objetivos = []
    for objetivo in equipo.get("objetivos", [])[:4]:
        objetivos.append(resumen_objetivo(objetivo))
    return {
        "equipo": reparar_mojibake(equipo.get("equipo")),
        "liga": equipo.get("liga"),
        "posicion": equipo.get("posicion"),
        "puntos": equipo.get("puntos"),
        "puntos_en_juego": equipo.get("puntos_en_juego"),
        "motivacion": equipo.get("motivacion_competitiva"),
        "objetivos": objetivos,
    }


def valor_motivacion(equipo):
    orden = {"baja": 0, "media": 1, "alta": 2, "maxima": 3}
    if not equipo:
        return 0
    return orden.get(str(equipo.get("motivacion_competitiva", "baja")).lower(), 0)


def etiquetas_objetivos(equipo):
    if not equipo:
        return "sin contexto competitivo suficiente"
    etiquetas = []
    for objetivo in equipo.get("objetivos", [])[:3]:
        nombre = str(objetivo.get("objetivo", "")).replace("_", " ")
        estado = str(objetivo.get("estado", "")).replace("_", " ")
        etiquetas.append(f"{nombre} ({estado})")
    return ", ".join(etiquetas) if etiquetas else "sin objetivo fuerte detectado"


def lectura_motivacion(local, visitante):
    local_valor = valor_motivacion(local)
    visitante_valor = valor_motivacion(visitante)
    local_nombre = reparar_mojibake(local.get("equipo")) if local else "local"
    visitante_nombre = reparar_mojibake(visitante.get("equipo")) if visitante else "visitante"
    if local_valor >= 2 and visitante_valor >= 2:
        return f"Choque de alta presion: {local_nombre} pelea {etiquetas_objetivos(local)} y {visitante_nombre} pelea {etiquetas_objetivos(visitante)}."
    if local_valor > visitante_valor:
        return f"La urgencia competitiva pesa mas en {local_nombre}: {etiquetas_objetivos(local)}."
    if visitante_valor > local_valor:
        return f"La urgencia competitiva pesa mas en {visitante_nombre}: {etiquetas_objetivos(visitante)}."
    return f"Motivacion parecida: {local_nombre} ({etiquetas_objetivos(local)}) frente a {visitante_nombre} ({etiquetas_objetivos(visitante)})."


def analizar_motivacion_prediccion(partidos, indice_competitivo):
    analisis = []
    for partido in partidos:
        local = buscar_contexto_equipo(partido.get("local"), indice_competitivo)
        visitante = buscar_contexto_equipo(partido.get("visitante"), indice_competitivo)
        if not local and not visitante:
            continue
        analisis.append({
            "num": partido.get("num"),
            "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
            "nivel": max(valor_motivacion(local), valor_motivacion(visitante)),
            "local": resumen_contexto_equipo(local),
            "visitante": resumen_contexto_equipo(visitante),
            "lectura": lectura_motivacion(local, visitante),
        })
    return sorted(analisis, key=lambda x: (-x["nivel"], x.get("num") or 99))


def motivo_trampa(partido):
    probs = partido.get("probabilidades") or {}
    x = float(probs.get("X", 0))
    margen = margen_probabilidad(partido)
    if x >= 33:
        return "Empate con mucho peso; no debe tratarse como fijo tranquilo."
    if margen < 8:
        return "Probabilidades muy juntas; cualquier signo alternativo puede tener valor."
    return "Incertidumbre alta por mezcla de forma, clasificacion, casa/fuera y contexto."


def duda_partido(partido):
    probs = partido.get("probabilidades") or {}
    x = float(probs.get("X", 0))
    if x >= 33:
        return "El empate esta demasiado cerca del signo elegido; revisar si merece doble."
    if "lesion" in str(partido.get("razonamiento", "")).lower() or "baja" in str(partido.get("razonamiento", "")).lower():
        return "La noticia de bajas puede cambiar el valor real del signo."
    if float(partido.get("probabilidad_sorpresa") or 0) >= 45:
        return "El azar estimado es alto; no debo tratar este signo como lectura cerrada."
    return "La incertidumbre es alta; esperar resultados/noticias antes de cerrar fijo."


def autocritica(jornada_actual, prediccion, memoria):
    criticas = []
    if jornada_actual.get("pendientes_totales_con_pleno15", jornada_actual.get("pendientes", 0)):
        criticas.append("Lectura provisional: no debo cerrar conclusiones fuertes mientras la jornada actual tenga partidos pendientes o el Pleno al 15 abierto.")
    if (prediccion.get("resumen") or {}).get("fijos", 0) >= 14:
        criticas.append("Autocritica: una quiniela con 14 fijos es demasiado rigida para una jornada con varios partidos equilibrados; deberia sugerir dobles/triples en los mayores riesgos.")
    propias = ((memoria.get("quiniela") or {}).get("nuestras_quinielas") or {})
    if not propias.get("jornadas_validadas"):
        criticas.append("Aun no tengo suficientes boletos nuestros persistidos; mi autocritica sobre nuestros errores reales sigue incompleta.")
    if jornada_actual.get("distribucion_signos", {}).get("2", 0) >= 3:
        criticas.append("La jornada actual trae varios doses; debo vigilar visitantes en buena dinamica aunque no sean favoritos claros.")
    return criticas


def aprendizajes(jornada_actual):
    signos = jornada_actual.get("distribucion_signos", {})
    resultados = jornada_actual.get("resultados_nuevos_o_vigentes") or []
    aprend = []
    if signos.get("2", 0):
        aprend.append("Los visitantes estan apareciendo con peso en la jornada actual; subir alerta de sorpresa visitante para la siguiente lectura.")
    if signos.get("X", 0):
        aprend.append("Los empates cerrados siguen siendo relevantes; no bajar demasiado el peso de X en partidos de margen corto.")
    if signos.get("1", 0):
        aprend.append("El factor local se mantiene util cuando hay ventaja clara, pero no basta si la dinamica visitante es fuerte.")
    for resultado in resultados:
        lectura = str(resultado.get("lectura", ""))
        if "Contexto competitivo:" in lectura and ("necesidad" in lectura or "descompensacion de urgencia" in lectura):
            aprend.append(
                f"{reparar_mojibake(resultado.get('partido'))}: debo explicar el signo con urgencia competitiva, puntos en juego y objetivos vivos, no solo con localia o favorito."
            )
            break
    if not aprend:
        aprend.append("Todavia no hay suficientes resultados cerrados en la jornada actual para extraer aprendizaje fuerte.")
    return aprend


def aprendizajes_contexto(contexto):
    aprend = []
    primera = contexto.get("primera") or {}
    segunda = contexto.get("segunda") or {}
    for lectura in (primera.get("lecturas_clave") or [])[:3]:
        aprend.append(f"Primera: {lectura}")
    for lectura in (segunda.get("lecturas_clave") or [])[:3]:
        aprend.append(f"Segunda: {lectura}")
    if contexto:
        aprend.append("En la recta final debo subir peso a la necesidad real de puntos: titulo, Europa, ascenso, playoff y descenso.")
    return aprend


def resumen_equipos_liga(liga, nombre_liga):
    equipos = []
    for equipo in (liga.get("equipos") or []):
        principal = objetivo_principal(equipo)
        equipos.append({
            "equipo": reparar_mojibake(equipo.get("equipo")),
            "liga": nombre_liga,
            "posicion": equipo.get("posicion"),
            "puntos": equipo.get("puntos"),
            "puntos_en_juego": equipo.get("puntos_en_juego"),
            "motivacion": equipo.get("motivacion_competitiva"),
            "objetivo_principal": resumen_objetivo(principal) if principal else None,
            "objetivos": [resumen_objetivo(obj) for obj in (equipo.get("objetivos") or [])[:4]],
        })
    return sorted(equipos, key=lambda x: x.get("posicion") or 999)


def resumir_contexto_competitivo(contexto):
    if not contexto:
        return {}
    primera = contexto.get("primera") or {}
    segunda = contexto.get("segunda") or {}
    return {
        "generado_en": contexto.get("generado_en"),
        "reglas": contexto.get("reglas") or {},
        "primera": {
            "resumen": primera.get("resumen") or {},
            "lecturas_clave": primera.get("lecturas_clave") or [],
            "equipos": resumen_equipos_liga(primera, "primera"),
        },
        "segunda": {
            "resumen": segunda.get("resumen") or {},
            "lecturas_clave": segunda.get("lecturas_clave") or [],
            "equipos": resumen_equipos_liga(segunda, "segunda"),
        },
    }


def errores_a_evitar(prediccion):
    riesgos = sorted(prediccion.get("partidos", []), key=lambda p: float(p.get("incertidumbre", 0)), reverse=True)[:3]
    errores = [
        "No convertir en Elige 8 partidos con incertidumbre alta.",
        "No dejar como fijo un partido donde el empate supera el 33% sin revisar cobertura.",
        "No ignorar bajas, sanciones o contexto si afectan al favorito.",
        "No confundir probabilidad alta con certeza: el azar tambien forma parte de la quiniela.",
    ]
    for p in riesgos:
        errores.append(f"Revisar antes de validar: {p.get('local')} - {p.get('visitante')} tiene incertidumbre {p.get('incertidumbre')}.")
    return errores


def main():
    memoria = cargar_json(MEMORIA / "aprendizaje_global.json", {})
    contexto_competitivo = cargar_json(MEMORIA / "contexto_competitivo.json", {})
    prediccion = cargar_json(PREDICCIONES / "jornada_63.json", {})
    if not prediccion:
        prediccion = cargar_json(PREDICCIONES / "ultima_prediccion.json", {})
    jornada = leer_jornada_actual()
    indice_competitivo = crear_indice_competitivo(contexto_competitivo or {})
    estado_jornada = cambios_jornada_actual(jornada, indice_competitivo)
    estado_prediccion = analizar_prediccion(prediccion, contexto_competitivo)

    salida = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "estado": "vivo_en_desarrollo",
        "jornada_actual": estado_jornada,
        "prediccion_objetivo": estado_prediccion,
        "contexto_competitivo": resumir_contexto_competitivo(contexto_competitivo),
        "que_ha_cambiado": estado_jornada["resultados_nuevos_o_vigentes"],
        "que_aprende": aprendizajes(estado_jornada) + aprendizajes_contexto(contexto_competitivo),
        "que_modifica_para_jornada_63": [
            "Reordenar confianza segun resultados nuevos de la jornada actual.",
            "Subir vigilancia de empates o visitantes si la jornada actual los confirma.",
            "Priorizar dobles/triples en partidos con incertidumbre mas alta.",
            "Cruzar cada signo con la necesidad real de puntos: titulo, Europa, ascenso, playoff y descenso.",
        ],
        "partidos_mas_seguros": estado_prediccion["partidos_mas_seguros"],
        "partidos_trampa_o_sorpresa": estado_prediccion["partidos_trampa_o_sorpresa"],
        "dudas_abiertas": estado_prediccion["dudas_abiertas"],
        "autocritica": autocritica(estado_jornada, prediccion, memoria),
        "errores_a_evitar": errores_a_evitar(prediccion),
    }
    guardar_json(MEMORIA / "estado_vivo.json", salida)
    print(MEMORIA / "estado_vivo.json")


if __name__ == "__main__":
    main()
