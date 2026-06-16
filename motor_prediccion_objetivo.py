from datetime import datetime, timezone

from jornada_objetivo_quiniela import resumen_jornada_objetivo
from motor_prediccion_quiniela import DATA, PREDICCIONES, guardar_json, predecir


ESTADO_OBJETIVO = DATA / "estado_jornada_objetivo.json"


def main():
    estado = resumen_jornada_objetivo()
    objetivo = int(estado.get("jornada_objetivo") or 0)
    estado["generado_en"] = datetime.now(timezone.utc).isoformat()

    guardar_json(ESTADO_OBJETIVO, estado)

    if not objetivo:
        raise SystemExit("No hay jornada objetivo para predecir.")

    if not estado.get("jornada_objetivo_cargada"):
        raise SystemExit(
            f"La jornada objetivo {objetivo} aun no esta cargada. "
            "Se espera a que el boleto oficial este publicado."
        )

    predecir(jornada=objetivo)

    prediccion = PREDICCIONES / "ultima_prediccion.json"
    data = {}
    if prediccion.exists():
        import json

        data = json.loads(prediccion.read_text(encoding="utf-8"))
        data["estado_jornada_objetivo"] = estado
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
