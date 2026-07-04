import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SNAPSHOTS = DATA / "backtesting" / "pre_cierre"
JORNADAS = DATA / "jornadas"
OUT = DATA / "memoria_ia" / "valor_de_senales.json"

SIGNOS = ("1", "X", "2")
MUESTRA_MINIMA = 100
DIFERENCIA_RELEVANTE = 3.0


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def signo_oficial(partido):
    signo = str(partido.get("signo_oficial") or partido.get("signo_real") or "").strip().upper()
    if signo in SIGNOS:
        return signo
    resultado = str(partido.get("resultado") or "")
    if "-" not in resultado:
        return ""
    try:
        gl, gv = [int(x.strip()) for x in resultado.split("-", 1)]
    except ValueError:
        return ""
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def indice_resultados(jornada):
    salida = {}
    for partido in jornada.get("partidos", []):
        try:
            num = int(partido.get("num") or 0)
        except (TypeError, ValueError):
            continue
        signo = signo_oficial(partido)
        if 1 <= num <= 14 and signo:
            salida[num] = signo
    return salida


def normalizar_probs(probs):
    valores = {}
    for signo in SIGNOS:
        try:
            valores[signo] = max(float(probs.get(signo, 0.0)), 0.0)
        except (TypeError, ValueError):
            valores[signo] = 0.0
    total = sum(valores.values())
    if total <= 0:
        return {"1": 1 / 3, "X": 1 / 3, "2": 1 / 3}
    return {signo: valores[signo] / total for signo in SIGNOS}


def top_signo(probs):
    return max(SIGNOS, key=lambda s: probs.get(s, 0.0))


# Señales del motor sobre las que ya tenemos rastro por partido (ver
# motor_prediccion_quiniela.py). Cada función devuelve True/False según si esa
# señal estaba activa para ese partido concreto en el momento de predecir.
SENALES = {
    "contexto_competitivo_motivacion": lambda p: bool(p.get("alertas_motivacion")),
    "datos_profesionales_cuotas": lambda p: bool(
        ((p.get("trazabilidad_datos") or {}).get("datos_profesionales") or {}).get("cuotas")
    ),
    "refuerzo_sorpresas_mercado": lambda p: bool(
        ((p.get("ajuste_motivacion") or {}).get("refuerzo_memoria_sorpresas_mercado") or {}).get("activo")
    ),
}


def evaluaciones_snapshots():
    evaluaciones = []
    if not SNAPSHOTS.exists():
        return evaluaciones
    for path in sorted(SNAPSHOTS.glob("jornada_*.json")):
        snap = cargar_json(path, {})
        pred = snap.get("prediccion") or snap
        try:
            jornada_num = int(snap.get("jornada") or pred.get("jornada") or 0)
        except (TypeError, ValueError):
            continue
        resultados = indice_resultados(cargar_json(JORNADAS / f"jornada_{jornada_num}.json", {}))
        for partido in pred.get("partidos", []):
            try:
                num = int(partido.get("num") or 0)
            except (TypeError, ValueError):
                continue
            real = resultados.get(num)
            probs_crudas = partido.get("probabilidades") or {}
            if not real or not probs_crudas:
                continue
            probs = normalizar_probs(probs_crudas)
            evaluaciones.append({
                "jornada": jornada_num,
                "num": num,
                "acierto_top": top_signo(probs) == real,
                "brier": sum((probs[s] - (1.0 if s == real else 0.0)) ** 2 for s in SIGNOS),
                "senales": {nombre: bool(fn(partido)) for nombre, fn in SENALES.items()},
            })
    return evaluaciones


def resumen_grupo(items):
    total = len(items)
    if not total:
        return {"partidos": 0, "precision": None, "brier_medio": None}
    aciertos = sum(1 for it in items if it["acierto_top"])
    return {
        "partidos": total,
        "precision": round(aciertos / total * 100, 2),
        "brier_medio": round(sum(it["brier"] for it in items) / total, 4),
    }


def evaluar_senal(evaluaciones, nombre):
    con = [ev for ev in evaluaciones if ev["senales"].get(nombre)]
    sin = [ev for ev in evaluaciones if not ev["senales"].get(nombre)]
    resumen_con = resumen_grupo(con)
    resumen_sin = resumen_grupo(sin)

    if resumen_con["partidos"] < MUESTRA_MINIMA:
        veredicto = "sin_muestra_suficiente"
        conclusion = (
            f"Solo {resumen_con['partidos']} partidos con esta senal activa hasta ahora "
            f"(hacen falta {MUESTRA_MINIMA}); todavia no hay evidencia suficiente para decidir si ayuda o no."
        )
        diferencia = None
    else:
        diferencia = round((resumen_con["precision"] or 0) - (resumen_sin["precision"] or 0), 2)
        if abs(diferencia) < DIFERENCIA_RELEVANTE:
            veredicto = "sin_diferencia_relevante"
            conclusion = (
                f"La precision con esta senal activa ({resumen_con['precision']}%) y sin ella "
                f"({resumen_sin['precision']}%) es practicamente igual: no hay evidencia de que aporte."
            )
        elif diferencia > 0:
            veredicto = "ayuda"
            conclusion = (
                f"Con esta senal activa la precision sube {diferencia:+.2f} puntos "
                f"({resumen_con['precision']}% frente a {resumen_sin['precision']}% sin ella)."
            )
        else:
            veredicto = "perjudica"
            conclusion = (
                f"Con esta senal activa la precision BAJA {diferencia:+.2f} puntos "
                f"({resumen_con['precision']}% frente a {resumen_sin['precision']}% sin ella): revisar por que."
            )

    return {
        "con_senal": resumen_con,
        "sin_senal": resumen_sin,
        "diferencia_precision": diferencia,
        "veredicto": veredicto,
        "conclusion": conclusion,
    }


def main():
    evaluaciones = evaluaciones_snapshots()
    resultado = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": (
            "Compara la precision real de los partidos con cada senal del motor activa frente a "
            "sin ella, usando solo snapshots inmutables guardados antes de conocer el resultado. "
            f"No se saca ninguna conclusion por debajo de {MUESTRA_MINIMA} partidos con la senal activa."
        ),
        "partidos_evaluados_total": len(evaluaciones),
        "senales": {nombre: evaluar_senal(evaluaciones, nombre) for nombre in SENALES},
    }
    guardar_json(OUT, resultado)
    print(f"Valor de senales evaluado: {len(evaluaciones)} partidos analizados -> {OUT}")


if __name__ == "__main__":
    main()
