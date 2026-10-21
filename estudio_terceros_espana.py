"""Estudio TERCEROS España (peticion de Marc, 21/10/2026, tras la autopsia
Oporto 0-1 PSV): todos los resultados de esta temporada 2026-27 en Primera,
Segunda y Liga F que salieron con el signo MENOS apostado por la masa LAE
(el "tercero"), en busca de patrones medibles ANTES del cierre.

Hermano de estudio_ver_sorpresas.py (Parte 4, 17/10/2026), que estudio "no
gana el favorito". Aqui el objeto es mas estrecho y mas duro: gana el signo
que ningun % veia. La investigacion mundial dice que la sorpresa concreta no
se predice; la autopsia del Oporto añadio el matiz: lo que si se detecta es
el FAVORITO INFLADO (fama que no se sostiene). Este estudio busca el
equivalente domestico con prerregistro estricto.

TERCERO (definicion): signo oficial == signo con MENOR % de masa LAE del
partido. Sub-tipo "tercero profundo": ademas masa <= 15%.

Dataset: jornadas 1-14 de 2026-27 (cerradas), partidos con
competicion_resuelta en {primera_division, segunda_division, liga_f} y masa
LAE disponible. Fuentes, todas congeladas antes del cierre de cada jornada:
  - data/predicciones/jornada_N.json  (snapshot del motor pre-cierre)
  - data/memoria_ia/porcentajes_lae/2026_2027/jornada_N.json  (masa LAE)
  - data/jornadas/jornada_N.json  (signo_oficial y competicion, post-partido;
    SOLO se usa para el resultado y la etiqueta de liga, jamas como feature)

PRERREGISTRO — hipotesis y umbrales (escritos antes de calcular; no se
amplian despues de ver numeros):

  T1 VALOR OCULTO: prob motor del tercero - masa del tercero >= +5 pts
     (el motor ve mas probable el tercero de lo que la masa lo juega).
  T2 SOBRECOMPRA (proxy domestico del "farol" del Oporto): masa del favorito
     de la masa - prob motor de ese signo >= +10 pts (el publico compra un
     favorito que el motor no sostiene).
  T3 FAVORITO DISTINTO DEL MERCADO: favorito del motor != favorito de
     mercado_losilla en el snapshot (señal viva de La Valiente).
  T4 SIN VENTAJA INFORMATIVA: calidad_datos == "baja" o incertidumbre
     == "alta" en el snapshot.
  T5 PARTIDO SIN DUEÑO: probabilidad_top del motor < 45.
  T6 LIGA: tasa de terceros por competicion (primera vs segunda vs liga_f).
     Contraste prerregistrado: segunda vs primera.
  T7 CRISIS EN EL PARTIDO: ajuste_revulsivo distinto de 0 o
     alertas_motivacion no vacias en el snapshot.
  T8 FORMA DEL TERCERO: cuando sale el tercero, ¿que signo es (1/X/2)?
     Descriptivo, sin umbral.

VEREDICTO prereg por hipotesis (T1-T5, T7): CANDIDATA si la tasa de terceros
con la condicion es >= 1,5x la tasa sin la condicion Y hay >= 6 terceros en
el grupo con condicion; DESCARTADA si tasa <= 1,0x; INDETERMINADA en medio o
con < 6 casos. Con ~25 terceros totales la potencia es poca: este estudio
NO gradua señales por si solo, solo nombra candidatas para seguimiento
prospectivo (cuaderno del ojeador / Laboratorio).

Salida: informe por pantalla + data/memoria_ia/estudio_terceros_espana.json.
Solo lee y reporta: no toca motor ni pipeline.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DATA = RAIZ / "data"
COMPETICIONES = {"primera_division", "segunda_division", "liga_f"}
JORNADAS = range(1, 15)  # cerradas a fecha del estudio


def cargar(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def construir_dataset():
    filas = []
    for n in JORNADAS:
        jor = cargar(DATA / "jornadas" / f"jornada_{n}.json")
        try:
            lae = cargar(DATA / "memoria_ia" / "porcentajes_lae" / "2026_2027" / f"jornada_{n}.json")
        except FileNotFoundError:
            continue
        masa = {p["numero"]: p["porcentajes"] for p in lae.get("partidos", [])}
        try:
            snap = {p["num"]: p for p in cargar(DATA / "predicciones" / f"jornada_{n}.json").get("partidos", [])}
        except FileNotFoundError:
            snap = {}
        for p in jor.get("partidos", []):
            num = p.get("num")
            comp = p.get("competicion_resuelta")
            oficial = p.get("signo_oficial")
            if comp not in COMPETICIONES or oficial not in ("1", "X", "2"):
                continue
            if num not in masa or num not in snap:
                continue
            s = snap[num]
            probs = {k: float(v) for k, v in (s.get("probabilidades") or {}).items() if k in ("1", "X", "2")}
            if len(probs) != 3:
                continue
            mm = {k: float(v) for k, v in masa[num].items()}
            tercero = min(mm, key=lambda x: mm[x])
            fav_masa = max(mm, key=lambda x: mm[x])
            fav_motor = max(probs, key=lambda x: probs[x])
            losilla = s.get("mercado_losilla") or {}
            fav_losilla = None
            if all(k in losilla for k in ("1", "X", "2")):
                fav_losilla = max("1X2", key=lambda k: float(losilla[k]))
            elif all(f"probabilidad_{k}" in losilla for k in ("1", "X", "2")):
                fav_losilla = max("1X2", key=lambda k: losilla[f"probabilidad_{k}"])
            filas.append({
                "jornada": n, "num": num,
                "local": p.get("local"), "visitante": p.get("visitante"),
                "competicion": comp, "oficial": oficial, "resultado": p.get("resultado"),
                "tercero": tercero, "masa_tercero": mm[tercero],
                "es_tercero": oficial == tercero,
                "profundo": oficial == tercero and mm[tercero] <= 15,
                "t1_valor_oculto": probs[tercero] - mm[tercero] >= 5,
                "t2_sobrecompra": mm[fav_masa] - probs.get(fav_masa, 0.0) >= 10,
                "t3_fav_distinto": bool(fav_losilla) and fav_losilla in "1X2" and fav_losilla != fav_motor,
                "t4_sin_ventaja": (s.get("calidad_datos") == "baja") or (s.get("incertidumbre") == "alta"),
                "t5_sin_dueno": float(s.get("probabilidad_top") or max(probs.values())) < 45,
                "t7_crisis": bool(s.get("ajuste_revulsivo")) or bool(s.get("alertas_motivacion")),
                "prob_motor": probs, "masa": mm,
            })
    return filas


def tasa(filas):
    n = len(filas)
    k = sum(1 for f in filas if f["es_tercero"])
    return k, n, (k / n * 100 if n else 0.0)


def contraste(filas, clave):
    con = [f for f in filas if f[clave]]
    sin = [f for f in filas if not f[clave]]
    kc, nc, tc = tasa(con)
    ks, ns, ts = tasa(sin)
    ratio = (tc / ts) if ts else float("inf") if tc else 0.0
    if kc >= 6 and ratio >= 1.5:
        veredicto = "CANDIDATA"
    elif ratio <= 1.0:
        veredicto = "DESCARTADA"
    else:
        veredicto = "INDETERMINADA"
    return {"con": {"terceros": kc, "n": nc, "tasa": round(tc, 1)},
            "sin": {"terceros": ks, "n": ns, "tasa": round(ts, 1)},
            "ratio": round(ratio, 2), "veredicto": veredicto}


def main():
    filas = construir_dataset()
    k, n, t = tasa(filas)
    informe = {
        "generado_en": "2026-10-21",
        "definicion": "tercero = signo oficial con menor masa LAE del partido",
        "dataset": {"jornadas": "1-14 (2026-27)", "partidos": n, "terceros": k,
                    "tasa_global_pct": round(t, 1)},
        "hipotesis": {},
        "por_competicion": {},
        "forma_del_tercero": {},
        "casos": [],
    }
    print(f"Dataset: {n} partidos de liga española (J1-14), {k} terceros ({t:.1f}%)")
    print()
    for clave, nombre in (("t1_valor_oculto", "T1 valor oculto (motor ve el tercero >= masa+5)"),
                          ("t2_sobrecompra", "T2 sobrecompra del favorito (masa >= motor+10)"),
                          ("t3_fav_distinto", "T3 favorito motor != favorito Losilla"),
                          ("t4_sin_ventaja", "T4 calidad baja / incertidumbre alta"),
                          ("t5_sin_dueno", "T5 sin dueño (prob top < 45)"),
                          ("t7_crisis", "T7 revulsivo/alerta de motivacion")):
        r = contraste(filas, clave)
        informe["hipotesis"][clave] = r
        print(f"{nombre}:")
        print(f"   con: {r['con']['terceros']}/{r['con']['n']} ({r['con']['tasa']}%)  "
              f"sin: {r['sin']['terceros']}/{r['sin']['n']} ({r['sin']['tasa']}%)  "
              f"ratio x{r['ratio']}  -> {r['veredicto']}")
    print()
    for comp in sorted({f["competicion"] for f in filas}):
        sub = [f for f in filas if f["competicion"] == comp]
        kc, nc, tc = tasa(sub)
        informe["por_competicion"][comp] = {"terceros": kc, "n": nc, "tasa": round(tc, 1)}
        print(f"T6 {comp:18} {kc:2d}/{nc:3d} terceros ({tc:.0f}%)")
    formas = Counter(f["oficial"] for f in filas if f["es_tercero"])
    informe["forma_del_tercero"] = dict(formas)
    print(f"T8 forma del tercero cuando sale: {dict(formas)}")
    print()
    print("Casos (todos los terceros, con lo que se sabia antes):")
    for f in filas:
        if not f["es_tercero"]:
            continue
        marcas = [m for m, v in (("valor", f["t1_valor_oculto"]), ("sobrec", f["t2_sobrecompra"]),
                                 ("fav!=", f["t3_fav_distinto"]), ("s/vent", f["t4_sin_ventaja"]),
                                 ("s/dueno", f["t5_sin_dueno"]), ("crisis", f["t7_crisis"])) if v]
        caso = {"jornada": f["jornada"], "num": f["num"],
                "partido": f"{f['local']} - {f['visitante']}",
                "competicion": f["competicion"], "salio": f["oficial"],
                "resultado": f["resultado"], "masa_del_signo": f["masa"][f["oficial"]],
                "prob_motor_del_signo": f["prob_motor"][f["oficial"]],
                "profundo": f["profundo"], "señales_prereg": marcas}
        informe["casos"].append(caso)
        print(f"  J{f['jornada']:2d} P{f['num']:2d} [{f['competicion'][:8]:8}] "
              f"{f['local'][:15]:15} - {f['visitante'][:15]:15} salio {f['oficial']} "
              f"({f['resultado']}) masa {f['masa'][f['oficial']]:.0f}% motor "
              f"{f['prob_motor'][f['oficial']]:.0f}% {'PROFUNDO ' if f['profundo'] else ''}"
              f"señales: {','.join(marcas) or 'ninguna'}")
    salida = DATA / "memoria_ia" / "estudio_terceros_espana.json"
    with open(salida, "w", encoding="utf-8") as fh:
        json.dump(informe, fh, ensure_ascii=False, indent=1)
    print(f"\nInforme guardado en {salida}")


if __name__ == "__main__":
    main()
