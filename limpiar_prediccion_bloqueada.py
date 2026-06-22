import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PREDICCIONES = ROOT / "data" / "predicciones"

CAMPOS_PREDICTIVOS = [
    "probabilidades",
    "incertidumbre",
    "probabilidad_sorpresa",
    "probabilidad_top",
    "margen_probabilidad",
    "tercera_probabilidad",
    "indice_sorpresa_quinielistica",
    "categoria_sorpresa",
    "favorito",
    "favorito_nombre",
    "favorito_atacable",
    "signo_sorpresa_principal",
    "signos_contra_favorito",
    "cobertura_sorpresa_sugerida",
    "motivos_sorpresa",
    "origen_probabilidades",
    "calidad_datos",
    "trazabilidad_datos",
    "memoria_mundial_2026",
    "diagnostico_calidad",
    "tipo",
    "razonamiento",
    "elige8_modo",
    "elige8_seguro_score",
    "elige8_seguro_posicion",
    "elige8_seguro_cumple_umbral",
    "elige8_seguro_probabilidad_top",
    "elige8_seguro_margen",
    "elige8_criterio",
]

CAMPOS_RAIZ_PREDICTIVOS = [
    "elige8_seguro",
    "memoria_mundial_2026",
    "criterio_cobertura",
    "ataques_favorito_prioritarios",
    "alertas_boleto",
]


def cargar(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def guardar(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def bloqueada(data):
    if not data:
        return False
    if data.get("prediccion_disponible") is False:
        return True
    estado = str(data.get("estado") or "").lower()
    return "bloqueada" in estado or "pendiente_cierre" in estado


def limpiar(data):
    partidos = data.get("partidos") or []
    for partido in partidos:
        for campo in CAMPOS_PREDICTIVOS:
            partido.pop(campo, None)
        partido["estado_prediccion"] = "bloqueada_por_aprendizaje_pendiente"
        partido["signo_base"] = ""
        partido["signo_final"] = ""
        partido["pronostico_ia"] = "SIN PREDICCION"
        partido["elige8"] = False
        partido["lectura"] = "Partido cargado oficialmente. Prediccion retenida hasta cerrar y aprender la jornada anterior."

    pleno15 = data.get("pleno15") or {}
    if pleno15:
        for campo in CAMPOS_PREDICTIVOS:
            pleno15.pop(campo, None)
        pleno15["estado_prediccion"] = "bloqueada_por_aprendizaje_pendiente"
        pleno15["pronostico_ia"] = "SIN PREDICCION"
        pleno15["lectura"] = "Pleno al 15 cargado oficialmente. Prediccion retenida hasta cerrar y aprender la jornada anterior."

    for campo in CAMPOS_RAIZ_PREDICTIVOS:
        data.pop(campo, None)

    data["prediccion_disponible"] = False
    data["aprendizaje_pendiente"] = True
    data["prediccion_permitida"] = False
    estado_actual = str(data.get("estado") or "").lower()
    data["estado"] = estado_actual if estado_actual in {"bloqueada", "aprendiendo"} else "bloqueada"
    data["publicar_solo_boleto"] = True
    data["publicar_prediccion"] = False
    config = data.setdefault("configuracion", {})
    config["dobles"] = 0
    config["triples"] = 0
    config["elige8"] = False
    config["elige8_modo"] = "bloqueado"
    config["elige8_modos_disponibles"] = ["conservador", "rentable"]
    config["cobertura_auto"] = False

    data["coste"] = {
        "apuestas": 0,
        "apuestas_elige8": 0,
        "importe_quiniela": 0,
        "importe_elige8": 0,
        "importe_total": 0,
    }

    resumen = data.setdefault("resumen", {})
    resumen.clear()
    resumen.update({
        "fijos": 0,
        "dobles": 0,
        "triples": 0,
        "elige8_seleccionados": 0,
        "partidos_cargados": len(partidos),
        "pleno15_cargado": bool(pleno15),
        "total_casillas": len(partidos) + (1 if pleno15 else 0),
        "prediccion": "BLOQUEADA_POR_APRENDIZAJE_PENDIENTE",
    })
    data["mensaje"] = "Jornada cargada con 14 partidos y Pleno al 15. Prediccion bloqueada hasta cerrar y aprender la jornada anterior."
    return data


def rutas():
    salida = []
    ultima = PREDICCIONES / "ultima_prediccion.json"
    data = cargar(ultima)
    if data:
        salida.append(ultima)
        jornada = data.get("jornada")
        if jornada:
            path_jornada = PREDICCIONES / f"jornada_{jornada}.json"
            if path_jornada.exists():
                salida.append(path_jornada)
    return salida


def main():
    actualizados = []
    for path in rutas():
        data = cargar(path)
        if bloqueada(data):
            guardar(path, limpiar(data))
            actualizados.append(str(path.relative_to(ROOT)))
    print(json.dumps({"estado": "ok", "archivos_actualizados": actualizados}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
