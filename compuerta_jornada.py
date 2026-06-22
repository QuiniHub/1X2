import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SIGNOS = {"1", "X", "2"}
ESTADOS_PREDICCION = {"bloqueada", "aprendiendo", "lista_para_publicar", "publicada"}


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
    historial_permanente = cargar_json(memoria / "historial_permanente.json", {})
    rendimiento = cargar_json(memoria / "rendimiento_jornadas.json", {})
    perfiles = cargar_json(memoria / "perfiles_equipos.json", {})
    jornada_historial = (historial_permanente.get("jornadas") or {}).get(str(int(jornada_num)))
    jornada_rendimiento = (rendimiento.get("jornadas") or {}).get(str(int(jornada_num)))
    checks = {
        "revisiones_prediccion_resultado": len(revisiones) >= 14,
        "diario_aprendizaje": len(diario) >= 14,
        "metricas_probabilisticas": int(metricas.get("partidos_evaluados") or 0) >= len(revisiones) >= 14,
        "fiabilidad_equipos": bool(fiabilidad.get("equipos") or {}) and bool(fiabilidad.get("generado_en")),
        "pesos_dinamicos": bool(pesos.get("pesos") or {}) and bool(pesos.get("generado_en")),
        "historial_permanente": bool(jornada_historial and int(jornada_historial.get("cerrados") or 0) >= 14),
        "rendimiento_jornadas": bool(jornada_rendimiento and int(jornada_rendimiento.get("partidos_cerrados") or 0) >= 14),
        "perfiles_equipos": bool((perfiles.get("equipos") or {}) and perfiles.get("generado_en")),
    }
    faltan = [nombre for nombre, ok in checks.items() if not ok]
    return {"ok": not faltan, "faltan": faltan, "revisiones": len(revisiones), "diario": len(diario)}


def respuesta_compuerta(
    jornada_objetivo,
    jornada_anterior,
    estado,
    motivo="",
    resultados=None,
    aprendizaje=None,
):
    if estado not in ESTADOS_PREDICCION:
        estado = "bloqueada"
    permitida = estado in {"lista_para_publicar", "publicada"}
    salida = {
        "jornada_objetivo": jornada_objetivo,
        "jornada_anterior": jornada_anterior,
        "prediccion_permitida": permitida,
        "motivo": motivo,
        "publicar_solo_boleto": not permitida,
        "publicar_prediccion": permitida,
        "estado": estado,
        "estado_prediccion_actual": estado,
        "en_espera": not permitida,
        "resultados_completos_anterior": bool(resultados and resultados.get("ok")) if jornada_anterior > 0 else True,
        "aprendizaje_aplicado_anterior": bool(aprendizaje and aprendizaje.get("ok")) if jornada_anterior > 0 else True,
        "actualizado_en": ahora_iso(),
    }
    if resultados is not None:
        salida["detalle_cierre_anterior"] = resultados
        salida["estado_jornada_anterior"] = "cerrada" if resultados.get("ok") else "pendiente"
    if aprendizaje is not None:
        salida["detalle_aprendizaje_anterior"] = aprendizaje
        if aprendizaje.get("ok"):
            salida["estado_jornada_anterior"] = "aprendida"
    return salida


def normalizar_estado_publicacion(prediccion):
    data = dict(prediccion or {})
    disponible = data.get("prediccion_disponible") is not False
    estado = str(data.get("estado") or "").strip().lower()
    if estado not in ESTADOS_PREDICCION:
        if not disponible:
            estado = "bloqueada" if not data.get("aprendizaje_pendiente") else "aprendiendo"
        elif data.get("publicada") or data.get("validada"):
            estado = "publicada"
        else:
            estado = "lista_para_publicar"
    if not disponible and estado in {"lista_para_publicar", "publicada"}:
        estado = "aprendiendo" if data.get("aprendizaje_pendiente") else "bloqueada"
    data["estado"] = estado
    data["publicar_prediccion"] = disponible and estado in {"lista_para_publicar", "publicada"}
    data["publicar_solo_boleto"] = not data["publicar_prediccion"]
    return data


def estado_compuerta(jornada_objetivo, data_root=DATA):
    try:
        jornada_objetivo = int(jornada_objetivo or 0)
    except (TypeError, ValueError):
        jornada_objetivo = 0
    anterior = jornada_objetivo - 1 if jornada_objetivo else 0
    if anterior <= 0:
        return respuesta_compuerta(jornada_objetivo, anterior, "lista_para_publicar")
    resultados = estado_resultados(anterior, data_root)
    if not resultados["ok"]:
        motivo = (
            f"Cierre pendiente de la jornada anterior: la jornada {anterior} solo tiene "
            f"{resultados['cerrados']} de 14 resultados oficiales. No se genera prediccion "
            f"para la jornada {jornada_objetivo} hasta cerrar y aprender la {anterior}."
        )
        return respuesta_compuerta(jornada_objetivo, anterior, "bloqueada", motivo, resultados=resultados)
    aprendizaje = estado_aprendizaje(anterior, data_root)
    if not aprendizaje["ok"]:
        motivo = f"Aprendizaje pendiente de la jornada anterior: faltan {', '.join(aprendizaje['faltan'])}."
        return respuesta_compuerta(
            jornada_objetivo,
            anterior,
            "aprendiendo",
            motivo,
            resultados=resultados,
            aprendizaje=aprendizaje,
        )
    return respuesta_compuerta(
        jornada_objetivo,
        anterior,
        "lista_para_publicar",
        resultados=resultados,
        aprendizaje=aprendizaje,
    )
