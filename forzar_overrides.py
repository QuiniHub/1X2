import json
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MEM = ROOT / "data" / "memoria_ia"
CTX = MEM / "contexto_competitivo.json"
OVR = MEM / "objetivos_jornada_actual.json"
INDEX = ROOT / "index.html"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def key(value):
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    tokens = re.findall(r"[a-z0-9]+", text)
    noise = {"real", "club", "fc", "cf", "cd", "sd", "ud", "rc", "de", "del", "la", "el"}
    result = "".join(token for token in tokens if token not in noise)
    aliases = {
        "santander": "racingsantander",
    }
    return aliases.get(result, result)


def find(name, overrides):
    if name in overrides:
        return overrides[name]
    name_key = key(name)
    for override_name, override in overrides.items():
        if key(override_name) == name_key:
            return override
    return None


def obj(override):
    result = {
        "objetivo": override.get("objetivo_principal", "situacion_final"),
        "estado": override.get("estado", "situacion_final"),
        "vivo": bool(override.get("vivo", False)),
        "terminal": bool(override.get("terminal", not override.get("vivo", False))),
        "override_oficial_jornada": True,
        "lectura": override.get("lectura", "Objetivo oficial aplicado."),
    }
    for field in [
        "puntos_necesarios_para_asegurar",
        "puntos_necesarios_para_entrar",
        "puntos_necesarios_para_salvarse",
        "depende_de_rivales",
    ]:
        if field in override:
            result[field] = override[field]
    return result


def forzar_index_elige8_estable():
    if not INDEX.exists():
        return
    texto = INDEX.read_text(encoding="utf-8")
    original = texto
    texto = texto.replace("\n        && !activarElige8", "")
    texto = texto.replace("\n        && !activarElige8\n", "\n")
    if texto != original:
        INDEX.write_text(texto, encoding="utf-8")
        print("Index corregido: Elige 8 ya no fuerza recalculo del boleto base.")


def main():
    ctx = load(CTX)
    overrides = load(OVR).get("equipos", {})
    for liga in ["primera", "segunda"]:
        for equipo in ctx.get(liga, {}).get("equipos", []):
            override = find(equipo.get("equipo"), overrides)
            if not override:
                continue
            objetivo = obj(override)
            equipo["objetivos"] = [objetivo]
            equipo["objetivo_principal"] = objetivo
            equipo["objetivos_vivos"] = [objetivo] if objetivo.get("vivo") else []
            equipo["motivacion_competitiva"] = override.get("motivacion_competitiva", "baja")
            equipo["motivacion"] = equipo["motivacion_competitiva"]
            equipo["situacion_competitiva"] = override.get("situacion_competitiva", objetivo.get("estado"))
            equipo["lectura_resumen"] = objetivo["lectura"]
            equipo["override_oficial_jornada"] = True
    ctx["version"] = "1.4"
    save(CTX, ctx)

    forzar_index_elige8_estable()

    try:
        from alinear_boleto_con_analisis import main as alinear_boleto
        from validar_publicacion_autonoma import main as validar_publicacion
        alinear_boleto()
        validar_publicacion()
    except ImportError:
        print("Validadores finales no disponibles en este ciclo.")

    print("ok")


if __name__ == "__main__":
    main()
