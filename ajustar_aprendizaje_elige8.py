import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
JUGADAS_ARCHIVO = DATA / "quinielas_jugadas.json"
JORNADAS = DATA / "jornadas"
MEMORIA_ELIGE8 = DATA / "memoria_ia" / "aprendizaje_elige8.json"
SIGNOS = ("1", "X", "2")


PREMIOS_CONOCIDOS = {
    63: {
        "premio_cobrado": 5.72,
        "premio_que_se_escapo": 572.0,
        "nota": "Jornada 63: 10 aciertos totales y Elige 8 de 7/8.",
    }
}

REGLA_BASE = (
    "Elige 8 se elige por probabilidad real de acertar el signo jugado: "
    "TRIPLE=100%, DOBLE=suma de probabilidades de sus dos signos, "
    "FIJO=probabilidad de su unico signo. El tipo no prioriza salvo el triple, que siempre es 100%."
)


def ahora():
    return datetime.now(timezone.utc).isoformat()


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


def normalizar_signos(valor):
    signos = "".join(ch for ch in str(valor or "").upper() if ch in "1X2")
    return "".join(dict.fromkeys(signos))


def probabilidades_pct(partido):
    probs = partido.get("probabilidades") or {}
    salida = {}
    for signo in SIGNOS:
        try:
            salida[signo] = max(float(probs.get(signo) or 0), 0.0)
        except (TypeError, ValueError):
            salida[signo] = 0.0
    total = sum(salida.values())
    if 0 < total <= 1.5:
        salida = {signo: valor * 100.0 for signo, valor in salida.items()}
    return salida


def prob_signo(partido, signo):
    return probabilidades_pct(partido).get(signo, 0.0)


def signo_base(partido):
    signo = normalizar_signos(partido.get("signo_base") or partido.get("signo_final"))
    if len(signo) == 1:
        return signo
    probs = probabilidades_pct(partido)
    if not any(probs.values()):
        return signo[:1]
    return max(SIGNOS, key=lambda s: probs.get(s, 0.0))


def signos_jugados(partido):
    signos = normalizar_signos(partido.get("signo_final") or partido.get("signos") or partido.get("signo_base"))
    return signos or signo_base(partido) or ""


def tipo_cobertura(signos):
    total = len(normalizar_signos(signos))
    if total >= 3:
        return "TRIPLE"
    if total == 2:
        return "DOBLE"
    if total == 1:
        return "FIJO"
    return "SIN_SIGNO"


def probabilidad_cubierta(partido):
    signos = signos_jugados(partido)
    if len(signos) >= 3:
        return 100.0
    probs = probabilidades_pct(partido)
    return round(min(100.0, sum(probs.get(signo, 0.0) for signo in signos)), 3)


def puntuacion_elige8(partido):
    return probabilidad_cubierta(partido)


