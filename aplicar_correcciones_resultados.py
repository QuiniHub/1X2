import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
CORRECCIONES = DATA / "correcciones_resultados.json"


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def reparar_mojibake(texto):
    texto = str(texto or "")
    try:
        reparado = texto.encode("latin1").decode("utf-8")
        if "�" not in reparado:
            return reparado
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return texto


def normalizar(texto):
    texto = reparar_mojibake(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|club|real|de|del|la|el|balompie|futbol)\b", " ", texto)
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def activa(correccion):
    hasta = correccion.get("aplicar_hasta_utc")
    if not hasta:
        return True
    try:
        limite = datetime.fromisoformat(str(hasta).replace("Z", "+00:00"))
    except ValueError:
        return True
    return datetime.now(timezone.utc) <= limite


def mismo_partido(partido, correccion):
    if correccion.get("num") and int(partido.get("num") or 0) == int(correccion["num"]):
        return True
    return (
        normalizar(partido.get("local")) == normalizar(correccion.get("local"))
        and normalizar(partido.get("visitante")) == normalizar(correccion.get("visitante"))
    )


def aplicar_en_jornadas(correcciones):
    cambios = 0
    for correccion in correcciones:
        jornada = correccion.get("jornada")
        if not jornada:
            continue
        path = JORNADAS / f"jornada_{jornada}.json"
        data = cargar_json(path, {})
        if not data:
            continue
        for partido in data.get("partidos", []):
            if not mismo_partido(partido, correccion):
                continue
            resultado = correccion.get("resultado", "Pendiente")
            signo = correccion.get("signo_oficial", "Pendiente")
            if partido.get("resultado") != resultado or partido.get("signo_oficial") != signo:
                partido["resultado"] = resultado
                partido["signo_oficial"] = signo
                partido.pop("actualizado_en", None)
                partido["corregido_en"] = datetime.now(timezone.utc).isoformat()
                partido["correccion_motivo"] = correccion.get("motivo", "")
                cambios += 1
        pleno = data.get("pleno15") or {}
        if pleno and mismo_partido(pleno, correccion):
            resultado = correccion.get("resultado", "Pendiente")
            signo = correccion.get("signo_oficial", "Pendiente")
            if pleno.get("resultado") != resultado or pleno.get("signo_oficial") != signo:
                pleno["resultado"] = resultado
                pleno["signo_oficial"] = signo
                pleno.pop("actualizado_en", None)
                pleno["corregido_en"] = datetime.now(timezone.utc).isoformat()
                pleno["correccion_motivo"] = correccion.get("motivo", "")
                cambios += 1
        data["estado"] = "cerrada" if all(
            str(p.get("signo_oficial", "")).upper() in ("1", "X", "2")
            for p in data.get("partidos", [])
        ) else "en_juego"
        guardar_json(path, data)
    return cambios


def aplicar_en_calendarios(correcciones):
    cambios = 0
    for archivo in (DATA / "calendario_primera.json", DATA / "calendario_segunda.json"):
        data = cargar_json(archivo, {})
        if not data:
            continue
        for correccion in correcciones:
            for jornada in data.get("jornadas", []):
                for partido in jornada.get("partidos", []):
                    if not mismo_partido(partido, correccion):
                        continue
                    resultado = correccion.get("resultado", "Pendiente")
                    nuevo_resultado = "" if str(resultado).lower() == "pendiente" else resultado
                    nuevo_estado = correccion.get("estado_calendario") or ("Programado" if not nuevo_resultado else "Jugado")
                    if partido.get("resultado") != nuevo_resultado or partido.get("estado") != nuevo_estado:
                        partido["resultado"] = nuevo_resultado
                        partido["estado"] = nuevo_estado
                        partido.pop("actualizado_en", None)
                        partido["corregido_en"] = datetime.now(timezone.utc).isoformat()
                        partido["correccion_motivo"] = correccion.get("motivo", "")
                        cambios += 1
        guardar_json(archivo, data)
    return cambios


def main():
    correcciones = [
        c for c in cargar_json(CORRECCIONES, {"correcciones": []}).get("correcciones", [])
        if activa(c)
    ]
    if not correcciones:
        print("Sin correcciones activas.")
        return
    cambios = aplicar_en_jornadas(correcciones) + aplicar_en_calendarios(correcciones)
    print(f"Correcciones de resultados aplicadas: {cambios}")


if __name__ == "__main__":
    main()
