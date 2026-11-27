import json
import re
from pathlib import Path

import cronologia_jornadas


# Origenes que NO son una jugada real: el propio fichero realimentandose.
ORIGENES_NO_REALES = {"", "historial_preservado", "prediccion_motor"}

ROOT = Path(__file__).resolve().parent
JORNADAS_DIR = ROOT / "data" / "jornadas"
SALIDA = ROOT / "data" / "historial_quinielas.json"
QUINIELAS_JUGADAS = ROOT / "data" / "quinielas_jugadas.json"


def cargar_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def cargar_json_seguro(path, defecto):
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def signo_valido(signo):
    return str(signo or "").strip().upper() in {"1", "X", "2"}


def nuestra_jugada(partido):
    signo = str(partido.get("signo_nuestro") or "").strip()
    return signo and "NO JUGADA" not in signo.upper()


def resumen_jornada(path):
    data = cargar_json(path)
    partidos = data.get("partidos", [])
    signos = []
    nuestros = []

    for partido in partidos:
        oficial = str(partido.get("signo_oficial") or "").strip().upper()
        nuestro = str(partido.get("signo_nuestro") or "").strip().upper()
        if signo_valido(oficial):
            signos.append(oficial)
        if nuestra_jugada(partido):
            nuestros.append(nuestro)

    pleno = data.get("pleno15") or {}
    pleno_oficial = str(pleno.get("signo_oficial") or pleno.get("resultado") or "").strip()
    pleno_nuestro = str(pleno.get("signo_nuestro") or "").strip()

    numero = int(data.get("jornada") or re.search(r"(\d+)", path.stem).group(1))
    fecha_real = cronologia_jornadas.fecha_real_jornada(data)

    # Auditoria 26/11: partido.signo_nuestro lo escribe actualizar_aprendizaje_ia
    # con la prediccion del MOTOR, no con lo que se jugo. Antes se copiaba a
    # 'nuestra_quiniela' y se marcaba validada=True, y la J22 (no jugada)
    # entro en la memoria como "quiniela nuestra". Una jornada solo queda
    # validada si hay una jugada real en quinielas_jugadas.json
    # (fusionar_validacion); la prediccion del motor va en su propio campo.
    return {
        "jornada": numero,
        "temporada": cronologia_jornadas.temporada_de_fecha(fecha_real, numero) if fecha_real else None,
        "fecha_real": fecha_real.isoformat() if fecha_real else "",
        "fecha": data.get("fecha") or "",
        "fuente": data.get("fuente") or "",
        "resultado_oficial": "".join(signos) if len(signos) == 14 else "Pendiente",
        "pleno15_oficial": pleno_oficial if pleno_oficial and pleno_oficial.lower() != "pendiente" else "Pendiente",
        "nuestra_quiniela": "No validada",
        "pleno15_nuestro": "No validada",
        "prediccion_motor": " ".join(nuestros) if nuestros else "",
        "pleno15_prediccion_motor": pleno_nuestro if pleno_nuestro and "no jugada" not in pleno_nuestro.lower() else "",
        "partidos_con_resultado": len(signos),
        "total_partidos": len(partidos),
        "validada": False,
        "estado": "cerrada" if len(signos) == 14 else "abierta",
    }


def extraer_signos_jugada(valor):
    if isinstance(valor, list):
        return [str(s).strip().upper() for s in valor if str(s).strip()]
    texto = str(valor or "").strip().upper()
    if not texto or texto in {"NO VALIDADA", "NO JUGADA"}:
        return []
    partes = [p for p in texto.split() if p]
    if len(partes) > 1:
        return partes
    if re.fullmatch(r"[12X]{14}", texto):
        return list(texto)
    return []


def jugada_valida(jugada):
    signos = extraer_signos_jugada(jugada.get("signos") or jugada.get("nuestra_quiniela"))
    return len(signos) >= 14


def origen_de(jugada):
    return str(jugada.get("origen") or jugada.get("origen_validacion") or "").strip()


def cargar_validaciones_previas():
    validaciones = {}
    anterior = cargar_json_seguro(SALIDA, {"jornadas": []})
    persistentes = cargar_json_seguro(QUINIELAS_JUGADAS, {"jugadas": []})

    for jugada in anterior.get("jornadas", []):
        # Del fichero anterior solo se conserva lo que vino de una jugada
        # real (tiene origen propio). 'historial_preservado' o sin origen es
        # este mismo fichero realimentandose con signo_nuestro del motor.
        if not jugada.get("validada") or origen_de(jugada) in ORIGENES_NO_REALES:
            continue
        if jugada_valida(jugada):
            validaciones[int(jugada["jornada"])] = jugada

    for jugada in persistentes.get("jugadas", []):
        if jugada_valida(jugada):
            validaciones[int(jugada["jornada"])] = jugada

    return validaciones


def temporada_de_la_jugada(jugada):
    """Temporada en la que se valido la jugada (None si no trae fecha)."""
    if jugada.get("temporada") and not jugada.get("validado_en") and not jugada.get("fecha_validacion"):
        return str(jugada.get("temporada"))
    fecha = cronologia_jornadas.parsear_fecha(jugada.get("validado_en") or jugada.get("fecha_validacion"))
    if fecha is None:
        return str(jugada.get("temporada")) if jugada.get("temporada") else None
    try:
        numero = int(jugada.get("jornada"))
    except (TypeError, ValueError):
        numero = None
    return cronologia_jornadas.temporada_de_fecha(fecha, numero)


def fusionar_validacion(resumen, validaciones):
    previa = validaciones.get(int(resumen["jornada"]))
    if not previa:
        return resumen
    # Mismo numero no basta: la jugada tiene que ser de la misma temporada
    # que el fichero de jornada (la numeracion se reinicia cada agosto).
    temporada_jugada = temporada_de_la_jugada(previa)
    if temporada_jugada and resumen.get("temporada") and temporada_jugada != resumen["temporada"]:
        return resumen
    signos = extraer_signos_jugada(previa.get("signos") or previa.get("nuestra_quiniela"))
    resumen["nuestra_quiniela"] = " ".join(signos[:14])
    resumen["pleno15_nuestro"] = str(previa.get("pleno15") or previa.get("pleno15_nuestro") or "No validada").strip()
    resumen["validada"] = True
    resumen["validado_en"] = previa.get("validado_en") or previa.get("fecha_validacion") or resumen.get("validado_en") or ""
    resumen["elige8"] = previa.get("elige8", resumen.get("elige8", []))
    resumen["origen_validacion"] = origen_de(previa) or "quinielas_jugadas"
    return resumen


def main():
    validaciones = cargar_validaciones_previas()
    jornadas = []
    for path in sorted(JORNADAS_DIR.glob("jornada_*.json"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1))):
        jornadas.append(fusionar_validacion(resumen_jornada(path), validaciones))

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        json.dumps(
            {
                "version": "1.0",
                "total_jornadas": len(jornadas),
                "jornadas": jornadas,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Historial Quiniela generado: {SALIDA} ({len(jornadas)} jornadas)")


if __name__ == "__main__":
    main()