def incertidumbre(partido):
    try:
        return float(partido.get("incertidumbre") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def sorpresa(partido):
    try:
        return float(partido.get("probabilidad_sorpresa") or partido.get("surprise_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def clave_ranking_elige8(partido):
    return (
        -probabilidad_cubierta(partido),
        incertidumbre(partido),
        sorpresa(partido),
        int(partido.get("num", 0) or 0),
    )


def explicar_entrada_elige8(partido):
    signos = signos_jugados(partido)
    cubierta = probabilidad_cubierta(partido)
    tipo = tipo_cobertura(signos)
    if tipo == "TRIPLE":
        return "Entra en Elige 8 porque es TRIPLE: probabilidad real de acierto 100%."
    if tipo == "DOBLE":
        return f"Entra en Elige 8 porque el doble {signos} suma {cubierta:.1f}% de probabilidad real de acierto."
    return f"Entra en Elige 8 porque el fijo {signos} tiene {cubierta:.1f}% de probabilidad real de acierto."


def recalcular_elige8(prediccion):
    partidos = [p for p in prediccion.get("partidos", []) if int(p.get("num", 0) or 0) <= 14]
    if not partidos:
        return False

    config = prediccion.get("configuracion") or {}
    tenia_elige8 = bool(config.get("elige8")) or any(p.get("elige8") for p in partidos)
    if not tenia_elige8:
        return False

    ordenados = sorted(partidos, key=clave_ranking_elige8)
    seleccionados = {int(p.get("num")) for p in ordenados[:8]}
    triples = {int(p.get("num")) for p in partidos if len(signos_jugados(p)) >= 3 and int(p.get("num", 0) or 0)}
    if len(triples) <= 8 and not triples.issubset(seleccionados):
        fuera = sorted(triples - seleccionados)
        raise RuntimeError(f"Elige 8 incoherente: triples fuera de la seleccion {fuera}")

    ranking = []
    for posicion, partido in enumerate(ordenados, start=1):
        num = int(partido.get("num", 0) or 0)
        signo = signo_base(partido)
        prob = prob_signo(partido, signo)
        signos = signos_jugados(partido)
        tipo = tipo_cobertura(signos)
        cubierta = probabilidad_cubierta(partido)
        elegido = num in seleccionados
        partido["elige8"] = elegido
        partido["elige8_score"] = puntuacion_elige8(partido)
        partido["elige8_probabilidad_signo"] = round(prob, 1)
        partido["elige8_probabilidad_cubierta"] = round(cubierta, 1)
        partido["elige8_probabilidad_acierto"] = round(cubierta, 1)
        partido["elige8_signo_objetivo"] = signo
        partido["elige8_tipo_cobertura"] = tipo.lower()
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
            "signos_jugados": signos,
            "tipo_cobertura": tipo,
            "probabilidad": round(prob, 1),
            "probabilidad_cubierta": round(cubierta, 1),
            "probabilidad_acierto": round(cubierta, 1),
            "score": partido["elige8_score"],
            "seleccionado": elegido,
        })

    prediccion["elige8_aprendizaje"] = {
        "version": "4.0",
        "generado_en": ahora(),
        "regla_activa": REGLA_BASE,
        "criterio": "ranking_por_probabilidad_real_de_acierto_del_signo_jugado",
        "ranking": ranking,
    }
    resumen = prediccion.setdefault("resumen", {})
    resumen["elige8_seleccionados"] = 8
    resumen["elige8_regla"] = "probabilidad_real_de_acierto"
    return True


def signos_oficiales_jornada(jornada):
    data = cargar_json(JORNADAS / f"jornada_{jornada}.json", {})
    signos = {}
    partidos = {}
    for partido in data.get("partidos", []):
        num = int(partido.get("num", 0) or 0)
        signo = normalizar_signos(partido.get("signo_oficial") or partido.get("resultado_1x2"))
        if num:
            partidos[num] = partido
        if num and signo in {"1", "X", "2"}:
            signos[num] = signo
    return signos, partidos


def evaluar_jugada(jugada):
    jornada = jugada.get("jornada")
    oficiales, partidos = signos_oficiales_jornada(jornada)
    signos = list(jugada.get("signos") or [])
    seleccionados_elige8 = [int(n) for n in jugada.get("elige8", []) if str(n).isdigit()]

    fallos = []
    pendientes = []
    aciertos_totales = 0
    aciertos_elige8 = 0
    partido_rompio = None

    for num in range(1, 15):
        jugado = normalizar_signos(signos[num - 1] if num - 1 < len(signos) else "")
        oficial = oficiales.get(num)
        partido = partidos.get(num, {})

        if not oficial:
            pendientes.append(num)
            continue

        acierto = bool(jugado and oficial in jugado)
        if acierto:
            aciertos_totales += 1
        else:
            fallos.append({
                "num": num,
                "local": partido.get("local"),
                "visitante": partido.get("visitante"),
                "jugado": jugado,
                "oficial": oficial,
            })

        if num in seleccionados_elige8:
            if acierto:
                aciertos_elige8 += 1
            elif partido_rompio is None:
                partido_rompio = {
                    "num": num,
                    "local": partido.get("local"),
                    "visitante": partido.get("visitante"),
                    "jugado": jugado,
                    "oficial": oficial,
                }

    cerrada = len(oficiales) == 14
    premios = PREMIOS_CONOCIDOS.get(jornada, {})
    if pendientes:
        regla = "Jornada parcial: esperar resultados oficiales antes de aprender reglas fuertes."
    elif partido_rompio:
        regla = (
            f"Elige 8 se rompio en el partido {partido_rompio['num']}; revisar si quedaron fuera partidos "
            "con mas probabilidad real de acierto que el partido elegido."
        )
    elif seleccionados_elige8:
        regla = "Elige 8 completo: mantener prioridad por probabilidad real de acierto."
    else:
        regla = "Jornada sin Elige 8: aprender aciertos y fallos del boleto, sin regla especifica de Elige 8."

    return {
        "jornada": jornada,
        "estado": "cerrada" if cerrada else "parcial",
        "validado_en": jugada.get("validado_en"),
        "evaluado_en": ahora(),
        "signos_jugados": signos,
        "elige8": seleccionados_elige8,
        "aciertos_totales": aciertos_totales,
        "fallos_totales": len(fallos),
        "aciertos_elige8": aciertos_elige8 if seleccionados_elige8 else None,
        "seleccionados_elige8": seleccionados_elige8,
        "partido_que_rompio_elige8": partido_rompio,
        "fallos": fallos,
        "partidos_pendientes": pendientes,
        "premio_cobrado": premios.get("premio_cobrado", 0.0),
        "premio_que_se_escapo": premios.get("premio_que_se_escapo", 0.0),
        "nota_premio": premios.get("nota", ""),
        "regla_aprendida": regla,
    }


def construir_memoria_desde_jugadas():
    data = cargar_json(JUGADAS_ARCHIVO, {"jugadas": []})
    jugadas = sorted(data.get("jugadas", []), key=lambda j: j.get("jornada") or 0)
    evaluadas = [evaluar_jugada(j) for j in jugadas if j.get("jornada")]

    cerradas = [j for j in evaluadas if j["estado"] == "cerrada"]
    con_elige8 = [j for j in cerradas if j.get("seleccionados_elige8")]
    resumen = {
        "jugadas_evaluadas": len(evaluadas),
        "jornadas_cerradas": len(cerradas),
        "aciertos_totales": sum(j["aciertos_totales"] for j in cerradas),
        "fallos_totales": sum(j["fallos_totales"] for j in cerradas),
        "elige8_evaluados": len(con_elige8),
        "aciertos_elige8": sum(j.get("aciertos_elige8") or 0 for j in con_elige8),
        "selecciones_elige8": sum(len(j.get("seleccionados_elige8") or []) for j in con_elige8),
        "premio_cobrado": round(sum(float(j.get("premio_cobrado") or 0) for j in evaluadas), 2),
        "premio_que_se_escapo": round(sum(float(j.get("premio_que_se_escapo") or 0) for j in evaluadas), 2),
    }
    if resumen["selecciones_elige8"]:
        resumen["precision_elige8"] = round(
            resumen["aciertos_elige8"] / resumen["selecciones_elige8"] * 100,
            2,
        )
    else:
        resumen["precision_elige8"] = 0.0

    memoria = {
        "version": "4.0",
        "actualizado_en": ahora(),
        "regla_activa": REGLA_BASE,
        "resumen": resumen,
        "jornadas": evaluadas,
        "reglas_aprendidas": [j["regla_aprendida"] for j in evaluadas if j.get("regla_aprendida")],
    }
    guardar_json(MEMORIA_ELIGE8, memoria)
    return memoria


def procesar_prediccion(path):
    prediccion = cargar_json(path, {})
    if not recalcular_elige8(prediccion):
        return False
    guardar_json(path, prediccion)
    return True


def main():
    tocados = []
    memoria = construir_memoria_desde_jugadas()
    tocados.append(str(MEMORIA_ELIGE8.relative_to(ROOT)))

    if PREDICCIONES.exists():
        for path in sorted(PREDICCIONES.glob("*.json")):
            if procesar_prediccion(path):
                tocados.append(str(path.relative_to(ROOT)))

    print(json.dumps({
        "estado": "ok",
        "script": "ajustar_aprendizaje_elige8.py",
        "archivos_actualizados": tocados,
        "resumen_aprendizaje": memoria.get("resumen", {}),
        "regla_activa": REGLA_BASE,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
