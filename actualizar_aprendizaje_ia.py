import json
import re
from collections import Counter
from pathlib import Path


DATA = Path("data")
JORNADAS = DATA / "jornadas"
OUT = DATA / "aprendizaje_ia.json"
QUINIELAS_JUGADAS = DATA / "quinielas_jugadas.json"
QUINIELAS_GENERADAS_IA = DATA / "quinielas_generadas_ia.json"
HISTORIAL_QUINIELAS = DATA / "historial_quinielas.json"


def cargar_json(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def signo_resultado(resultado):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(resultado or ""))
    if not m:
        return None
    gl, gv = int(m.group(1)), int(m.group(2))
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def signos_pronostico(valor):
    texto = str(valor or "").strip().upper()
    return {signo for signo in ("1", "X", "2") if signo in texto}


def acierta(pron, real):
    return real in signos_pronostico(pron)


def tipo_pronostico(valor):
    total = len(signos_pronostico(valor))
    if total >= 3:
        return "TRIPLE"
    if total == 2:
        return "DOBLE"
    if total == 1:
        return "FIJO"
    return "NO_VALIDO"


def pronostico_valido(valor):
    texto = str(valor or "").strip().upper()
    if not texto or texto in {"NO JUGADA", "NO VALIDADA", "PENDIENTE"}:
        return False
    return bool(signos_pronostico(texto))


def extraer_signos_jugada(valor):
    if isinstance(valor, list):
        return [str(s).strip().upper() for s in valor if str(s).strip()]
    texto = str(valor or "").strip().upper()
    if not texto or texto in {"NO VALIDADA", "NO JUGADA", "PENDIENTE"}:
        return []
    partes = [p for p in texto.split() if p]
    if len(partes) > 1:
        return partes
    if re.fullmatch(r"[12X]{14}", texto):
        return list(texto)
    return []


def normalizar_jugada(jugada, origen):
    jornada = jugada.get("jornada")
    jornada_num = int(jornada) if str(jornada or "").isdigit() else None
    signos = extraer_signos_jugada(jugada.get("signos") or jugada.get("nuestra_quiniela"))
    if jornada_num and len(signos) >= 14:
        return jornada_num, {
            "signos": signos[:14],
            "pleno15": str(jugada.get("pleno15") or jugada.get("pleno15_nuestro") or "").strip(),
            "elige8": [int(x) for x in jugada.get("elige8", []) if str(x).isdigit()],
            "origen": jugada.get("origen") or origen,
        }
    return None, None


def cargar_jugadas_validadas():
    jugadas = {}
    memoria = cargar_json(QUINIELAS_JUGADAS, {"jugadas": []})
    generadas_ia = cargar_json(QUINIELAS_GENERADAS_IA, {"jugadas": []})
    historial = cargar_json(HISTORIAL_QUINIELAS, {"jornadas": []})
    for jugada in memoria.get("jugadas", []):
        jornada, normalizada = normalizar_jugada(jugada, "data/quinielas_jugadas.json")
        if normalizada:
            jugadas[jornada] = normalizada
    for jugada in generadas_ia.get("jugadas", []):
        jornada, normalizada = normalizar_jugada(jugada, "data/quinielas_generadas_ia.json")
        if normalizada and jornada not in jugadas:
            jugadas[jornada] = normalizada
    for jugada in historial.get("jornadas", []):
        jornada, normalizada = normalizar_jugada(jugada, "data/historial_quinielas.json")
        if normalizada and jornada not in jugadas:
            jugadas[jornada] = normalizada
    return jugadas


def clasificar_fallo(pron, real):
    signos = signos_pronostico(pron)
    if "X" not in signos and real == "X":
        return "No cubrio empate"
    if len(signos) == 1:
        return "Fijo fallado"
    if len(signos) == 2:
        return "Doble insuficiente"
    return "Triple fallado"


def numero_jornada(path):
    m = re.search(r"(\d+)", path.stem)
    return int(m.group(1)) if m else 0


def porcentaje(parte, total):
    return round(float(parte) / max(float(total), 1.0) * 100, 2)


def precision(aciertos, total):
    return porcentaje(aciertos, total)


