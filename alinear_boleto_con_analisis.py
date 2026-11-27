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


def signo_limpio(valor):
    """Signos 1/X/2 presentes en el valor, sin repetir y en orden 1-X-2."""
    texto = str(valor or "").upper()
    return "".join(s for s in ("1", "X", "2") if s in texto)


def tipo_por_signo(signo):
    return {1: "FIJO", 2: "DOBLE", 3: "TRIPLE"}.get(len(signo_limpio(signo)), "FIJO")


def multiplicador(signos):
    total = 1
    for signo in signos:
        total *= max(len(signo_limpio(signo)), 1)
    return total


def recalcular_coste(partidos, elige8=True):
    """Coste del boleto TAL Y COMO lo dejo el motor.

    Auditoria 26/11/2026 (hallazgo 181): el Elige 8 se cobra solo sobre los 8
    partidos elegidos (apuestas_elige8 = producto de los signos de esos 8),
    no sobre todas las apuestas del boleto. Misma cuenta que
    aplicar_elige8_seguro.recalcular_coste, que corre al final de la cadena.
    """
    con_signo = [p for p in partidos if signo_limpio(p.get("signo_final"))]
    if not con_signo:
        # Prediccion retenida (sin signos): no hay boleto que cobrar.
        return {
            "apuestas": 0,
            "apuestas_elige8": 0,
            "importe_quiniela": 0,
            "importe_elige8": 0,
            "importe_total": 0,
        }
    apuestas = multiplicador(p.get("signo_final") for p in con_signo)
    elegidos = [p for p in con_signo if p.get("en_elige8") or p.get("elige8")] if elige8 else []
    apuestas_elige8 = multiplicador(p.get("signo_final") for p in elegidos) if elegidos else 0
    importe_quiniela = max(apuestas * PRECIO_APUESTA, IMPORTE_MINIMO)
    importe_elige8 = apuestas_elige8 * PRECIO_ELIGE8
    return {
        "apuestas": apuestas,
        "apuestas_elige8": apuestas_elige8,
        "importe_quiniela": round(importe_quiniela, 2),
        "importe_elige8": round(importe_elige8, 2),
        "importe_total": round(importe_quiniela + importe_elige8, 2),
    }


def texto_probabilidades(partido):
    probs = partido.get("probabilidades") or {}
    return f"1={probs.get('1', '-')}%, X={probs.get('X', '-')}%, 2={probs.get('2', '-')}%"


def frase_tipo(partido):
    tipo = str(partido.get("tipo") or "FIJO").upper()
    signo = partido.get("signo_final") or partido.get("signo_base") or "1"
    sugerida = cobertura_sugerida(partido)
    indice = numero(partido.get("indice_sorpresa_quinielistica"))
    sorpresa = numero(partido.get("probabilidad_sorpresa"))
    incertidumbre = numero(partido.get("incertidumbre"))
    margen = numero(partido.get("margen_probabilidad"), 99)
    if tipo == "TRIPLE":
        return (
            "Se abre TRIPLE porque el partido aparece entre las maximas prioridades de cobertura: "
            f"sugerencia={sugerida}, indice de sorpresa={indice:.1f}/100, sorpresa={sorpresa:.1f}%, "
            f"incertidumbre={incertidumbre:.1f} y margen={margen:.1f}."
        )
    if tipo == "DOBLE":
        return (
            f"Se cubre con DOBLE ({signo}) porque entra entre las siguientes prioridades de riesgo: "
            f"sugerencia={sugerida}, indice de sorpresa={indice:.1f}/100, sorpresa={sorpresa:.1f}%, "
            f"incertidumbre={incertidumbre:.1f} y margen={margen:.1f}."
        )
    return (
        f"Se mantiene como FIJO ({signo}) solo porque el presupuesto de dobles/triples obliga a priorizar otros riesgos. "
        f"No es un fijo limpio si la sugerencia es {sugerida}, indice={indice:.1f}/100 o sorpresa={sorpresa:.1f}%."
    )


def frase_calidad_datos(partido):
    mundial = partido.get("memoria_mundial_2026") or {}
    origen = str(partido.get("origen_probabilidades") or "")
    calidad = partido.get("calidad_datos") or "sin_calidad"
    if mundial.get("aplicado"):
        local = mundial.get("local") or {}
        visitante = mundial.get("visitante") or {}
        return (
            "Calidad de datos: "
            f"{calidad}. Historial Mundial 2026 incorporado con muestra minima {mundial.get('muestra_minima')} partido(s): "
            f"{partido.get('local')} {local.get('pts', 0)} pts, GF {local.get('gf', 0)}, GC {local.get('gc', 0)}; "
            f"{partido.get('visitante')} {visitante.get('pts', 0)} pts, GF {visitante.get('gf', 0)}, GC {visitante.get('gc', 0)}."
        )
    if origen.startswith("fallback"):
        return (
            "ALERTA de calidad: no hay historial estadistico suficiente para ambos equipos. "
            "Estos porcentajes son fallback y no deben venderse como prediccion plenamente estudiada."
        )
    return f"Calidad de datos: {calidad}; origen={origen or 'no especificado'}."


