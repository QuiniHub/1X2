import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MEMORIA = ROOT / "data" / "memoria_ia"
CONTEXTO = MEMORIA / "contexto_competitivo.json"
OBJETIVOS = MEMORIA / "objetivos_jornada_actual.json"


def cargar(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def norm(texto):
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    tokens = re.findall(r"[a-z0-9]+", texto)
    ruido = {"fc", "cf", "cd", "sd", "ud", "rc", "real", "club", "de", "del", "la", "el"}
    return "".join(token for token in tokens if token not in ruido)


def encontrar_override(nombre, overrides):
    if nombre in overrides:
        return overrides[nombre]
    clave = norm(nombre)
    for k, v in overrides.items():
        if norm(k) == clave:
            return v
    return None


def objetivo_desde_override(override):
    objetivo = {
        "objetivo": override.get("objetivo_principal", "situacion_final"),
        "estado": override.get("estado", "no_se_juega_nada_clasificatorio"),
        "vivo": bool(override.get("vivo", False)),
        "terminal": bool(override.get("terminal", not override.get("vivo", False))),
        "override_oficial_jornada": True,
        "lectura": override.get("lectura", "Objetivo oficial de jornada aplicado."),
    }
    for campo in (
        "puntos_necesarios_para_asegurar",
        "puntos_necesarios_para_entrar",
        "depende_de_rivales",
    ):
        if campo in override:
            objetivo[campo] = override[campo]
    return objetivo


def aplicar():
    contexto = cargar(CONTEXTO, {})
    overrides = cargar(OBJETIVOS, {}).get("equipos", {})
    if not contexto or not overrides:
        raise SystemExit("Falta contexto_competitivo.json u objetivos_jornada_actual.json")

    aplicados = []
    for liga in ("primera", "segunda"):
        for equipo in contexto.get(liga, {}).get("equipos", []):
            override = encontrar_override(equipo.get("equipo"), overrides)
            if not override:
                continue
            objetivo = objetivo_desde_override(override)
            anteriores = [o for o in equipo.get("objetivos", []) if not o.get("override_oficial_jornada")]
            equipo["objetivos"] = [objetivo] + anteriores
            equipo["objetivo_principal"] = objetivo
            equipo["objetivos_vivos"] = [objetivo] if objetivo.get("vivo") else []
            equipo["motivacion_competitiva"] = override.get("motivacion_competitiva", "baja")
            equipo["motivacion"] = equipo["motivacion_competitiva"]
            equipo["situacion_competitiva"] = override.get("situacion_competitiva", objetivo.get("estado"))
            equipo["lectura_resumen"] = objetivo.get("lectura")
            equipo["override_oficial_jornada"] = True
            aplicados.append(equipo.get("equipo"))

    contexto["version"] = "1.3"
    contexto["objetivos_oficiales_jornada"] = {
        "aplicados_en": datetime.now(timezone.utc).isoformat(),
        "fuente": "data/memoria_ia/objetivos_jornada_actual.json",
        "equipos": aplicados,
    }
    guardar(CONTEXTO, contexto)
    print(json.dumps({"objetivos_oficiales_aplicados": aplicados}, ensure_ascii=False))


if __name__ == "__main__":
    aplicar()
