from datetime import datetime, timezone
from pathlib import Path

from generar_estado_vivo_ia import (
    DATA,
    JORNADAS,
    MEMORIA,
    PREDICCIONES,
    analizar_prediccion,
    aprendizajes,
    aprendizajes_contexto,
    autocritica,
    cargar_json,
    cambios_jornada_actual,
    crear_indice_competitivo,
    errores_a_evitar,
    guardar_json,
    leer_jornada_actual,
    resumir_contexto_competitivo,
)


def ultima_prediccion_disponible():
    pred = cargar_json(PREDICCIONES / "ultima_prediccion.json", {})
    if pred:
        return pred

    candidatas = []
    for path in PREDICCIONES.glob("jornada_*.json"):
        data = cargar_json(path, {})
        if isinstance(data.get("jornada"), int):
            candidatas.append(data)
    return max(candidatas, key=lambda item: item.get("jornada", 0), default={})


def main():
    memoria = cargar_json(MEMORIA / "aprendizaje_global.json", {})
    contexto_competitivo = cargar_json(MEMORIA / "contexto_competitivo.json", {})
    prediccion = ultima_prediccion_disponible()
    jornada = leer_jornada_actual()
    indice_competitivo = crear_indice_competitivo(contexto_competitivo or {})
    estado_jornada = cambios_jornada_actual(jornada, indice_competitivo)
    estado_prediccion = analizar_prediccion(prediccion, contexto_competitivo)
    jornada_objetivo = prediccion.get("jornada") or estado_jornada.get("jornada")

    salida = {
        "version": "1.1",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "estado": "vivo_en_desarrollo",
        "jornada_actual": estado_jornada,
        "prediccion_objetivo": estado_prediccion,
        "contexto_competitivo": resumir_contexto_competitivo(contexto_competitivo),
        "que_ha_cambiado": estado_jornada["resultados_nuevos_o_vigentes"],
        "que_aprende": aprendizajes(estado_jornada) + aprendizajes_contexto(contexto_competitivo),
        "que_modifica_para_jornada_objetivo": [
            f"Reordenar confianza para la jornada {jornada_objetivo} segun resultados nuevos de la jornada actual.",
            "Subir vigilancia de empates o visitantes si la jornada actual los confirma.",
            "Priorizar dobles/triples en partidos con incertidumbre mas alta.",
            "Cruzar cada signo con la necesidad real de puntos: titulo, Europa, ascenso, playoff y descenso.",
        ],
        "partidos_mas_seguros": estado_prediccion["partidos_mas_seguros"],
        "partidos_trampa_o_sorpresa": estado_prediccion["partidos_trampa_o_sorpresa"],
        "dudas_abiertas": estado_prediccion["dudas_abiertas"],
        "autocritica": autocritica(estado_jornada, prediccion, memoria),
        "errores_a_evitar": errores_a_evitar(prediccion),
    }
    guardar_json(MEMORIA / "estado_vivo.json", salida)
    print(f"Estado vivo regenerado con prediccion jornada {jornada_objetivo}.")


if __name__ == "__main__":
    main()