def reescribir_razonamiento(partido):
    motivos = "; ".join((partido.get("motivos_sorpresa") or [])[:3])
    partes = [
        f"Probabilidades IA: {texto_probabilidades(partido)}.",
        frase_calidad_datos(partido),
        frase_tipo(partido),
    ]
    if partido.get("favorito_nombre"):
        partes.append(f"Favorito o signo de referencia: {partido.get('favorito_nombre')}.")
    if motivos:
        partes.append(f"Motivos principales: {motivos}.")
    autor = partido.get("cobertura_autor") or {}
    if autor.get("activo") and autor.get("razon"):
        partes.append(f"Cobertura de autor: {autor.get('razon')}")
    x_autor = partido.get("x_de_autor") or {}
    if x_autor.get("activo") and x_autor.get("razon"):
        partes.append(str(x_autor.get("razon")))
    partes.append(f"Decision final: {partido.get('signo_final')}.")
    return " ".join(partes)


def alinear_prediccion(data):
    """Reescribe TEXTOS y COSTE del boleto; NO reparte coberturas.

    Auditoria 26/11/2026 (hallazgos 1 y 30): el unico dueno del reparto de
    dobles y triples es el motor (prioridad_triple/prioridad_doble, con la
    calibracion de fijos, el desacuerdo con el mercado y la cobertura de
    autor). Este script volvia a repartirlos con otro criterio y ponia en el
    doble los dos signos mas probables, con lo que quitaba la X de la
    cobertura de autor (J25, P7 Celta-Villarreal: el motor dijo X2 y se
    publico 12 con cobertura_autor.cubierta=True) y borraba la X de autor de
    los fijos. Ahora se respetan signo_final, tipo, cobertura_autor y
    x_de_autor tal y como llegan; solo se normaliza el tipo a partir del
    signo ya decidido.
    """
    partidos = list(data.get("partidos") or [])
    if not partidos:
        return data

    config = data.setdefault("configuracion", {})
    elige8 = bool(config.get("elige8"))

    for partido in partidos:
        if not isinstance(partido, dict):
            continue
        signo = signo_limpio(partido.get("signo_final"))
        if not signo:
            # Sin decision del motor (prediccion retenida): no se inventa nada.
            continue
        partido["signo_final"] = signo
        partido["tipo"] = tipo_por_signo(signo)
        partido["razonamiento"] = reescribir_razonamiento(partido)

    data["partidos"] = sorted(partidos, key=lambda p: int(p.get("num") or 0))
    data["coste"] = recalcular_coste(data["partidos"], elige8)
    # El criterio de cobertura es el del motor; solo se rellena si falta.
    if not data.get("criterio_cobertura"):
        data["criterio_cobertura"] = (
            "Reparto de dobles y triples decidido por el motor (prioridad de cobertura); "
            "aviso explicito cuando un fijo queda sin cobertura por presupuesto."
        )
    data["resumen"] = {
        "fijos": sum(1 for p in data["partidos"] if p.get("tipo") == "FIJO"),
        "dobles": sum(1 for p in data["partidos"] if p.get("tipo") == "DOBLE"),
        "triples": sum(1 for p in data["partidos"] if p.get("tipo") == "TRIPLE"),
        "elige8_seleccionados": sum(1 for p in data["partidos"] if p.get("elige8")),
        "favoritos_atacables": sum(1 for p in data["partidos"] if p.get("favorito_atacable")),
        "indice_sorpresa_max": max((numero(p.get("indice_sorpresa_quinielistica")) for p in data["partidos"]), default=0),
        "calidad_datos": {
            "alta": sum(1 for p in data["partidos"] if p.get("calidad_datos") == "alta"),
            "media": sum(1 for p in data["partidos"] if p.get("calidad_datos") == "media"),
            "media_baja": sum(1 for p in data["partidos"] if p.get("calidad_datos") == "media_baja"),
            "baja": sum(1 for p in data["partidos"] if p.get("calidad_datos") == "baja"),
        },
    }
    # Reconciliar el boleto millonario con el boleto YA alineado. Bug real
    # (auditoria 01/09/2026): este script reescribe tipo/signo_final pero el
    # boleto_millonario del motor se quedaba con los signos conservadores de
    # ANTES del alineado -la web mostraba "cambia X2 -> X" en un partido
    # cuyo boleto final ya era un fijo "2", y marcaba como cambio cosas que
    # el boleto final ya cubria.
    millonario = data.get("boleto_millonario") or {}
    if millonario.get("cambios_respecto_a_conservadora"):
        finales = {int(p.get("num") or 0): p for p in data["partidos"]}
        cambios_vivos = []
        for cambio in millonario["cambios_respecto_a_conservadora"]:
            final = finales.get(int(cambio.get("num") or 0)) or {}
            signo_final = str(final.get("signo_final") or "")
            cambio["signo_conservador"] = signo_final or cambio.get("signo_conservador")
            signo_mill = str(cambio.get("signo_millonario") or "")
            # Si el boleto final ya cubre el signo millonario (doble/triple
            # que lo incluye), el "cambio" ya no cambia nada: fuera.
            if signo_mill and signo_mill not in signo_final:
                cambios_vivos.append(cambio)
        millonario["cambios_respecto_a_conservadora"] = cambios_vivos
        millonario["total_cambios"] = len(cambios_vivos)
        millonario["resumen"] = (
            f"{len(cambios_vivos)} partido(s) con evidencia contextual real para ir a por la sorpresa."
            if cambios_vivos else
            "Sin cambios: el boleto alineado ya cubre todas las sorpresas con evidencia real."
        )
        vivos_num = {int(c.get("num") or 0) for c in cambios_vivos}
        for p in millonario.get("partidos", []):
            p["es_cambio_millonario"] = int(p.get("num") or 0) in vivos_num
        data["boleto_millonario"] = millonario

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
