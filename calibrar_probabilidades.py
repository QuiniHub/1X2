import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORIA = DATA / "memoria_ia"
SNAPSHOTS = DATA / "backtesting" / "pre_cierre"
JORNADAS = DATA / "jornadas"
PREDICCIONES = DATA / "predicciones"
OUT = MEMORIA / "calibracion_probabilidades.json"

SIGNOS = ("1", "X", "2")


def ahora():
    return datetime.now(timezone.utc).isoformat()


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
        if 1 <= num <= 14 and signo in SIGNOS:
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
    if total > 1.5:
        return {signo: valores[signo] / total for signo in SIGNOS}
    return {signo: valores[signo] / total for signo in SIGNOS}


def top_signo(probs):
    return max(SIGNOS, key=lambda s: probs.get(s, 0.0))


def bucket(prob):
    pct = int(prob * 100)
    inicio = max(0, min(90, (pct // 10) * 10))
    return f"{inicio}-{inicio + 10}"


def evaluar_partido(partido, real, jornada, fuente):
    probs = normalizar_probs(partido.get("probabilidades") or {})
    top = top_signo(probs)
    brier = sum((probs[s] - (1.0 if s == real else 0.0)) ** 2 for s in SIGNOS)
    logloss = -math.log(max(probs[real], 1e-9))
    return {
        "jornada": jornada,
        "num": partido.get("num"),
        "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
        "fuente": fuente,
        "real": real,
        "top": top,
        "acierto_top": top == real,
        "prob_top": round(probs[top] * 100, 2),
        "prob_real": round(probs[real] * 100, 2),
        "bucket_top": bucket(probs[top]),
        "brier": brier,
        "logloss": logloss,
        "competicion": partido.get("competicion_resuelta") or partido.get("competicion") or "desconocida",
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
            if real in SIGNOS and partido.get("probabilidades"):
                evaluaciones.append(evaluar_partido(partido, real, jornada_num, str(path.relative_to(ROOT))))
    return evaluaciones


def resumen_bucket(evaluaciones):
    grupos = defaultdict(list)
    for ev in evaluaciones:
        grupos[ev["bucket_top"]].append(ev)
    salida = {}
    for nombre, items in sorted(grupos.items()):
        total = len(items)
        aciertos = sum(1 for ev in items if ev["acierto_top"])
        prob_media = sum(ev["prob_top"] for ev in items) / max(total, 1)
        precision_real = aciertos / max(total, 1) * 100
        salida[nombre] = {
            "total": total,
            "prob_top_media": round(prob_media, 2),
            "precision_real": round(precision_real, 2),
            "desviacion_calibracion": round(precision_real - prob_media, 2),
            "muestra_suficiente": total >= 30,
        }
    return salida


def resumen_competicion(evaluaciones):
    grupos = defaultdict(list)
    for ev in evaluaciones:
        grupos[ev.get("competicion") or "desconocida"].append(ev)
    salida = {}
    for nombre, items in sorted(grupos.items()):
        total = len(items)
        salida[nombre] = resumen_global(items)
        salida[nombre]["muestra_suficiente"] = total >= 100
    return salida


def resumen_global(evaluaciones):
    total = len(evaluaciones)
    if not total:
        return {
            "partidos": 0,
            "precision_top": None,
            "brier_medio": None,
            "logloss_medio": None,
            "muestra": "sin_datos",
        }
    aciertos = sum(1 for ev in evaluaciones if ev["acierto_top"])
    brier = sum(ev["brier"] for ev in evaluaciones) / total
    logloss = sum(ev["logloss"] for ev in evaluaciones) / total
    muestra = "baja" if total < 100 else "media" if total < 500 else "suficiente"
    return {
        "partidos": total,
        "precision_top": round(aciertos / total * 100, 2),
        "brier_medio": round(brier, 4),
        "logloss_medio": round(logloss, 4),
        "muestra": muestra,
    }


def anotar_prediccion_actual(calibracion):
    path = PREDICCIONES / "ultima_prediccion.json"
    data = cargar_json(path, {})
    if not data:
        return False
    antes = json.dumps(data, ensure_ascii=False, sort_keys=True)
    data["calibracion_probabilidades"] = {
        "generado_en": calibracion.get("generado_en"),
        "estado": calibracion.get("estado"),
        "muestra": calibracion.get("global", {}).get("muestra"),
        "partidos_evaluados": calibracion.get("global", {}).get("partidos"),
        "brier_medio": calibracion.get("global", {}).get("brier_medio"),
        "logloss_medio": calibracion.get("global", {}).get("logloss_medio"),
        "criterio": "No presentar porcentajes como plenamente fiables si la muestra es baja.",
    }
    despues = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if antes != despues:
        guardar_json(path, data)
        jornada = data.get("jornada")
        if jornada:
            guardar_json(PREDICCIONES / f"jornada_{jornada}.json", data)
        return True
    return False


def main():
    evaluaciones = evaluaciones_snapshots()
    global_resumen = resumen_global(evaluaciones)
    estado = "sin_muestra" if not evaluaciones else "muestra_baja" if len(evaluaciones) < 100 else "calibracion_operativa"
    salida = {
        "version": "1.0",
        "generado_en": ahora(),
        "objetivo": "probabilidades calibradas con predicciones pre-cierre y resultados oficiales",
        "estado": estado,
        "global": global_resumen,
        "por_bucket_top": resumen_bucket(evaluaciones),
        "por_competicion": resumen_competicion(evaluaciones),
        "detalle_reciente": evaluaciones[-250:],
        "reglas": [
            "No recalibrar automaticamente con menos de 100 partidos evaluados.",
            "No calibrar una competicion concreta con menos de 100 partidos de esa competicion.",
            "Usar Brier y log loss para comparar versiones del motor.",
        ],
    }
    guardar_json(OUT, salida)
    anoto = anotar_prediccion_actual(salida)
    print(f"Calibracion probabilistica: {len(evaluaciones)} partidos evaluados. Prediccion anotada: {anoto}.")


if __name__ == "__main__":
    main()
