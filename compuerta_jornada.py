import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SIGNOS = {"1", "X", "2"}


def ahora_iso():
    return datetime.now(timezone.utc).isoformat()


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def signo_de_resultado(valor):
    match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(valor or ""))
    if not match:
        return None
    local, visitante = int(match.group(1)), int(match.group(2))
    if local > visitante:
        return "1"
    if local == visitante:
        return "X"
    return "2"


def signo_partido(partido):
    signo = str(partido.get("signo_oficial") or partido.get("signo_real") or "").strip().upper()
    if signo in SIGNOS:
        return signo
    return signo_de_resultado(partido.get("resultado"))


def estado_resultados(jornada_num, data_root=DATA):
    data_root = Path(data_root)
    jornada = cargar_json(data_root / "jornadas" / f"jornada_{int(jornada_num)}.json", None)
    if not jornada:
        return {"ok": False, "total": 0, "cerrados": 0, "faltan": ["jornada_no_cargada"]}
    partidos = []
    for partido in jornada.get("partidos", []):
        try:
            num = int(partido.get("num") or 0)
        except (TypeError, ValueError):
            num = 0
        if 1 <= num <= 14:
            partidos.append(partido)
    faltan = []
    cerrados = 0
    for partido in partidos:
        if signo_partido(partido) in SIGNOS:
            cerrados += 1
        else:
            faltan.append(partido.get("num"))
    return {"ok": len(partidos) >= 14 and cerrados >= 14 and not faltan, "total": len(partidos), "cerrados": cerrados, "faltan": faltan}


def items_jornada(path, jornada_num, clave):
    data = cargar_json(path, {clave: []})
    salida = []
    for item in data.get(clave, []) if isinstance(data, dict) else []:
        try:
            if int(item.get("jornada") or 0) == int(jornada_num):
                salida.append(item)
        except (TypeError, ValueError):
            continue
    return salida


def estado_aprendizaje(jornada_num, data_root=DATA):
    memoria = Path(data_root) / "memoria_ia"
    revisiones = items_jornada(memoria / "revisiones_prediccion_resultado.json", jornada_num, "revisiones")
    diario = items_jornada(memoria / "diario_aprendizaje.json", jornada_num, "entradas")
    metricas = cargar_json(memoria / "metricas_probabilisticas.json", {})
    fiabilidad = cargar_json(memoria / "fiabilidad_equipos.json", {})
    pesos = cargar_json(memoria / "pesos_dinamicos.json", {})
    checks = {
        "revisiones_prediccion_resultado": len(revisiones) >= 14,
        "diario_aprendizaje": len(diario) >= 14,
        "metricas_probabilisticas": int(metricas.get("partidos_evaluados") or 0) >= len(revisiones) >= 14,
        "fiabilidad_equipos": bool(fiabilidad.get("equipos") or {}) and bool(fiabilidad.get("generado_en")),
        "pesos_dinamicos": bool(pesos.get("pesos") or {}) and bool(pesos.get("generado_en")),
    }
    faltan = [nombre for nombre, ok in checks.items() if not ok]
    return {"ok": not faltan, "faltan": faltan, "revisiones": len(revisiones), "diario": len(diario)}


def estado_compuerta(jornada_objetivo, data_root=DATA):
    try:
        jornada_objetivo = int(jornada_objetivo or 0)
    except (TypeError, ValueError):
        jornada_objetivo = 0
    anterior = jornada_objetivo - 1 if jornada_objetivo else 0
    if anterior <= 0:
        return {"jornada_objetivo": jornada_objetivo, "jornada_anterior": anterior, "en_espera": False, "estado_prediccion_actual": "jugable", "motivo": "", "actualizado_en": ahora_iso()}
    resultados = estado_resultados(anterior, data_root)
    if not resultados["ok"]:
        return {
            "jornada_objetivo": jornada_objetivo,
            "jornada_anterior": anterior,
            "en_espera": True,
            "estado_jornada_anterior": "pendiente",
            "resultados_completos_anterior": False,
            "aprendizaje_aplicado_anterior": False,
            "estado_prediccion_actual": "pendiente_cierre_anterior",
            "motivo": f"La jornada {anterior} solo tiene {resultados['cerrados']} de 14 resultados oficiales. La jornada {jornada_objetivo} queda pendiente hasta completar resultados y aprendizaje de la {anterior}.",
            "detalle_cierre_anterior": resultados,
            "actualizado_en": ahora_iso(),
        }
    aprendizaje = estado_aprendizaje(anterior, data_root)
    if not aprendizaje["ok"]:
        return {
            "jornada_objetivo": jornada_objetivo,
            "jornada_anterior": anterior,
            "en_espera": True,
            "estado_jornada_anterior": "cerrada",
            "resultados_completos_anterior": True,
            "aprendizaje_aplicado_anterior": False,
            "estado_prediccion_actual": "pendiente_cierre_anterior",
            "motivo": f"La jornada {anterior} esta cerrada, pero falta aprendizaje: {', '.join(aprendizaje['faltan'])}.",
            "detalle_aprendizaje_anterior": aprendizaje,
            "actualizado_en": ahora_iso(),
        }
    return {"jornada_objetivo": jornada_objetivo, "jornada_anterior": anterior, "en_espera": False, "estado_jornada_anterior": "aprendida", "resultados_completos_anterior": True, "aprendizaje_aplicado_anterior": True, "estado_prediccion_actual": "jugable", "motivo": "", "actualizado_en": ahora_iso()}
