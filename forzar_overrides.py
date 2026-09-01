import json
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MEM = ROOT / "data" / "memoria_ia"
CTX = MEM / "contexto_competitivo.json"
OVR = MEM / "objetivos_jornada_actual.json"


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
    aliases = {"santander": "racingsantander"}
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


def _minimo_partidos_restantes(ctx):
    valores = []
    for liga in ("primera", "segunda"):
        for equipo in ctx.get(liga, {}).get("equipos", []):
            try:
                valores.append(int(equipo.get("partidos_restantes")))
            except (TypeError, ValueError):
                continue
    return min(valores) if valores else None


def overrides_vigentes(datos, ctx):
    # Misma guardia que aplicar_objetivos_oficiales_json.py (este script
    # aplica EL MISMO archivo) -ver alli el bug real del 01/09/2026: los
    # overrides manuales de la ultima jornada 25/26 se aplicaron cada
    # ciclo durante meses por no tener caducidad ni gate de momento de
    # temporada.
    from datetime import datetime, timezone
    valido_hasta = str(datos.get("valido_hasta") or "")[:10]
    if not valido_hasta:
        return False, "sin campo valido_hasta (archivo de otra jornada/temporada; se ignora)"
    hoy = datetime.now(timezone.utc).date().isoformat()
    if valido_hasta < hoy:
        return False, f"caducado (valido_hasta {valido_hasta} < hoy {hoy})"
    restantes = _minimo_partidos_restantes(ctx)
    if restantes is not None and restantes > 10:
        return False, f"faltan {restantes} jornadas (>10)"
    return True, ""


def main():
    ctx = load(CTX)
    datos = load(OVR)
    overrides = datos.get("equipos", {})
    vigentes, motivo = overrides_vigentes(datos, ctx)
    if not vigentes:
        print(f"Overrides competitivos ignorados: {motivo}")
        return
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
    print("Overrides competitivos aplicados.")


if __name__ == "__main__":
    main()