def resumen_por_counter(aciertos, totales):
    salida = {}
    for clave in sorted(set(aciertos) | set(totales)):
        total = int(totales.get(clave, 0))
        ok = int(aciertos.get(clave, 0))
        salida[clave] = {
            "total": total,
            "aciertos": ok,
            "fallos": max(total - ok, 0),
            "precision": precision(ok, total),
        }
    return salida


def generar_ajuste_motor(resumen):
    total = int(resumen.get("partidos_revisados") or 0)
    fallos = int(resumen.get("fallos") or 0)
    fallos_por_tipo = resumen.get("fallos_por_tipo") or {}
    no_cubrio_empate = int(fallos_por_tipo.get("No cubrio empate") or 0)
    fijo_fallado = int(fallos_por_tipo.get("Fijo fallado") or 0)
    doble_insuficiente = int(fallos_por_tipo.get("Doble insuficiente") or 0)

    if total < 28:
        muestra = "baja"
    elif total < 84:
        muestra = "media"
    else:
        muestra = "suficiente"

    no_cubrio_empate_sobre_fallos = porcentaje(no_cubrio_empate, fallos)
    no_cubrio_empate_sobre_total = porcentaje(no_cubrio_empate, total)
    fijo_fallado_sobre_fallos = porcentaje(fijo_fallado, fallos)
    fijo_fallado_sobre_total = porcentaje(fijo_fallado, total)
    doble_insuficiente_sobre_total = porcentaje(doble_insuficiente, total)

    if muestra == "baja":
        boost_empate = 0.0
        riesgo_fijo = 0.0
        riesgo_triple = 0.0
    else:
        boost_empate = round(min(
            6.0,
            max(0.0, no_cubrio_empate_sobre_fallos - 15.0) * 0.18
            + max(0.0, no_cubrio_empate_sobre_total - 5.0) * 0.40,
        ), 2)
        riesgo_fijo = round(min(
            18.0,
            max(0.0, fijo_fallado_sobre_total - 12.0) * 0.80
            + max(0.0, fijo_fallado_sobre_fallos - 35.0) * 0.20,
        ), 2)
        riesgo_triple = round(min(
            10.0,
            max(0.0, doble_insuficiente_sobre_total - 4.0) * 0.90,
        ), 2)

    reglas = []
    if boost_empate:
        reglas.append("Subir X en partidos de margen corto o tendencia de empate porque el historial propio dejo empates sin cubrir.")
    if riesgo_fijo:
        reglas.append("Penalizar fijo limpio si el favorito no supera un umbral fuerte de probabilidad/margen.")
    if riesgo_triple:
        reglas.append("Elevar riesgo de triple cuando el tercer signo sigue vivo y los dobles propios fueron insuficientes.")
    if not reglas:
        reglas.append("Muestra todavia insuficiente o sin sesgo fuerte: mantener aprendizaje conservador.")

    return {
        "version": "1.0",
        "partidos_base": total,
        "muestra": muestra,
        "tasas_error": {
            "fallos_total_pct": porcentaje(fallos, total),
            "no_cubrio_empate_sobre_fallos_pct": no_cubrio_empate_sobre_fallos,
            "no_cubrio_empate_sobre_total_pct": no_cubrio_empate_sobre_total,
            "fijo_fallado_sobre_fallos_pct": fijo_fallado_sobre_fallos,
            "fijo_fallado_sobre_total_pct": fijo_fallado_sobre_total,
            "doble_insuficiente_sobre_total_pct": doble_insuficiente_sobre_total,
        },
        "boost_empate_zona_riesgo": boost_empate,
        "riesgo_extra_fijo_fragil": riesgo_fijo,
        "riesgo_extra_triple_insuficiente": riesgo_triple,
        "min_dobles_auto": 3 if muestra != "baja" and fijo_fallado_sobre_total >= 15 else 0,
        "min_triples_auto": 1 if muestra != "baja" and doble_insuficiente_sobre_total >= 6 else 0,
        "umbral_fijo_seguro": 58 if muestra != "baja" and fijo_fallado_sobre_total >= 15 else 54,
        "reglas": reglas,
    }


