import json
import os
from pathlib import Path

from bloqueo_jornada import estado_bloqueo_jornada


ROOT = Path(os.environ.get("QUINIHUB_ROOT", Path(__file__).resolve().parent)).resolve()
DATA = ROOT / "data"
SIGNOS = {"1", "X", "2"}
ESTADOS_PREDICCION_BLOQUEADA = {
    "pendiente_cierre_anterior",
    "bloqueada_pendiente_cierre_anterior",
    "provisional_pendiente_cierre_anterior",
}


def cargar(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def contar_partidos_con_resultado(jornada):
    if not jornada:
        return 0
    total = 0
    for partido in jornada.get("partidos", []):
        signo = str(partido.get("signo_oficial") or partido.get("signo_real") or "").upper()
        resultado = str(partido.get("resultado") or "")
        if signo in SIGNOS or "-" in resultado:
            total += 1
    return total


def contar_resultados_disponibles():
    total = 0
    jornadas = 0
    base = DATA / "jornadas"
    for path in sorted(base.glob("jornada_*.json")):
        data = cargar(path) or {}
        partidos = contar_partidos_con_resultado(data)
        if partidos:
            jornadas += 1
            total += partidos
    return jornadas, total


def validar_prediccion(prediccion, errores, bloqueo=None):
    if not prediccion:
        errores.append("No existe data/predicciones/ultima_prediccion.json")
        return None, 0, False

    partidos = prediccion.get("partidos") or []
    jornada_num = prediccion.get("jornada")
    estado = str(prediccion.get("estado") or "")
    bloqueada = bool(bloqueo and bloqueo.get("bloqueada"))

    if bloqueada:
        if estado not in ESTADOS_PREDICCION_BLOQUEADA:
            errores.append(
                "La prediccion objetivo esta bloqueada por cierre anterior, "
                "pero ultima_prediccion.json no esta marcada como bloqueada/provisional."
            )
        if int(prediccion.get("jornada") or 0) != int((bloqueo or {}).get("jornada_objetivo") or 0):
            errores.append("La prediccion bloqueada no coincide con la jornada objetivo.")
        if not (prediccion.get("motivo_bloqueo") or prediccion.get("mensaje")):
            errores.append("La prediccion bloqueada no explica motivo_bloqueo/mensaje.")
        return jornada_num, len(partidos), True

    if len(partidos) != 14:
        errores.append(f"La prediccion publicada tiene {len(partidos)} partidos; deben ser 14.")
    if not prediccion.get("generado_en"):
        errores.append("La prediccion no tiene timestamp generado_en.")
    sin_id = [p.get("num") for p in partidos if not p.get("partido_id")]
    if len(partidos) == 14 and sin_id:
        errores.append(f"La prediccion tiene partidos sin partido_id: {sin_id}")
    return jornada_num, len(partidos), False


def main():
    errores = []
    avisos = []

    estado_objetivo = cargar(DATA / "estado_jornada_objetivo.json") or {}
    objetivo_estado = int(estado_objetivo.get("jornada_objetivo") or 0)
    bloqueo = estado_bloqueo_jornada(objetivo_estado, DATA) if objetivo_estado else None
    prediccion = cargar(DATA / "predicciones" / "ultima_prediccion.json")
    jornada_num, total_partidos_prediccion, prediccion_bloqueada = validar_prediccion(prediccion, errores, bloqueo)

    jornada = cargar(DATA / "jornadas" / f"jornada_{jornada_num}.json") if jornada_num else None
    if not jornada:
        errores.append(f"No existe jornada oficial para la prediccion {jornada_num}.")
        partidos_resultado_jornada = 0
    else:
        partidos_resultado_jornada = contar_partidos_con_resultado(jornada)
        if partidos_resultado_jornada == 0:
            avisos.append(f"La jornada {jornada_num} aun no tiene resultados oficiales cerrados.")

    persistidas = cargar(DATA / "quinielas_generadas_ia.json")
    quinielas_persistidas = len((persistidas or {}).get("jugadas") or [])
    if quinielas_persistidas == 0 and not prediccion_bloqueada:
        errores.append("No hay quinielas IA persistidas en data/quinielas_generadas_ia.json")

    checks = {
        "memoria": DATA / "memoria_ia" / "aprendizaje_global.json",
        "diario": DATA / "memoria_ia" / "diario_aprendizaje.json",
        "pesos": DATA / "memoria_ia" / "pesos_dinamicos.json",
        "metricas": DATA / "memoria_ia" / "metricas_probabilisticas.json",
        "fiabilidad": DATA / "memoria_ia" / "fiabilidad_equipos.json",
        "revisiones": DATA / "memoria_ia" / "revisiones_prediccion_resultado.json",
    }
    cargados = {}
    for nombre, path in checks.items():
        data = cargar(path)
        cargados[nombre] = data or {}
        if not data:
            errores.append(f"No existe salida de {nombre}: {path.relative_to(ROOT)}")

    jornadas_con_resultado, partidos_con_resultado = contar_resultados_disponibles()
    revisiones = cargados["revisiones"]
    total_revisiones = int(revisiones.get("total_revisiones") or len(revisiones.get("revisiones") or []))
    metricas = cargados["metricas"]
    metricas_evaluadas = int(metricas.get("partidos_evaluados") or 0)
    fiabilidad = cargados["fiabilidad"]
    equipos_fiabilidad = fiabilidad.get("equipos") or {}

    if partidos_con_resultado > 0 and total_revisiones == 0:
        errores.append("Hay jornadas con resultados, pero no hay revisiones prediccion_resultado.")
    if partidos_con_resultado > 0 and metricas_evaluadas == 0:
        errores.append("Hay resultados cerrados, pero metricas_probabilisticas tiene 0 partidos evaluados.")
    if total_revisiones > 0 and not equipos_fiabilidad:
        errores.append("Hay revisiones, pero fiabilidad_equipos esta vacio.")

    print("COMPROBACION_CICLO_APRENDIZAJE")
    print(f"prediccion_jornada={jornada_num}")
    print(f"estado_prediccion_actual={(bloqueo or {}).get('estado_prediccion_actual')}")
    print(f"motivo_bloqueo={(bloqueo or {}).get('motivo_bloqueo')}")
    print(f"partidos_prediccion={total_partidos_prediccion}")
    print(f"partidos_resultado_jornada={partidos_resultado_jornada}")
    print(f"jornadas_con_resultado={jornadas_con_resultado}")
    print(f"partidos_con_resultado={partidos_con_resultado}")
    print(f"quinielas_ia_persistidas={quinielas_persistidas}")
    print(f"revisiones={total_revisiones}")
    print(f"metricas_partidos_evaluados={metricas_evaluadas}")
    print(f"equipos_fiabilidad={len(equipos_fiabilidad)}")
    for aviso in avisos:
        print(f"AVISO_CICLO: {aviso}")
    for error in errores:
        print(f"ERROR_CICLO: {error}")
    if errores:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
