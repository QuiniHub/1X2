import json
import os
import re
import sys
from pathlib import Path


ROOT = Path(os.environ.get("QUINIHUB_ROOT", Path(__file__).resolve().parent)).resolve()
DATA = ROOT / "data"
SIGNOS = {"1", "X", "2"}
ESTADOS_PREDICCION_BLOQUEADA = {
    "pendiente_cierre_anterior",
    "bloqueada_pendiente_cierre_anterior",
    "provisional_pendiente_cierre_anterior",
}
PESOS_REQUERIDOS = {
    "forma_reciente",
    "casa_fuera",
    "clasificacion",
    "goles",
    "empate",
    "sorpresa",
    "motivacion_competitiva",
    "necesidad_descenso_ascenso_europa",
    "fatiga",
    "bajas",
}


def cargar(path, errores):
    if not path.exists():
        errores.append(f"{rel(path)}: no existe")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errores.append(f"{rel(path)}: {exc}")
        return None


def rel(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def es_numero(valor):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def tiene_valor(item, campo):
    return campo in item and item.get(campo) not in (None, "", [])


def tiene_resultado(item):
    signo = str(item.get("signo_real") or item.get("signo_oficial") or "").upper()
    resultado = str(item.get("resultado") or "")
    return signo in SIGNOS or bool(re.match(r"^\s*\d+\s*-\s*\d+\s*$", resultado))


def validar_probabilidades(path, probs, errores):
    if not isinstance(probs, dict):
        errores.append(f"{path}: probabilidades debe ser objeto")
        return
    for signo in ("1", "X", "2"):
        if signo not in probs:
            errores.append(f"{path}: falta probabilidades.{signo}")
        elif not es_numero(probs.get(signo)):
            errores.append(f"{path}: probabilidades.{signo} debe ser numerico")


def validar_partido_contrato(path, item, errores, exigir_jornada=False):
    if not isinstance(item, dict):
        errores.append(f"{path}: debe ser objeto")
        return

    campos = [
        "partido_id",
        "local",
        "visitante",
        "signo_predicho",
        "probabilidades",
        "tipo_apuesta",
        "timestamp_generacion",
    ]
    if exigir_jornada:
        campos.insert(0, "jornada")
    for campo in campos:
        if not tiene_valor(item, campo):
            errores.append(f"{path}: falta {campo}")

    validar_probabilidades(path, item.get("probabilidades"), errores)

    if tiene_resultado(item):
        signo_real = str(item.get("signo_real") or "").upper()
        if signo_real not in SIGNOS:
            errores.append(f"{path}: falta signo_real valido aunque existe resultado")
        for campo in ("probabilidad_signo_real", "brier_score", "ranking_signo_real"):
            if campo not in item or item.get(campo) is None:
                errores.append(f"{path}: falta {campo} porque existe signo_real/resultado")
        if item.get("probabilidad_signo_real") is not None and not es_numero(item.get("probabilidad_signo_real")):
            errores.append(f"{path}: probabilidad_signo_real debe ser numerico")
        if item.get("brier_score") is not None and not es_numero(item.get("brier_score")):
            errores.append(f"{path}: brier_score debe ser numerico")
        ranking = item.get("ranking_signo_real")
        if ranking is not None and ranking not in (1, 2, 3):
            errores.append(f"{path}: ranking_signo_real debe ser 1, 2 o 3")


def validar_ultima_prediccion(path, data, errores):
    if not isinstance(data, dict):
        errores.append(f"{rel(path)}: debe ser objeto")
        return
    for campo in ("jornada", "generado_en"):
        if not tiene_valor(data, campo):
            errores.append(f"{rel(path)}: falta {campo}")
    estado = str(data.get("estado") or "")
    if estado in ESTADOS_PREDICCION_BLOQUEADA:
        if not (data.get("motivo_bloqueo") or data.get("mensaje")):
            errores.append(f"{rel(path)}: prediccion bloqueada sin motivo_bloqueo/mensaje")
        return
    partidos = data.get("partidos")
    if not isinstance(partidos, list) or len(partidos) != 14:
        errores.append(f"{rel(path)}: partidos debe contener 14 elementos")
        return
    for idx, partido in enumerate(partidos, 1):
        validar_partido_contrato(f"{rel(path)} partidos[{idx}]", partido, errores)


def validar_quinielas_generadas(path, data, errores):
    if not isinstance(data, dict):
        errores.append(f"{rel(path)}: debe ser objeto")
        return
    jugadas = data.get("jugadas")
    if not isinstance(jugadas, list):
        errores.append(f"{rel(path)}: jugadas debe ser lista")
        return
    for idx, jugada in enumerate(jugadas, 1):
        base = f"{rel(path)} jugadas[{idx}]"
        for campo in ("jornada", "generado_en", "signos", "partidos"):
            if not tiene_valor(jugada, campo):
                errores.append(f"{base}: falta {campo}")
        if isinstance(jugada.get("signos"), list) and len(jugada["signos"]) != 14:
            errores.append(f"{base}: signos debe contener 14 elementos")
        partidos = jugada.get("partidos") or []
        if not isinstance(partidos, list) or len(partidos) != 14:
            errores.append(f"{base}: partidos debe contener 14 elementos")
            continue
        for pidx, partido in enumerate(partidos, 1):
            validar_partido_contrato(f"{base} partidos[{pidx}]", partido, errores, exigir_jornada=True)


def validar_metricas(path, data, errores):
    campos = [
        "version",
        "generado_en",
        "partidos_evaluados",
        "probabilidad_media_signo_real",
        "error_probabilistico_medio",
        "brier_score_medio",
        "accuracy_top1",
        "accuracy_top2",
        "accuracy_por_signo",
        "accuracy_por_tipo_apuesta",
        "accuracy_favoritos",
        "accuracy_sorpresas",
    ]
    for campo in campos:
        if not tiene_valor(data, campo) and data.get(campo) != 0:
            errores.append(f"{rel(path)}: falta {campo}")
    for campo in ("partidos_evaluados", "brier_score_medio", "accuracy_top1", "accuracy_top2"):
        if campo in data and not es_numero(data.get(campo)):
            errores.append(f"{rel(path)}: {campo} debe ser numerico")


def validar_fiabilidad(path, data, errores):
    for campo in ("version", "generado_en", "equipos"):
        if not tiene_valor(data, campo) and data.get(campo) != {}:
            errores.append(f"{rel(path)}: falta {campo}")
    equipos = data.get("equipos")
    if not isinstance(equipos, dict):
        errores.append(f"{rel(path)}: equipos debe ser objeto")
        return
    campos_equipo = [
        "partidos_evaluados",
        "aciertos",
        "fallos",
        "accuracy_global",
        "accuracy_como_local",
        "accuracy_como_visitante",
        "fallos_por_sorpresa",
        "aciertos_como_favorito",
        "fallos_como_favorito",
        "tendencia_reciente",
        "nivel_fiabilidad_motor",
    ]
    for equipo, stats in equipos.items():
        for campo in campos_equipo:
            if campo not in stats:
                errores.append(f"{rel(path)} equipos.{equipo}: falta {campo}")


def validar_revisiones(path, data, errores):
    for campo in ("version", "generado_en", "total_revisiones", "revisiones"):
        if not tiene_valor(data, campo) and data.get(campo) != 0:
            errores.append(f"{rel(path)}: falta {campo}")
    revisiones = data.get("revisiones")
    if not isinstance(revisiones, list):
        errores.append(f"{rel(path)}: revisiones debe ser lista")
        return
    if int(data.get("total_revisiones") or 0) != len(revisiones):
        errores.append(f"{rel(path)}: total_revisiones no coincide con revisiones")
    for idx, revision in enumerate(revisiones, 1):
        validar_partido_contrato(f"{rel(path)} revisiones[{idx}]", revision, errores, exigir_jornada=True)


def validar_pesos(path, data, errores):
    for campo in ("version", "generado_en", "referencia", "explicaciones", "pesos", "muestra", "ajustes"):
        if not tiene_valor(data, campo) and data.get(campo) not in ({}, []):
            errores.append(f"{rel(path)}: falta {campo}")
    referencia = data.get("referencia") or {}
    pesos = data.get("pesos") or {}
    explicaciones = data.get("explicaciones") or {}
    for peso in PESOS_REQUERIDOS:
        if peso not in referencia:
            errores.append(f"{rel(path)}: falta referencia.{peso}")
        if peso not in pesos:
            errores.append(f"{rel(path)}: falta pesos.{peso}")
        elif not es_numero(pesos.get(peso)):
            errores.append(f"{rel(path)}: pesos.{peso} debe ser numerico")
        if not explicaciones.get(peso):
            errores.append(f"{rel(path)}: falta explicaciones.{peso}")


def validar_diario(path, data, errores):
    for campo in ("version", "generado_en", "total_entradas", "entradas", "ajustes_pesos_dinamicos"):
        if not tiene_valor(data, campo) and data.get(campo) not in (0, []):
            errores.append(f"{rel(path)}: falta {campo}")
    entradas = data.get("entradas")
    if not isinstance(entradas, list):
        errores.append(f"{rel(path)}: entradas debe ser lista")
        return
    if int(data.get("total_entradas") or 0) != len(entradas):
        errores.append(f"{rel(path)}: total_entradas no coincide con entradas")
    for idx, entrada in enumerate(entradas, 1):
        validar_partido_contrato(f"{rel(path)} entradas[{idx}]", entrada, errores, exigir_jornada=True)


def validar_esquemas(errores):
    objetivos = {
        DATA / "predicciones" / "ultima_prediccion.json": validar_ultima_prediccion,
        DATA / "quinielas_generadas_ia.json": validar_quinielas_generadas,
        DATA / "memoria_ia" / "metricas_probabilisticas.json": validar_metricas,
        DATA / "memoria_ia" / "fiabilidad_equipos.json": validar_fiabilidad,
        DATA / "memoria_ia" / "revisiones_prediccion_resultado.json": validar_revisiones,
        DATA / "memoria_ia" / "pesos_dinamicos.json": validar_pesos,
        DATA / "memoria_ia" / "diario_aprendizaje.json": validar_diario,
    }
    for path, validador in objetivos.items():
        data = cargar(path, errores)
        if data is not None:
            validador(path, data, errores)


def validar_archivos(root=ROOT):
    errores = []
    total = 0
    for base in [Path(root) / "data"]:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.json")):
            total += 1
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                errores.append(f"{rel(path)}: {exc}")
    validar_esquemas(errores)
    return total, errores


def main():
    total, errores = validar_archivos(ROOT)
    print(f"VALIDACION_JSON: archivos revisados={total}, errores={len(errores)}")
    for error in errores:
        print(f"ERROR_JSON: {error}")
    if errores:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