def resumen_vacio():
    return {
        "jornadas_revisadas": 0,
        "partidos_revisados": 0,
        "aciertos": 0,
        "fallos": 0,
        "fallos_por_tipo": Counter(),
        "fallos_por_signo_real": Counter(),
        "signos_omitidos_en_fallo": Counter(),
        "totales_por_tipo": Counter(),
        "aciertos_por_tipo": Counter(),
        "totales_por_signo_real": Counter(),
        "aciertos_por_signo_real": Counter(),
        "detalle": [],
    }


def registrar_revision(resumen, jornada_num, partido, pron, real, origen):
    ok = acierta(pron, real)
    tipo = tipo_pronostico(pron)
    signos = signos_pronostico(pron)
    resumen["partidos_revisados"] += 1
    resumen["totales_por_tipo"][tipo] += 1
    resumen["totales_por_signo_real"][real] += 1

    if ok:
        resumen["aciertos"] += 1
        resumen["aciertos_por_tipo"][tipo] += 1
        resumen["aciertos_por_signo_real"][real] += 1
    else:
        resumen["fallos"] += 1
        resumen["fallos_por_tipo"][clasificar_fallo(pron, real)] += 1
        resumen["fallos_por_signo_real"][real] += 1
        if real not in signos:
            resumen["signos_omitidos_en_fallo"][real] += 1

    resumen["detalle"].append({
        "jornada": jornada_num,
        "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
        "pronostico": pron,
        "tipo_pronostico": tipo,
        "resultado": partido.get("resultado"),
        "signo_real": real,
        "signos_cubiertos": "".join(signo for signo in ("1", "X", "2") if signo in signos),
        "signo_omitido": real if real not in signos else "",
        "acierto": ok,
        "origen": origen,
    })


def construir_salida(resumen, fuentes_jugadas):
    total = max(resumen["partidos_revisados"], 1)
    salida = {
        "version": "1.1",
        "precision": round(resumen["aciertos"] / total * 100, 2),
        "jornadas_revisadas": resumen["jornadas_revisadas"],
        "partidos_revisados": resumen["partidos_revisados"],
        "aciertos": resumen["aciertos"],
        "fallos": resumen["fallos"],
        "fallos_por_tipo": dict(resumen["fallos_por_tipo"]),
        "fallos_por_signo_real": dict(resumen["fallos_por_signo_real"]),
        "signos_omitidos_en_fallo": dict(resumen["signos_omitidos_en_fallo"]),
        "precision_por_tipo": resumen_por_counter(resumen["aciertos_por_tipo"], resumen["totales_por_tipo"]),
        "precision_por_signo_real": resumen_por_counter(
            resumen["aciertos_por_signo_real"],
            resumen["totales_por_signo_real"],
        ),
        "detalle": resumen["detalle"][-250:],
        "ajustes_recomendados": [
            "Subir peso del empate si aumenta No cubrio empate.",
            "Reducir fijos en partidos con margen probabilistico bajo.",
            "Asignar triples a partidos con historial de sorpresa alta.",
        ],
        "fuentes_jugadas": dict(fuentes_jugadas),
    }
    salida["ajuste_motor"] = generar_ajuste_motor(salida)
    return salida


def main():
    resumen = resumen_vacio()
    jugadas = cargar_jugadas_validadas()
    fuentes_jugadas = Counter(jugada.get("origen") or "desconocido" for jugada in jugadas.values())
    for path in sorted(JORNADAS.glob("jornada_*.json"), key=numero_jornada):
        data = cargar_json(path, {})
        revisados_jornada = 0
        jornada_num = data.get("jornada") or path.stem
        jugada = jugadas.get(data.get("jornada"))
        for idx, partido in enumerate(data.get("partidos", [])):
            real = signo_resultado(partido.get("resultado"))
            if jugada and idx < len(jugada["signos"]):
                pron = jugada["signos"][idx]
                origen = jugada.get("origen") or "data/quinielas_jugadas.json"
            else:
                pron = partido.get("signo_nuestro") or partido.get("signo_final") or partido.get("pronostico_ia")
                origen = "partido"
            if not real or not pronostico_valido(pron):
                continue
            registrar_revision(resumen, jornada_num, partido, pron, real, origen)
            revisados_jornada += 1
        if revisados_jornada:
            resumen["jornadas_revisadas"] += 1

    salida = construir_salida(resumen, fuentes_jugadas)
    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Aprendizaje IA generado: {OUT}")


if __name__ == "__main__":
    main()
