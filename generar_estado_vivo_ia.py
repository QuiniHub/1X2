import json
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
    return sorted(candidatas, key=lambda x: (x[0], x[1]), reverse=True)[0][2]


def cambios_jornada_actual(jornada):
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
                "lectura": lectura_resultado(partido, oficial),
            })
        else:
            pendientes += 1
    return {
        "jornada": jornada.get("jornada"),
        "cerrados": cerrados,
        "pendientes": pendientes,
        "distribucion_signos": {k: signos[k] for k in ("1", "X", "2")},
        "resultados_nuevos_o_vigentes": cambios[-8:],
    }


def lectura_resultado(partido, signo):
    resultado = partido.get("resultado", "")
    if signo == "2":
        return f"Victoria visitante ({resultado}); aumenta la cautela con favoritos locales y partidos de inercia rota."
    if signo == "X":
        return f"Empate ({resultado}); refuerza peso de equilibrio, rachas de empate y marcadores cerrados."
    return f"Victoria local ({resultado}); confirma que el factor casa sigue teniendo valor cuando hay ventaja clara."


def analizar_prediccion(prediccion):
    partidos = prediccion.get("partidos", [])
    orden_riesgo = sorted(partidos, key=lambda p: float(p.get("incertidumbre", 0)), reverse=True)
    orden_seguridad = sorted(partidos, key=lambda p: (float(p.get("incertidumbre", 999)), -margen_probabilidad(p)))

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
    }


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
    return "La incertidumbre es alta; esperar resultados/noticias antes de cerrar fijo."


def autocritica(jornada_actual, prediccion, memoria):
    criticas = []
    if jornada_actual.get("pendientes", 0):
        criticas.append("Lectura provisional: no debo cerrar conclusiones fuertes mientras la jornada actual tenga partidos pendientes.")
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
    aprend = []
    if signos.get("2", 0):
        aprend.append("Los visitantes estan apareciendo con peso en la jornada actual; subir alerta de sorpresa visitante para la siguiente lectura.")
    if signos.get("X", 0):
        aprend.append("Los empates cerrados siguen siendo relevantes; no bajar demasiado el peso de X en partidos de margen corto.")
    if signos.get("1", 0):
        aprend.append("El factor local se mantiene util cuando hay ventaja clara, pero no basta si la dinamica visitante es fuerte.")
    if not aprend:
        aprend.append("Todavia no hay suficientes resultados cerrados en la jornada actual para extraer aprendizaje fuerte.")
    return aprend


def errores_a_evitar(prediccion):
    riesgos = sorted(prediccion.get("partidos", []), key=lambda p: float(p.get("incertidumbre", 0)), reverse=True)[:3]
    errores = [
        "No convertir en Elige 8 partidos con incertidumbre alta.",
        "No dejar como fijo un partido donde el empate supera el 33% sin revisar cobertura.",
        "No ignorar bajas, sanciones o contexto si afectan al favorito.",
    ]
    for p in riesgos:
        errores.append(f"Revisar antes de validar: {p.get('local')} - {p.get('visitante')} tiene incertidumbre {p.get('incertidumbre')}.")
    return errores


def main():
    memoria = cargar_json(MEMORIA / "aprendizaje_global.json", {})
    prediccion = cargar_json(PREDICCIONES / "jornada_63.json", {})
    if not prediccion:
        prediccion = cargar_json(PREDICCIONES / "ultima_prediccion.json", {})
    jornada = leer_jornada_actual()
    estado_jornada = cambios_jornada_actual(jornada)
    estado_prediccion = analizar_prediccion(prediccion)

    salida = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "estado": "vivo_en_desarrollo",
        "jornada_actual": estado_jornada,
        "prediccion_objetivo": estado_prediccion,
        "que_ha_cambiado": estado_jornada["resultados_nuevos_o_vigentes"],
        "que_aprende": aprendizajes(estado_jornada),
        "que_modifica_para_jornada_63": [
            "Reordenar confianza segun resultados nuevos de la jornada actual.",
            "Subir vigilancia de empates o visitantes si la jornada actual los confirma.",
            "Priorizar dobles/triples en partidos con incertidumbre mas alta.",
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
