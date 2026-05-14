import json
import re
from pathlib import Path


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

    return {
        "jornada": int(data.get("jornada") or re.search(r"(\d+)", path.stem).group(1)),
        "fecha": data.get("fecha") or "",
        "fuente": data.get("fuente") or "",
        "resultado_oficial": "".join(signos) if len(signos) == 14 else "Pendiente",
        "pleno15_oficial": pleno_oficial if pleno_oficial and pleno_oficial.lower() != "pendiente" else "Pendiente",
        "nuestra_quiniela": " ".join(nuestros) if nuestros else "No validada",
        "pleno15_nuestro": pleno_nuestro if pleno_nuestro and "no jugada" not in pleno_nuestro.lower() else "No validada",
        "partidos_con_resultado": len(signos),
        "total_partidos": len(partidos),
        "validada": bool(nuestros),
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


def cargar_validaciones_previas():
    validaciones = {}
    anterior = cargar_json_seguro(SALIDA, {"jornadas": []})
    persistentes = cargar_json_seguro(QUINIELAS_JUGADAS, {"jugadas": []})

    for jugada in anterior.get("jornadas", []):
        if jugada_valida(jugada):
            validaciones[int(jugada["jornada"])] = jugada

    for jugada in persistentes.get("jugadas", []):
        if jugada_valida(jugada):
            validaciones[int(jugada["jornada"])] = jugada

    return validaciones


def fusionar_validacion(resumen, validaciones):
    previa = validaciones.get(int(resumen["jornada"]))
    if not previa:
        return resumen
    signos = extraer_signos_jugada(previa.get("signos") or previa.get("nuestra_quiniela"))
    resumen["nuestra_quiniela"] = " ".join(signos[:14])
    resumen["pleno15_nuestro"] = str(previa.get("pleno15") or previa.get("pleno15_nuestro") or "No validada").strip()
    resumen["validada"] = True
    resumen["validado_en"] = previa.get("validado_en") or previa.get("fecha_validacion") or resumen.get("validado_en") or ""
    resumen["elige8"] = previa.get("elige8", resumen.get("elige8", []))
    resumen["origen_validacion"] = previa.get("origen") or "historial_preservado"
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
