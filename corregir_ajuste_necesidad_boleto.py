from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

OLD = r'''    function ajustarPorMotivacionCompetitiva(probs, localComp, visitanteComp) {
      const p = { ...probs };
      const diferencia = valorMotivacionCompetitiva(localComp) - valorMotivacionCompetitiva(visitanteComp);
      if (diferencia) {
        const ajuste = Math.max(Math.min(diferencia * 2.2, 6), -6);
        p["1"] += ajuste;
        p["2"] -= ajuste;
      }
      if (valorMotivacionCompetitiva(localComp) >= 2 && valorMotivacionCompetitiva(visitanteComp) >= 2) {
        p["X"] += 2;
      }
      return normalizarProbabilidades(p);
    }
'''

NEW = r'''    function ajustarPorMotivacionCompetitiva(probs, localComp, visitanteComp) {
      const p = { ...probs };
      const vLocal = valorMotivacionCompetitiva(localComp);
      const vVisitante = valorMotivacionCompetitiva(visitanteComp);
      const diferencia = vLocal - vVisitante;
      if (diferencia) {
        const ajuste = Math.max(Math.min(diferencia * 2.2, 6), -6);
        p["1"] += ajuste;
        p["2"] -= ajuste;
      }

      const localVivo = equipoNecesidadVivaBoleto(localComp);
      const visitanteVivo = equipoNecesidadVivaBoleto(visitanteComp);
      const localCerrado = equipoObjetivoCerradoBoleto(localComp);
      const visitanteCerrado = equipoObjetivoCerradoBoleto(visitanteComp);

      if (visitanteVivo) {
        p["X"] += 6;
        p["2"] += localCerrado ? 9 : 5;
        if (localCerrado) p["1"] -= 5;
      }
      if (localVivo) {
        p["X"] += 6;
        p["1"] += visitanteCerrado ? 9 : 5;
        if (visitanteCerrado) p["2"] -= 5;
      }
      if (localVivo && visitanteVivo) p["X"] += 4;
      if (vLocal >= 2 && vVisitante >= 2) p["X"] += 2;

      return normalizarProbabilidades(p);
    }
'''

APLICADO = '''    function ajustarPorMotivacionCompetitiva(probs, localComp, visitanteComp) {
      const p = { ...probs };
      const vLocal = valorMotivacionCompetitiva(localComp);
'''


def main():
    html = INDEX.read_text(encoding="utf-8")
    if APLICADO in html:
        print("Ajuste de necesidad ya aplicado en probabilidades.")
        return
    if OLD not in html:
        raise SystemExit("No encuentro el bloque antiguo de ajustarPorMotivacionCompetitiva.")
    INDEX.write_text(html.replace(OLD, NEW, 1), encoding="utf-8")
    print("Ajuste de probabilidades por necesidad competitiva aplicado.")


if __name__ == "__main__":
    main()
