import json
from datetime import datetime, timezone

from bloqueo_jornada import estado_bloqueo_jornada
from jornada_objetivo_quiniela import resumen_jornada_objetivo
from motor_prediccion_quiniela import DATA, PREDICCIONES, guardar_json, predecir


ESTADO_OBJETIVO = DATA / "estado_jornada_objetivo.json"


def motivo_bloqueo(estado):
    return estado.get("motivo_bloqueo") or estado.get("motivo") or "Jornada pendiente de cierre anterior."


def escribir_prediccion_en_espera(objetivo, estado):
    salida = {
        "version": "1.1",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "jornada": objetivo,
        "temporada_base": "2025/2026",
        "temporada": "2025/2026",
        "competicion": "quiniela",
        "estado": "pendiente_cierre_anterior",
        "partidos": [],
        "configuracion": {"dobles": 0, "triples": 0, "elige8": False, "cobertura_auto": False},
        "coste": {"apuestas": 0, "importe_quiniela": 0, "importe_elige8": 0, "importe_total": 0.01},
        "mensaje": motivo_bloqueo(estado),
        "motivo_bloqueo": motivo_bloqueo(estado),
        "estado_jornada_objetivo": estado,
        "resumen": {"fijos": 0, "dobles": 0, "triples": 0, "elige8_seleccionados": 0},
    }
    guardar_json(PREDICCIONES / "ultima_prediccion.json", salida)
    guardar_json(PREDICCIONES / f"jornada_{objetivo}.json", salida)


def main():
    estado = resumen_jornada_objetivo()
    objetivo = int(estado.get("jornada_objetivo") or 0)
    estado["generado_en"] = datetime.now(timezone.utc).isoformat()

    if objetivo:
        estado.update(estado_bloqueo_jornada(objetivo))
    else:
        estado.update({
            "estado_prediccion_actual": "bloqueada",
            "bloqueada": True,
            "motivo_bloqueo": "No hay jornada objetivo para predecir.",
        })

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

    if estado.get("bloqueada"):
        escribir_prediccion_en_espera(objetivo, estado)
        print(
            f"BLOQUEO_JORNADA: no se publica la jornada {objetivo}. "
            f"Motivo: {estado.get('motivo_bloqueo')}"
        )
        return

    predecir(jornada=objetivo)

    prediccion = PREDICCIONES / "ultima_prediccion.json"
    if prediccion.exists():
        data = json.loads(prediccion.read_text(encoding="utf-8"))
        data["estado_jornada_objetivo"] = estado
        data["estado"] = "publicable"
        guardar_json(prediccion, data)
        guardar_json(PREDICCIONES / f"jornada_{objetivo}.json", data)

    print(
        f"Jornada objetivo de prediccion: {objetivo}. "
        f"Ultima aprendida: {estado.get('ultima_jornada_aprendida')}. "
        f"Futuras cargadas: {estado.get('jornadas_futuras_cargadas')}. "
        f"Faltantes intermedias: {estado.get('jornadas_intermedias_faltantes')}."
    )


if __name__ == "__main__":
    main()
