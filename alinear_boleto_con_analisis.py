import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREDICCIONES = ROOT / "data" / "predicciones"
PRECIO_APUESTA = 0.75
PRECIO_ELIGE8 = 0.50
IMPORTE_MINIMO = 1.50
ORDEN_SIGNOS = {"1": 0, "X": 1, "2": 2}


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def numero(valor, defecto=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def cobertura_sugerida(partido):
    return str(partido.get("cobertura_sorpresa_sugerida") or "FIJO").upper()


def probabilidad(partido, signo):
    return numero((partido.get("probabilidades") or {}).get(signo), 0.0)


def top_dos_signos(partido):
    probs = partido.get("probabilidades") or {}
    signos = sorted(("1", "X", "2"), key=lambda s: (probabilidad(partido, s), -ORDEN_SIGNOS[s]), reverse=True)
    return signos[:2]


def signo_doble(partido):
    signos = sorted(top_dos_signos(partido), key=lambda s: ORDEN_SIGNOS[s])
    return "".join(signos)


def puntuacion_triple(partido):
    sugerida = cobertura_sugerida(partido)
    return (
        100000 if sugerida == "TRIPLE" else 0,
        numero(partido.get("indice_sorpresa_quinielistica")),
        numero(partido.get("tercera_probabilidad")),
        numero(partido.get("probabilidad_sorpresa")),
        numero(partido.get("incertidumbre")),
        -numero(partido.get("margen_probabilidad")),
        -int(partido.get("num") or 0),
    )


def puntuacion_doble(partido):
    sugerida = cobertura_sugerida(partido)
    return (
        100000 if sugerida == "DOBLE" else 0,
        50000 if sugerida == "TRIPLE" else 0,
        numero(partido.get("indice_sorpresa_quinielistica")),
        numero(partido.get("probabilidad_sorpresa")),
        numero(partido.get("incertidumbre")),
        -numero(partido.get("margen_probabilidad")),
        probabilidad(partido, "X"),
        -int(partido.get("num") or 0),
    )


def recalcular_coste(dobles, triples, elige8):
    apuestas = 2 ** int(dobles) * 3 ** int(triples)
    importe_quiniela = max(apuestas * PRECIO_APUESTA, IMPORTE_MINIMO)
    importe_elige8 = apuestas * PRECIO_ELIGE8 if elige8 else 0.0
    return {
        "apuestas": apuestas,
        "importe_quiniela": round(importe_quiniela, 2),
        "importe_elige8": round(importe_elige8, 2),
        "importe_total": round(importe_quiniela + importe_elige8, 2),
    }


def alinear_prediccion(data):
    partidos = list(data.get("partidos") or [])
    if not partidos:
        return data

    config = data.setdefault("configuracion", {})
    triples = int(config.get("triples") or 0)
    dobles = int(config.get("dobles") or 0)
    elige8 = bool(config.get("elige8"))

    triples = max(0, min(triples, len(partidos)))
    dobles = max(0, min(dobles, len(partidos) - triples))

    triples_set = {p.get("num") for p in sorted(partidos, key=puntuacion_triple, reverse=True)[:triples]}
    candidatos_doble = [p for p in partidos if p.get("num") not in triples_set]
    dobles_set = {p.get("num") for p in sorted(candidatos_doble, key=puntuacion_doble, reverse=True)[:dobles]}

    for partido in partidos:
        num = partido.get("num")
        if num in triples_set:
            partido["tipo"] = "TRIPLE"
            partido["signo_final"] = "1X2"
        elif num in dobles_set:
            partido["tipo"] = "DOBLE"
            partido["signo_final"] = signo_doble(partido)
        else:
            partido["tipo"] = "FIJO"
            partido["signo_final"] = partido.get("signo_base") or top_dos_signos(partido)[0]

        razon = str(partido.get("razonamiento") or "")
        corte = razon.rfind("Decision final:")
        if corte >= 0:
            razon = razon[:corte].rstrip()
        partido["razonamiento"] = f"{razon} Decision final: {partido['signo_final']}.".strip()

    data["partidos"] = sorted(partidos, key=lambda p: int(p.get("num") or 0))
    data["coste"] = recalcular_coste(dobles, triples, elige8)
    data["criterio_cobertura"] = (
        "Boleto alineado con el analisis: triples para los mayores indices de sorpresa "
        "y coberturas TRIPLE sugeridas; dobles para las siguientes prioridades por sorpresa, "
        "empate, margen bajo e incertidumbre."
    )
    data["resumen"] = {
        "fijos": sum(1 for p in data["partidos"] if p.get("tipo") == "FIJO"),
        "dobles": sum(1 for p in data["partidos"] if p.get("tipo") == "DOBLE"),
        "triples": sum(1 for p in data["partidos"] if p.get("tipo") == "TRIPLE"),
        "elige8_seleccionados": sum(1 for p in data["partidos"] if p.get("elige8")),
        "favoritos_atacables": sum(1 for p in data["partidos"] if p.get("favorito_atacable")),
        "indice_sorpresa_max": max((numero(p.get("indice_sorpresa_quinielistica")) for p in data["partidos"]), default=0),
    }

    data["ataques_favorito_prioritarios"] = [
        {
            "num": p.get("num"),
            "partido": f"{p.get('local', '')} - {p.get('visitante', '')}",
            "favorito": p.get("favorito"),
            "favorito_nombre": p.get("favorito_nombre"),
            "indice_sorpresa_quinielistica": p.get("indice_sorpresa_quinielistica"),
            "signo_sorpresa_principal": p.get("signo_sorpresa_principal"),
            "signos_contra_favorito": p.get("signos_contra_favorito", []),
            "cobertura_sorpresa_sugerida": p.get("cobertura_sorpresa_sugerida"),
            "tipo_final": p.get("tipo"),
            "signo_final": p.get("signo_final"),
            "motivo_sorpresa": "; ".join((p.get("motivos_sorpresa") or [])[:3]),
        }
        for p in sorted(data["partidos"], key=lambda item: numero(item.get("indice_sorpresa_quinielistica")), reverse=True)
        if p.get("favorito_atacable") or cobertura_sugerida(p) != "FIJO"
    ][:8]
    return data


def alinear_archivo(path):
    data = cargar_json(path, {})
    if not data:
        return False
    antes = json.dumps(data, ensure_ascii=False, sort_keys=True)
    data = alinear_prediccion(data)
    despues = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if antes == despues:
        return False
    guardar_json(path, data)
    return True


def main():
    ultima = PREDICCIONES / "ultima_prediccion.json"
    cambios = []
    if alinear_archivo(ultima):
        cambios.append(str(ultima))
    data = cargar_json(ultima, {})
    jornada = data.get("jornada")
    if jornada:
        path_jornada = PREDICCIONES / f"jornada_{jornada}.json"
        guardar_json(path_jornada, data)
        cambios.append(str(path_jornada))
    print("Boleto alineado con analisis: " + (", ".join(cambios) if cambios else "sin cambios"))


if __name__ == "__main__":
    main()
