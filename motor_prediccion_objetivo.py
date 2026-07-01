import json
from datetime import datetime, timezone

from compuerta_jornada import estado_compuerta
from jornada_objetivo_quiniela import resumen_jornada_objetivo
from motor_prediccion_quiniela import DATA, PREDICCIONES, guardar_json, predecir


ESTADO_OBJETIVO = DATA / "estado_jornada_objetivo.json"


def cargar_jornada_oficial(objetivo):
    path = DATA / "jornadas" / f"jornada_{objetivo}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def partido_en_espera(partido):
    return {
        "num": partido.get("num"),
        "local": partido.get("local"),
        "visitante": partido.get("visitante"),
        "fecha": partido.get("fecha"),
        "hora": partido.get("hora"),
        "resultado": partido.get("resultado", "Pendiente"),
        "signo_oficial": partido.get("signo_oficial", "Pendiente"),
        "signo_nuestro": partido.get("signo_nuestro", "No jugada"),
        "estado_prediccion": "bloqueada_por_aprendizaje_pendiente",
        "signo_base": "",
        "signo_final": "",
        "pronostico_ia": "SIN PREDICCION",
        "elige8": False,
        "lectura": "Partido cargado oficialmente. Prediccion retenida hasta cerrar y aprender la jornada anterior.",
    }


def escribir_prediccion_en_espera(objetivo, estado):
    jornada = cargar_jornada_oficial(objetivo)
    partidos = [partido_en_espera(p) for p in jornada.get("partidos", [])]
    pleno15 = jornada.get("pleno15") or {}
    motivo = estado.get("motivo") or "Jornada pendiente de cierre anterior."

    salida = {
        "version": "1.2",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "jornada": objetivo,
        "fecha": jornada.get("fecha"),
        "fuente": jornada.get("fuente"),
        "temporada_base": "2025/2026",
        "temporada": "2025/2026",
        "competicion": "quiniela",
        "estado": "partidos_cargados_prediccion_bloqueada",
        "prediccion_disponible": False,
        "aprendizaje_pendiente": True,
        "partidos": partidos,
        "pleno15": pleno15,
        "configuracion": {"dobles": 0, "triples": 0, "elige8": False, "cobertura_auto": False},
        "coste": {"apuestas": 0, "importe_quiniela": 0, "importe_elige8": 0, "importe_total": 0.0},
        "mensaje": "Partidos de la jornada cargados. Prediccion bloqueada hasta cerrar y aprender la jornada anterior.",
        "motivo_bloqueo": motivo,
        "estado_jornada_objetivo": estado,
        "resumen": {
            "fijos": 0,
            "dobles": 0,
            "triples": 0,
            "elige8_seleccionados": 0,
            "partidos_cargados": len(partidos),
            "prediccion": "BLOQUEADA_POR_APRENDIZAJE_PENDIENTE",
        },
    }
    guardar_json(PREDICCIONES / "ultima_prediccion.json", salida)
    guardar_json(PREDICCIONES / f"jornada_{objetivo}.json", salida)


def main():
    estado = resumen_jornada_objetivo()
    objetivo = int(estado.get("jornada_objetivo") or 0)
    estado["generado_en"] = datetime.now(timezone.utc).isoformat()

    if objetivo:
        compuerta = estado_compuerta(objetivo)
        estado.update(compuerta)
        estado["bloqueada"] = bool(compuerta.get("en_espera"))
        estado["motivo_bloqueo"] = compuerta.get("motivo", "")

    guardar_json(ESTADO_OBJETIVO, estado)

    if not objetivo:
        print("No hay jornada objetivo para predecir. Se conserva la prediccion existente.")
        return

    if not estado.get("jornada_objetivo_cargada"):
        print(
            f"La jornada objetivo {objetivo} aun no esta cargada. "
            "Se espera a que el boleto oficial este publicado y se conserva la prediccion existente."
        )
        return

    if estado.get("en_espera"):
        escribir_prediccion_en_espera(objetivo, estado)
        print(f"Jornada {objetivo} con partidos cargados, pero prediccion en espera. {estado.get('motivo')}")
        return

    predecir(jornada=objetivo)

    prediccion = PREDICCIONES / "ultima_prediccion.json"
    if prediccion.exists():
        data = json.loads(prediccion.read_text(encoding="utf-8"))
        data["estado_jornada_objetivo"] = estado
        guardar_json(prediccion, data)
        guardar_json(PREDICCIONES / f"jornada_{objetivo}.json", data)

    print(
        f"Jornada objetivo de prediccion: {objetivo}. "
        f"Ultima aprendida: {estado.get('ultima_jornada_aprendida')}. "
        f"Futuras cargadas: {estado.get('jornadas_futuras_cargadas')}. "
        f"Faltantes intermedias: {estado.get('jornadas_intermedias_faltantes')}"
    )


if __name__ == "__main__":
    main()
