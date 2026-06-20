import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SIGNOS = {"1", "X", "2"}


def utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def signo_resultado(resultado):
    match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(resultado or ""))
    if not match:
        return None
    local, visitante = int(match.group(1)), int(match.group(2))
    if local > visitante:
        return "1"
    if local == visitante:
        return "X"
    return "2"


def signo_real_partido(partido):
    signo = str(partido.get("signo_oficial") or partido.get("signo_real") or "").strip().upper()
    if signo in SIGNOS:
        return signo
    return signo_resultado(partido.get("resultado"))


def partidos_principales(jornada):
    partidos = []
    for partido in (jornada or {}).get("partidos", []):
        try:
            num = int(partido.get("num") or 0)
        except (TypeError, ValueError):
            num = 0
        if 1 <= num <= 14:
            partidos.append(partido)
    return partidos


def resultados_completos_jornada(jornada_num, data_root=DATA):
    data_root = Path(data_root)
    jornada = cargar_json(data_root / "jornadas" / f"jornada_{int(jornada_num)}.json", None)
    if not jornada:
        return {
            "completa": False,
            "partidos_total": 0,
            "partidos_con_resultado": 0,
            "faltantes": ["jornada_no_cargada"],
        }

    partidos = partidos_principales(jornada)
    faltantes = []
    con_resultado = 0
    for partido in partidos:
        signo = signo_real_partido(partido)
        if signo in SIGNOS:
            con_resultado += 1
        else:
            faltantes.append(partido.get("num"))

    completa = len(partidos) >= 14 and con_resultado >= 14 and not faltantes
    return {
        "completa": completa,
        "partidos_total": len(partidos),
        "partidos_con_resultado": con_resultado,
        "faltantes": faltantes,
    }


def revisiones_de_jornada(jornada_num, data_root=DATA):
    revisiones = cargar_json(
        Path(data_root) / "memoria_ia" / "revisiones_prediccion_resultado.json",
        {"revisiones": []},
    )
    salida = []
    for item in revisiones.get("revisiones", []) if isinstance(revisiones, dict) else []:
        try:
            if int(item.get("jornada") or 0) == int(jornada_num):
                salida.append(item)
        except (TypeError, ValueError):
            continue
    return salida


def entradas_diario_de_jornada(jornada_num, data_root=DATA):
    diario = cargar_json(Path(data_root) / "memoria_ia" / "diario_aprendizaje.json", {"entradas": []})
    salida = []
    for item in diario.get("entradas", []) if isinstance(diario, dict) else []:
        try:
            if int(item.get("jornada") or 0) == int(jornada_num):
                salida.append(item)
        except (TypeError, ValueError):
            continue
    return salida


def aprendizaje_aplicado_jornada(jornada_num, data_root=DATA):
    data_root = Path(data_root)
    revisiones = revisiones_de_jornada(jornada_num, data_root)
    diario = entradas_diario_de_jornada(jornada_num, data_root)
    metricas = cargar_json(data_root / "memoria_ia" / "metricas_probabilisticas.json", {})
    fiabilidad = cargar_json(data_root / "memoria_ia" / "fiabilidad_equipos.json", {})
    pesos = cargar_json(data_root / "memoria_ia" / "pesos_dinamicos.json", {})

    metricas_ok = int(metricas.get("partidos_evaluados") or 0) >= len(revisiones) >= 14
    fiabilidad_ok = bool((fiabilidad.get("equipos") or {})) and bool(fiabilidad.get("generado_en"))
    pesos_ok = bool((pesos.get("pesos") or {})) and bool(pesos.get("generado_en"))
    revisiones_ok = len(revisiones) >= 14
    diario_ok = len(diario) >= 14

    ok = all([revisiones_ok, diario_ok, metricas_ok, fiabilidad_ok, pesos_ok])
    faltan = []
    if not revisiones_ok:
        faltan.append("revisiones_prediccion_resultado")
    if not diario_ok:
        faltan.append("diario_aprendizaje")
    if not metricas_ok:
        faltan.append("metricas_probabilisticas")
    if not fiabilidad_ok:
        faltan.append("fiabilidad_equipos")
    if not pesos_ok:
        faltan.append("pesos_dinamicos")

    return {
        "aprendida": ok,
        "revisiones": len(revisiones),
        "entradas_diario": len(diario),
        "metricas_partidos_evaluados": int(metricas.get("partidos_evaluados") or 0),
        "fiabilidad_equipos": len((fiabilidad.get("equipos") or {})),
        "pesos_generado_en": pesos.get("generado_en"),
        "faltan": faltan,
    }


def estado_bloqueo_jornada(jornada_objetivo, data_root=DATA):
    try:
        jornada_objetivo = int(jornada_objetivo or 0)
    except (TypeError, ValueError):
        jornada_objetivo = 0

    jornada_anterior = jornada_objetivo - 1 if jornada_objetivo else 0
    if jornada_anterior <= 0:
        return {
            "jornada_objetivo": jornada_objetivo,
            "jornada_anterior": jornada_anterior,
            "estado_jornada_anterior": "sin_anterior",
            "resultados_completos_anterior": True,
            "aprendizaje_aplicado_anterior": True,
            "estado_prediccion_actual": "jugable",
            "bloqueada": False,
            "motivo_bloqueo": "",
            "actualizado_en": utcnow_iso(),
        }

    cierre = resultados_completos_jornada(jornada_anterior, data_root)
    aprendizaje = aprendizaje_aplicado_jornada(jornada_anterior, data_root) if cierre["completa"] else {
        "aprendida": False,
        "faltan": ["resultados_completos"],
    }

    if not cierre["completa"]:
        estado_anterior = "pendiente"
        bloqueada = True
        motivo = (
            f"La jornada {jornada_anterior} no tiene 14 resultados oficiales completos "
            f"({cierre['partidos_con_resultado']}/{max(cierre['partidos_total'], 14)})."
        )
    elif not aprendizaje.get("aprendida"):
        estado_anterior = "cerrada"
        bloqueada = True
        motivo = (
            f"La jornada {jornada_anterior} esta cerrada, pero aun falta aprendizaje: "
            f"{', '.join(aprendizaje.get('faltan') or [])}."
        )
    else:
        estado_anterior = "aprendida"
        bloqueada = False
        motivo = ""

    return {
        "jornada_objetivo": jornada_objetivo,
        "jornada_anterior": jornada_anterior,
        "estado_jornada_anterior": estado_anterior,
        "resultados_completos_anterior": bool(cierre["completa"]),
        "aprendizaje_aplicado_anterior": bool(aprendizaje.get("aprendida")),
        "estado_prediccion_actual": "bloqueada" if bloqueada else "jugable",
        "bloqueada": bloqueada,
        "motivo_bloqueo": motivo,
        "detalle_cierre_anterior": cierre,
        "detalle_aprendizaje_anterior": aprendizaje,
        "actualizado_en": utcnow_iso(),
    }
