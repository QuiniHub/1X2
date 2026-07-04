"""Validador de esquema de los JSON en data/ — MODO INFORME.

No esta conectado al pipeline (no aparece en SCRIPTS_ACTIVOS de
actualizar_todo.py). Se ejecuta a mano y solo informa; nunca falla con
codigo de salida distinto de 0 y nunca bloquea nada.

Dos tipos de comprobacion, a proposito ninguna sobre VALORES concretos
(ver la limpieza de las comprobaciones de Oviedo/Racing/Deportivo en
control_calidad_actualizacion.py — ese fue el error a no repetir):

1. Universal en los ~153 JSON de data/: que el archivo se pueda parsear
   como JSON, y que no tenga un BOM UTF-8 al principio (la causa real
   del bug de calcular_premios.py/actualizar_aprendizaje_ia.py de hace
   unos dias).
2. Esquema minimo (solo presencia de claves + tipo esperado, nunca
   valores) para un puñado de archivos criticos que si se corrompen
   rompen algo real.

Para las carpetas con muchos archivos repetidos (jornadas/, predicciones/
por jornada) se informa de la distribucion de combinaciones de claves
encontradas, sin tratarlo como error — el esquema evoluciona con el
tiempo y no es corrupcion.
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

BOM = "﻿"

# Esquemas minimos: solo claves obligatorias + tipo esperado. Nunca valores.
ESQUEMAS_ARCHIVO = {
    "historial_quinielas.json": {"version": str, "jornadas": list},
    "quinielas_jugadas.json": {"version": str, "jugadas": list},
    "contexto_equipos.json": {"version": str, "generado_en": str, "equipos": (dict, list)},
    "clasificaciones_oficiales.json": {"primera": list, "segunda": list},
    "estado_jornada_objetivo.json": {"generado_en": str},
    "premios/historial_premios.json": {"jornadas": list},
    "memoria_ia/pesos_dinamicos.json": {"version": str, "referencia": dict, "pesos": dict},
    "predicciones/ultima_prediccion.json": {
        "jornada": int,
        "estado": str,
        "partidos": list,
        "coste": dict,
    },
}

CARPETAS_PATRON = {
    "jornadas/jornada_*.json",
    "predicciones/jornada_*.json",
    "backtesting/pre_cierre/*.json",
}


def tipo_legible(tipos):
    if isinstance(tipos, tuple):
        return " o ".join(t.__name__ for t in tipos)
    return tipos.__name__


def es_tipo_correcto(valor, tipos):
    return isinstance(valor, tipos)


def leer_texto_crudo(path):
    return path.read_bytes()


def validar_universal(path, problemas):
    crudo = leer_texto_crudo(path)
    if crudo.startswith(b"\xef\xbb\xbf"):
        problemas.append(f"{path.relative_to(ROOT)}: tiene BOM UTF-8 al principio (rompe json.loads con encoding='utf-8' estricto).")
    try:
        texto = crudo.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        problemas.append(f"{path.relative_to(ROOT)}: no es UTF-8 valido ({exc}).")
        return None
    if not texto.strip():
        problemas.append(f"{path.relative_to(ROOT)}: archivo vacio.")
        return None
    try:
        return json.loads(texto)
    except json.JSONDecodeError as exc:
        problemas.append(f"{path.relative_to(ROOT)}: JSON invalido ({exc}).")
        return None


def validar_esquema(path, datos, esquema, problemas):
    if not isinstance(datos, dict):
        problemas.append(f"{path.relative_to(ROOT)}: se esperaba un objeto JSON, es {type(datos).__name__}.")
        return
    for clave, tipos in esquema.items():
        if clave not in datos:
            problemas.append(f"{path.relative_to(ROOT)}: falta la clave obligatoria '{clave}'.")
            continue
        if not es_tipo_correcto(datos[clave], tipos):
            problemas.append(
                f"{path.relative_to(ROOT)}: '{clave}' deberia ser {tipo_legible(tipos)}, "
                f"es {type(datos[clave]).__name__}."
            )


def informar_consistencia_carpeta(patron, avisos_informativos):
    archivos = sorted(ROOT.glob(f"data/{patron}"))
    if not archivos:
        return
    conteo = Counter()
    for a in archivos:
        try:
            d = json.loads(a.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if isinstance(d, dict):
            conteo[frozenset(d.keys())] += 1
    if len(conteo) <= 1:
        return
    resumen = ", ".join(f"{n} archivo(s) con {len(claves)} claves" for claves, n in conteo.most_common())
    avisos_informativos.append(f"data/{patron}: {len(archivos)} archivos, {len(conteo)} formas distintas ({resumen}).")


def main():
    problemas = []
    avisos_informativos = []
    total = 0

    for path in sorted(DATA.rglob("*.json")):
        total += 1
        datos = validar_universal(path, problemas)
        if datos is None:
            continue
        rel = str(path.relative_to(DATA)).replace("\\", "/")
        if rel in ESQUEMAS_ARCHIVO:
            validar_esquema(path, datos, ESQUEMAS_ARCHIVO[rel], problemas)

    for patron in CARPETAS_PATRON:
        informar_consistencia_carpeta(patron, avisos_informativos)

    print(f"=== Validacion de esquema de datos (modo informe, {total} archivos JSON) ===\n")
    if problemas:
        print(f"PROBLEMAS ({len(problemas)}):")
        for p in problemas:
            print(f"  - {p}")
    else:
        print("Sin problemas de sintaxis, BOM ni esquema minimo en los archivos criticos.")

    if avisos_informativos:
        print(f"\nINFORMATIVO — formas distintas por carpeta (no es error, puede ser evolucion normal del esquema):")
        for a in avisos_informativos:
            print(f"  - {a}")

    print("\nModo informe: este script no falla ni bloquea nada (siempre termina con codigo 0).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
