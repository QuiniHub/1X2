import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLASIF = ROOT / "clasificaciones.json"
CLASIF_OFICIAL = ROOT / "data" / "clasificaciones_oficiales.json"
CTX = ROOT / "data" / "memoria_ia" / "contexto_competitivo.json"
OVR = ROOT / "data" / "memoria_ia" / "objetivos_jornada_actual.json"
MAX_EDAD_MIN = 120

PROHIBIDAS_SALVADO = (
    "riesgo_descenso",
    "permanencia_por_cerrar",
    "en_descenso_con_opciones",
    "necesita 1 punto para salvarse",
    "necesita 1 punto para salvarse por puntos",
)


def cargar(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fecha(valor):
    if not valor:
        return None
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def error(msg):
    raise SystemExit(msg)


def texto_equipo(equipo):
    partes = [equipo.get("lectura_resumen", ""), equipo.get("situacion_competitiva", "")]
    for objetivo in equipo.get("objetivos", []):
        partes.extend(str(objetivo.get(k, "")) for k in ("objetivo", "estado", "lectura"))
    return " ".join(partes).lower()


def equipos(ctx):
    for liga in ("primera", "segunda"):
        for equipo in ctx.get(liga, {}).get("equipos", []):
            yield equipo


def buscar(ctx, nombre):
    for equipo in equipos(ctx):
        if equipo.get("equipo") == nombre:
            return equipo
    return None


def fecha_clasificacion(clasif):
    for campo in ("validado_en", "actualizado_en"):
        f = fecha(clasif.get(campo))
        if f:
            return f
    if CLASIF_OFICIAL.exists():
        oficial = cargar(CLASIF_OFICIAL)
        for campo in ("validado_en", "actualizado_en"):
            f = fecha(oficial.get(campo))
            if f:
                return f
    return None


def validar_fechas(clasif, ctx):
    ahora = datetime.now(timezone.utc)
    f_clasif = fecha_clasificacion(clasif)
    f_ctx = fecha(ctx.get("generado_en"))
    if not f_clasif:
        error("No hay fecha valida de clasificacion en clasificaciones.json ni data/clasificaciones_oficiales.json")
    if not f_ctx:
        error("contexto_competitivo.json no tiene generado_en valido")
    if ahora - f_clasif > timedelta(minutes=MAX_EDAD_MIN):
        error(f"clasificacion no validada recientemente: {f_clasif.isoformat()}")
    if ahora - f_ctx > timedelta(minutes=MAX_EDAD_MIN):
        error(f"contexto_competitivo.json demasiado antiguo: {f_ctx.isoformat()}")
    if f_ctx + timedelta(seconds=5) < f_clasif:
        error("contexto_competitivo.json es anterior a la clasificacion fresca")


def validar_overrides(ctx, overrides):
    fallos = []
    for nombre, ov in overrides.items():
        equipo = buscar(ctx, nombre)
        if not equipo:
            fallos.append(f"No encuentro equipo con override: {nombre}")
            continue
        if not equipo.get("override_oficial_jornada"):
            fallos.append(f"Override no aplicado: {nombre}")
        if len(equipo.get("objetivos", [])) != 1:
            fallos.append(f"{nombre}: conserva objetivos antiguos contradictorios")
        objetivo = equipo.get("objetivo_principal") or {}
        if objetivo.get("estado") != ov.get("estado"):
            fallos.append(f"{nombre}: estado {objetivo.get('estado')} != override {ov.get('estado')}")
        if equipo.get("motivacion_competitiva") != ov.get("motivacion_competitiva"):
            fallos.append(f"{nombre}: motivacion no coincide con override")
        texto = texto_equipo(equipo)
        if ov.get("estado") in {"salvado_matematicamente", "asegurado_matematicamente", "sin_opciones_matematicas"}:
            for frase in PROHIBIDAS_SALVADO:
                if frase in texto:
                    fallos.append(f"{nombre}: aparece frase prohibida: {frase}")
    if fallos:
        error("\n".join(fallos))


def main():
    clasif = cargar(CLASIF)
    ctx = cargar(CTX)
    overrides = cargar(OVR).get("equipos", {}) if OVR.exists() else {}
    validar_fechas(clasif, ctx)
    validar_overrides(ctx, overrides)
    print("Contexto competitivo fresco y sin contradicciones oficiales.")


if __name__ == "__main__":
    main()
