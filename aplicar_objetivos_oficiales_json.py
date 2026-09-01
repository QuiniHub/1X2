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
    clave = "".join(token for token in tokens if token not in ruido)
    alias = {
        "santander": "racingsantander",
    }
    return alias.get(clave, clave)


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


def _minimo_partidos_restantes(contexto):
    valores = []
    for liga in ("primera", "segunda"):
        for equipo in contexto.get(liga, {}).get("equipos", []):
            try:
                valores.append(int(equipo.get("partidos_restantes")))
            except (TypeError, ValueError):
                continue
    return min(valores) if valores else None


def overrides_vigentes(datos, contexto):
    """Bug real (01/09/2026): objetivos_jornada_actual.json era un archivo
    de overrides MANUALES escrito el 29/06/2026 para la ULTIMA jornada de
    la temporada 25/26 ("Necesita 1 punto para asegurar Europa League",
    etc.) y, al no tener ni fecha de caducidad ni comprobacion de momento
    de temporada, se siguio aplicando CADA CICLO durante toda la
    pretemporada y el arranque de la 26/27 -inyectando motivacion "maxima"
    y lecturas obsoletas a 8 equipos (incluido un Malaga que cambio de
    division). Doble guardia: caducidad explicita obligatoria (un archivo
    sin valido_hasta se ignora) y el principio del proyecto de que los
    objetivos de tabla solo existen a falta de 10 jornadas o menos."""
    valido_hasta = str(datos.get("valido_hasta") or "")[:10]
    if not valido_hasta:
        return False, "sin campo valido_hasta (archivo de otra jornada/temporada; se ignora)"
    hoy = datetime.now(timezone.utc).date().isoformat()
    if valido_hasta < hoy:
        return False, f"caducado (valido_hasta {valido_hasta} < hoy {hoy})"
    restantes = _minimo_partidos_restantes(contexto)
    if restantes is not None and restantes > 10:
        return False, f"faltan {restantes} jornadas (>10): los overrides de ultima jornada no aplican todavia"
    return True, ""


def aplicar():
    contexto = cargar(CONTEXTO, {})
    datos_overrides = cargar(OBJETIVOS, {})
    overrides = datos_overrides.get("equipos", {})
    if not contexto or not overrides:
        raise SystemExit("Falta contexto_competitivo.json u objetivos_jornada_actual.json")

    vigentes, motivo = overrides_vigentes(datos_overrides, contexto)
    if not vigentes:
        print(json.dumps({"objetivos_oficiales_aplicados": [], "ignorado": motivo}, ensure_ascii=False))
        return

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
