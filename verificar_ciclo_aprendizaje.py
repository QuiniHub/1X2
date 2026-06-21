import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def cargar(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def contar_partidos_con_resultado(jornada):
    if not jornada:
        return 0
    total = 0
    for partido in jornada.get("partidos", []):
        signo = str(partido.get("signo_oficial") or "").upper()
        resultado = str(partido.get("resultado") or "")
        if signo in {"1", "X", "2"} or "-" in resultado:
            total += 1
    return total


def main():
    errores = []
    avisos = []

    prediccion = cargar(DATA / "predicciones" / "ultima_prediccion.json")
    if not prediccion:
        errores.append("No existe data/predicciones/ultima_prediccion.json")
    else:
        partidos = prediccion.get("partidos") or []
        if len(partidos) != 14:
            errores.append(f"La prediccion publicada tiene {len(partidos)} partidos; deben ser 14.")
        if not prediccion.get("generado_en"):
            errores.append("La prediccion no tiene timestamp generado_en.")
        if not all(p.get("partido_id") for p in partidos):
            errores.append("Hay partidos de prediccion sin partido_id estable.")

    jornada_num = prediccion.get("jornada") if prediccion else None
    jornada = cargar(DATA / "jornadas" / f"jornada_{jornada_num}.json") if jornada_num else None
    if not jornada:
        errores.append(f"No existe jornada oficial para la prediccion {jornada_num}.")
    else:
        con_resultado = contar_partidos_con_resultado(jornada)
        if con_resultado == 0:
            avisos.append(f"La jornada {jornada_num} aun no tiene resultados oficiales cerrados.")

    persistidas = cargar(DATA / "quinielas_generadas_ia.json")
    if not persistidas or not persistidas.get("jugadas"):
        errores.append("No hay quinielas IA persistidas en data/quinielas_generadas_ia.json")

    checks = {
        "memoria": DATA / "memoria_ia" / "aprendizaje_global.json",
        "diario": DATA / "memoria_ia" / "diario_aprendizaje.json",
        "pesos": DATA / "memoria_ia" / "pesos_dinamicos.json",
        "metricas": DATA / "memoria_ia" / "metricas_probabilisticas.json",
        "fiabilidad": DATA / "memoria_ia" / "fiabilidad_equipos.json",
        "revisiones": DATA / "memoria_ia" / "revisiones_prediccion_resultado.json",
    }
    for nombre, path in checks.items():
        data = cargar(path)
        if not data:
            errores.append(f"No existe salida de {nombre}: {path.relative_to(ROOT)}")

    metricas = cargar(checks["metricas"]) or {}
    if int(metricas.get("partidos_evaluados") or 0) == 0:
        avisos.append("Metricas probabilisticas sin partidos evaluados; falta cerrar resultados o persistir jugadas.")

    print("COMPROBACION_CICLO_APRENDIZAJE")
    print(f"prediccion_jornada={jornada_num}")
    print(f"partidos_prediccion={len((prediccion or {}).get('partidos') or [])}")
    print(f"partidos_resultado_jornada={contar_partidos_con_resultado(jornada)}")
    print(f"quinielas_ia_persistidas={len((persistidas or {}).get('jugadas') or [])}")
    print(f"metricas_partidos_evaluados={metricas.get('partidos_evaluados', 0)}")
    for aviso in avisos:
        print(f"AVISO_CICLO: {aviso}")
    for error in errores:
        print(f"ERROR_CICLO: {error}")
    if errores:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
