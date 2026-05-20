from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

HELPERS = r'''
    function tasaPatronCompetitivo(patrones, clave) {
      return Number(patrones?.patrones?.[clave]?.tasa_sorpresa || 0);
    }

    function ajustarPorPatronesAprendidosWeb(probs, localComp, visitanteComp, patrones) {
      const p = { ...probs };
      const localCerrado = equipoObjetivoCerradoBoleto(localComp);
      const visitanteCerrado = equipoObjetivoCerradoBoleto(visitanteComp);
      const localNecesita = equipoNecesidadVivaBoleto(localComp);
      const visitanteNecesita = equipoNecesidadVivaBoleto(visitanteComp);
      const localDescenso = contieneDescensoVivoBoleto(localComp);
      const visitanteDescenso = contieneDescensoVivoBoleto(visitanteComp);
      const top = signoTopProbabilidad(p);

      if (visitanteCerrado && localNecesita) {
        const tasa = tasaPatronCompetitivo(patrones, "necesitado_local_vs_visitante_objetivo_cerrado");
        p["1"] += 5 + tasa * 0.08;
        p["X"] += 5 + tasa * 0.06;
        p["2"] -= 4;
      }
      if (localCerrado && visitanteNecesita) {
        const tasa = tasaPatronCompetitivo(patrones, "visitante_necesitado_vs_local_objetivo_cerrado");
        p["2"] += 5 + tasa * 0.08;
        p["X"] += 5 + tasa * 0.06;
        p["1"] -= 4;
      }
      if (visitanteDescenso && top === "1") {
        const tasa = tasaPatronCompetitivo(patrones, "visitante_descenso_vs_local_favorito");
        p["X"] += 9 + tasa * 0.07;
        p["2"] += 9 + tasa * 0.07;
        p["1"] -= 8;
      }
      if (localDescenso && top === "2") {
        const tasa = tasaPatronCompetitivo(patrones, "local_descenso_vs_visitante_favorito");
        p["X"] += 9 + tasa * 0.07;
        p["1"] += 9 + tasa * 0.07;
        p["2"] -= 8;
      }
      return normalizarProbabilidades(p);
    }

    function bonusPatronesAprendidosWeb(localComp, visitanteComp, patrones, probs) {
      const localCerrado = equipoObjetivoCerradoBoleto(localComp);
      const visitanteCerrado = equipoObjetivoCerradoBoleto(visitanteComp);
      const localNecesita = equipoNecesidadVivaBoleto(localComp);
      const visitanteNecesita = equipoNecesidadVivaBoleto(visitanteComp);
      const localDescenso = contieneDescensoVivoBoleto(localComp);
      const visitanteDescenso = contieneDescensoVivoBoleto(visitanteComp);
      const top = signoTopProbabilidad(probs);
      let bonus = 0;

      if (visitanteCerrado && localNecesita) bonus += 10 + tasaPatronCompetitivo(patrones, "necesitado_local_vs_visitante_objetivo_cerrado") * 0.35;
      if (localCerrado && visitanteNecesita) bonus += 10 + tasaPatronCompetitivo(patrones, "visitante_necesitado_vs_local_objetivo_cerrado") * 0.35;
      if (visitanteDescenso && top === "1") bonus += 35 + tasaPatronCompetitivo(patrones, "visitante_descenso_vs_local_favorito") * 0.45;
      if (localDescenso && top === "2") bonus += 35 + tasaPatronCompetitivo(patrones, "local_descenso_vs_visitante_favorito") * 0.45;
      if ((localNecesita && visitanteCerrado) || (visitanteNecesita && localCerrado)) {
        bonus += 12 + tasaPatronCompetitivo(patrones, "equipo_necesitado_vs_equipo_sin_objetivo") * 0.25;
      }
      return Math.round(bonus * 10) / 10;
    }
'''


def main():
    html = INDEX.read_text(encoding="utf-8")

    if "function ajustarPorPatronesAprendidosWeb" not in html:
        marker = "\n\n    function puntosCasaFueraTexto(equipo, condicion) {"
        if marker not in html:
            raise SystemExit("No encuentro puntosCasaFueraTexto.")
        html = html.replace(marker, "\n" + HELPERS + marker, 1)

    if "patronesCompetitivos = await fetchJSON" not in html:
        html = html.replace(
            '      const contextoCompetitivo = await fetchJSON("data/memoria_ia/contexto_competitivo.json", {});\n      contextoCompetitivoGlobal = contextoCompetitivo;\n',
            '      const contextoCompetitivo = await fetchJSON("data/memoria_ia/contexto_competitivo.json", {});\n      const patronesCompetitivos = await fetchJSON("data/memoria_ia/patrones_competitivos.json", {});\n      contextoCompetitivoGlobal = contextoCompetitivo;\n',
            1,
        )

    old_probs = '''          let probs = analisis?.probabilidades || { "1": 37, "X": 31, "2": 32 };
          probs = ajustarProbabilidades(probs, p.local, p.visitante, clasif, contextoCompetitivo);

          const riesgo = analisis?.riesgo_sorpresa || "Alto";
'''
    new_probs = '''          let probs = analisis?.probabilidades || { "1": 37, "X": 31, "2": 32 };
          probs = ajustarProbabilidades(probs, p.local, p.visitante, clasif, contextoCompetitivo);
          probs = ajustarPorPatronesAprendidosWeb(probs, contextoCompetitivoLocal, contextoCompetitivoVisitante, patronesCompetitivos);

          const riesgo = analisis?.riesgo_sorpresa || "Alto";
'''
    if "ajustarPorPatronesAprendidosWeb(probs" not in html:
        if old_probs not in html:
            raise SystemExit("No encuentro bloque de probabilidades del boleto IA.")
        html = html.replace(old_probs, new_probs, 1)

    old_bonus = '''          const bonusCompetitivo = bonusRiesgoCompetitivo(contextoCompetitivoLocal, contextoCompetitivoVisitante, probs);
'''
    new_bonus = '''          const bonusCompetitivo = bonusRiesgoCompetitivo(contextoCompetitivoLocal, contextoCompetitivoVisitante, probs)
            + bonusPatronesAprendidosWeb(contextoCompetitivoLocal, contextoCompetitivoVisitante, patronesCompetitivos, probs);
'''
    if "bonusPatronesAprendidosWeb" in html and old_bonus in html:
        html = html.replace(old_bonus, new_bonus, 1)

    INDEX.write_text(html, encoding="utf-8")
    print("Web reforzada con patrones competitivos aprendidos.")


if __name__ == "__main__":
    main()
