from datos_profesionales import (
    OUT,
    crear_esqueleto_sin_secretos,
    guardar_si_cambia,
    leer_payload_externo,
    normalizar_payload,
)


def main():
    try:
        payload = leer_payload_externo()
    except Exception as exc:
        print(
            "AVISO: no se pudo leer datos profesionales externos; "
            f"se conserva salida local normalizada. Motivo: {exc}"
        )
        payload = None

    if payload:
        datos = normalizar_payload(payload, origen="secrets")
        cambiado = guardar_si_cambia(OUT, datos)
        print(
            "Datos profesionales actualizados desde secrets: "
            f"{datos['resumen'].get('partidos_enriquecidos', 0)} partidos enriquecidos. "
            f"{'Archivo modificado.' if cambiado else 'Sin cambios materiales.'}"
        )
        return

    datos = crear_esqueleto_sin_secretos()
    cambiado = guardar_si_cambia(OUT, datos)
    print(
        "Datos profesionales sin secrets configurados o fuente externa no disponible: "
        "se conserva esqueleto normalizado para cuotas, bajas, alineaciones y datos oficiales. "
        f"{'Archivo creado/actualizado.' if cambiado else 'Sin cambios materiales.'}"
    )


if __name__ == "__main__":
    main()
