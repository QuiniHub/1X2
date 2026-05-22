import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
JUGADAS = DATA / "quinielas_jugadas"
JORNADAS = DATA / "jornadas"
MEMORIA_ELIGE8 = DATA / "memoria_ia" / "aprendizaje_elige8.json"


REGLA_BASE = (
    "Elige 8 no se elige por partido interesante ni por cobertura: se eligen los 8 partidos "
    "donde el signo base tiene mejor probabilidad real de acierto, penalizando incertidumbre, "
    "riesgo de sorpresa y empates por debajo de zona claramente fiable."
)


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def prob_signo(partido, signo):
    probs = partido.get("probabilidades") or {}
    if signo in probs:
        try:
            return float(probs.get(signo) or 0)
        except (TypeError, ValueError):
            return 0.0
    valores = []
    for valor in probs.values():
        try:
            valores.append(float(valor or 0))
        except (TypeError, ValueError):
            pass
    return max(valores) if valores else 0.0


def signo_base(partido):
    signo = str(partido.get("signo_base") or "").strip()
    if signo in {"1", "X", "2"}:
        return signo
    probs = partido.get("probabilidades") or {}
    if not probs:
        return ""
    return max(("1", "X", "2"), key=lambda s: prob_signo(partido, s))


def puntuacion_elige8(partido):
    signo = signo_base(partido)
    prob = prob_signo(partido, signo)
    incertidumbre = float(partido.get("incertidumbre") or 0)
    sorpresa = float(partido.get("probabilidad_sorpresa") or 0)

    score = prob * 2.4 - incertidumbre * 0.22 - sorpresa * 0.30

    if signo == "X" and prob < 55:
        score -= 12
    elif signo == "X" and prob < 60:
        score -= 5

    if partido.get("riesgo_necesidad_real"):
        score -= 3

    return round(score, 3)


def explicar_entrada_elige8(partido):
    signo = signo_base(partido)
    prob = prob_signo(partido, signo)
    return (
        f"Entra en Elige 8 por confianza de cobro: signo {signo} con {prob:.1f}% "
        f"y puntuacion Elige 8 {puntuacion_elige8(partido):.1f}."
    )


def recalcular_elige8(prediccion):
    partidos = [p for p in prediccion.get("partidos", []) if int(p.get("num", 0) or 0) <= 14]
    if not partidos:
        return False

    tenia_elige8 = bool((prediccion.get("configuracion") or {}).get("elige8")) or any(p.get("elige8") for p in partidos)
    if not tenia_elige8:
        return False

    ordenados = sorted(
        partidos,
        key=lambda p: (puntuacion_elige8(p), prob_signo(p, signo_base(p))),
        reverse=True,
    )
    seleccionados = {int(p.get("num")) for p in ordenados[:8]}

    ranking = []
    for posicion, partido in enumerate(ordenados, start=1):
        num = int(partido.get("num", 0) or 0)
        signo = signo_base(partido)
        prob = prob_signo(partido, signo)
        elegido = num in seleccionados
        partido["elige8"] = elegido
        partido["elige8_score"] = puntuacion_elige8(partido)
        partido["elige8_probabilidad_signo"] = round(prob, 1)
        partido["elige8_signo_objetivo"] = signo
        if elegido:
            partido["elige8_criterio"] = explicar_entrada_elige8(partido)
        else:
            partido.pop("elige8_criterio", None)
        ranking.append({
            "posicion": posicion,
            "num": num,
            "local": partido.get("local"),
            "visitante": partido.get("visitante"),
            "signo": signo,
            "probabilidad": round(prob, 1),
            "score": partido["elige8_score"],
            "seleccionado": elegido,
        })

    prediccion["elige8_aprendizaje"] = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "regla_activa": REGLA_BASE,
        "criterio": "ranking_por_probabilidad_de_cobro",
        "ranking": ranking,
    }
    resumen = prediccion.setdefault("resumen", {})
    resumen["elige8_seleccionados"] = 8
    return True


def signos_oficiales_jornada(jornada):
    data = cargar_json(JORNADAS / f"jornada_{jornada}.json", {})
    signos = {}
    for partido in data.get("partidos", []):
        num = int(partido.get("num", 0) or 0)
        signo = str(partido.get("signo_oficial") or partido.get("resultado_1x2") or "").strip().upper()
        if num and signo in {"1", "X", "2"}:
            signos[num] = signo
    return signos


def actualizar_memoria(prediccion):
    jornada = prediccion.get("jornada")
    partidos = [p for p in prediccion.get("partidos", []) if int(p.get("num", 0) or 0) <= 14]
    if not jornada or not partidos:
        return

    oficiales = signos_oficiales_jornada(jornada)
    if not oficiales:
        return

    aciertos_totales = 0
    aciertos_elige8 = 0
    seleccionados = []
    partido_rompio = None

    for partido in partidos:
        num = int(partido.get("num", 0) or 0)
        oficial = oficiales.get(num)
        signo = signo_base(partido)
        acierto = bool(oficial and signo == oficial)
        if acierto:
            aciertos_totales += 1
        if partido.get("elige8"):
            seleccionados.append(num)
            if acierto:
                aciertos_elige8 += 1
            elif partido_rompio is None:
                partido_rompio = {
                    "num": num,
                    "local": partido.get("local"),
                    "visitante": partido.get("visitante"),
                    "pronostico": signo,
                    "oficial": oficial,
                    "probabilidad_pronostico": prob_signo(partido, signo),
                }

    memoria = cargar_json(MEMORIA_ELIGE8, {"version": "1.0", "jornadas": []})
    jornadas = [j for j in memoria.get("jornadas", []) if j.get("jornada") != jornada]
    premio_cobrado = 0.0
    premio_escapado = 0.0
    if aciertos_elige8 == 8:
        regla = "La seleccion fue cobrable: mantener prioridad por probabilidad alta y baja incertidumbre."
    else:
        regla = "Si Elige 8 falla, revisar el primer fallo y bajar peso de perfiles parecidos aunque sean atractivos para cobertura."

    jornadas.append({
        "jornada": jornada,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "aciertos_totales": aciertos_totales,
        "aciertos_elige8": aciertos_elige8,
        "seleccionados_elige8": seleccionados,
        "partido_que_rompio_elige8": partido_rompio,
        "premio_cobrado": premio_cobrado,
        "premio_que_se_escapo": premio_escapado,
        "regla_aprendida": regla,
    })
    memoria["jornadas"] = sorted(jornadas, key=lambda j: j.get("jornada") or 0)
    memoria["ultima_regla_aprendida"] = regla
    memoria["actualizado_en"] = datetime.now(timezone.utc).isoformat()
    guardar_json(MEMORIA_ELIGE8, memoria)


def procesar_archivo(path):
    prediccion = cargar_json(path, {})
    if not recalcular_elige8(prediccion):
        return False
    actualizar_memoria(prediccion)
    guardar_json(path, prediccion)
    return True


def main():
    tocados = []
    for carpeta in (PREDICCIONES, JUGADAS):
        if not carpeta.exists():
            continue
        for path in sorted(carpeta.glob("*.json")):
            if procesar_archivo(path):
                tocados.append(str(path.relative_to(ROOT)))

    print(json.dumps({
        "estado": "ok",
        "script": "ajustar_aprendizaje_elige8.py",
        "archivos_actualizados": tocados,
        "regla_activa": REGLA_BASE,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
