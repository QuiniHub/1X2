import json
import re
import unicodedata
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


def clave_equipo(nombre):
    texto = unicodedata.normalize("NFD", str(nombre or "").lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    tokens = re.findall(r"[a-z0-9]+", texto)
    ruido = {"fc", "cf", "cd", "sd", "ud", "rc", "real", "club", "de", "del", "la", "el"}
    clave = "".join(token for token in tokens if token not in ruido)
    alias = {
        "santander": "racingsantander",
    }
    return alias.get(clave, clave)


def buscar(ctx, nombre):
    clave = clave_equipo(nombre)
    for equipo in equipos(ctx):
        if equipo.get("equipo") == nombre or clave_equipo(equipo.get("equipo")) == clave:
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


def overrides_a_validar(ctx):
    """Overrides que hay que exigir HOY (dict nombre -> override) y el motivo
    por el que se ignoran si no aplican.

    Auditoria 26/11/2026 (hallazgos 50, 85, 116, 122, 139): el 01/09/2026 se
    puso una guardia de caducidad en aplicar_objetivos_oficiales_json.py y en
    forzar_overrides.py (overrides_vigentes: sin valido_hasta, caducado o a
    mas de 10 jornadas del final -> el fichero se ignora). Este validador no
    la tenia: seguia exigiendo que los 8 overrides de la ULTIMA jornada 25/26
    estuvieran aplicados y fallo en 555 ciclos seguidos, sin llegar a hacer
    su trabajo real. Ahora usa la MISMA guardia que quien los aplica.
    """
    if not OVR.exists():
        return {}, "no existe objetivos_jornada_actual.json"
    datos = cargar(OVR)
    if not isinstance(datos, dict):
        return {}, "objetivos_jornada_actual.json no es un objeto"
    from forzar_overrides import overrides_vigentes
    vigentes, motivo = overrides_vigentes(datos, ctx)
    if not vigentes:
        return {}, motivo
    equipos_ov = datos.get("equipos")
    return (equipos_ov if isinstance(equipos_ov, dict) else {}), ""


OBJETIVOS_DE_ZONA_BAJA = ("descenso", "permanencia", "salvacion")


def validar_coherencia_tabla(ctx):
    """Contradiccion logica que no depende de overrides: el lider de una liga
    no puede tener como objetivo principal uno de la zona baja.

    Devuelve la lista de contradicciones. NO detiene el script: es un AVISO
    (y una anotacion ::warning:: en Actions). El contexto publicado el
    27/11/2026 la incumple (lideres con objetivo 'descenso') por un defecto
    de generar_contexto_competitivo.py; hacerla bloqueante antes de que ese
    generador este corregido y verificado dejaria a este validador fallando
    cada ciclo, que es justo el hallazgo 50 que se queria cerrar."""
    fallos = []
    for liga in ("primera", "segunda"):
        lista = [e for e in ctx.get(liga, {}).get("equipos", []) if isinstance(e, dict)]
        for equipo in lista:
            try:
                posicion = int(equipo.get("posicion"))
            except (TypeError, ValueError):
                continue
            if posicion != 1:
                continue
            objetivo = equipo.get("objetivo_principal") or {}
            nombre_objetivo = str(objetivo.get("objetivo") or "").lower()
            if objetivo.get("vivo") and any(z in nombre_objetivo for z in OBJETIVOS_DE_ZONA_BAJA):
                fallos.append(
                    f"{equipo.get('equipo')} es lider de {liga} y su objetivo principal es '{nombre_objetivo}'"
                )
    for fallo in fallos:
        print(f"AVISO contexto incoherente: {fallo}")
        print(f"::warning title=Contexto competitivo incoherente::{fallo}")
    return fallos


def main():
    clasif = cargar(CLASIF)
    ctx = cargar(CTX)
    overrides, motivo = overrides_a_validar(ctx)
    validar_fechas(clasif, ctx)
    if overrides:
        validar_overrides(ctx, overrides)
    else:
        print(f"Overrides oficiales no vigentes ({motivo}): no se exigen.")
    incoherencias = validar_coherencia_tabla(ctx)
    if incoherencias:
        print(f"Contexto competitivo fresco; {len(incoherencias)} aviso(s) de coherencia (no bloquean).")
    else:
        print("Contexto competitivo fresco y sin contradicciones oficiales.")


if __name__ == "__main__":
    main()
