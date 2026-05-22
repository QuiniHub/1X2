from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

FUNCIONES = r'''

    function signosElige8Web(item) {
      const partido = item?.partido || item || {};
      const signos = String(item?.signos || partido.signo_final || partido.signo_base || "")
        .replace(/[^1X2]/g, "")
        .split("");
      return signos.length ? Array.from(new Set(signos)) : ["1", "X", "2"];
    }

    function probabilidadCubiertaElige8Web(item) {
      const partido = item?.partido || item || {};
      const probs = partido.probabilidades || {};
      const signos = signosElige8Web(item);
      return Math.min(100, signos.reduce((total, signo) => total + Number(probs[signo] || 0), 0));
    }

    function signoObjetivoElige8Web(item) {
      const partido = item?.partido || item || {};
      const probs = partido.probabilidades || {};
      const signos = signosElige8Web(item);
      return signos.sort((a, b) => Number(probs[b] || 0) - Number(probs[a] || 0))[0] || "";
    }

    function puntuacionElige8CobroWeb(item) {
      const partido = item?.partido || item || {};
      const probCubierta = probabilidadCubiertaElige8Web(item);
      const signos = signosElige8Web(item);
      const incertidumbre = Number(partido.incertidumbre || item?.riesgo || 0);
      const sorpresa = Number(partido.probabilidad_sorpresa || 0);
      let score = probCubierta * 4 - incertidumbre * 0.05 - sorpresa * 0.08;

      if (signos.length === 3) score += 30;
      else if (signos.length === 2) score += 12;
      else if (signos[0] === "X" && probCubierta < 55) score -= 20;

      if (partido.riesgo_necesidad_real || partido.riesgo_necesidad) score -= 1;
      return score;
    }

    function candidatosElige8CobroWeb(detalle) {
      return [...detalle]
        .sort((a, b) => {
          const scoreA = puntuacionElige8CobroWeb(a);
          const scoreB = puntuacionElige8CobroWeb(b);
          if (scoreA !== scoreB) return scoreB - scoreA;
          return probabilidadCubiertaElige8Web(b) - probabilidadCubiertaElige8Web(a);
        })
        .slice(0, 8);
    }
'''

BLOQUE_ESTRATEGIA_ANTIGUO = r'''      const elige8Candidatos = [...detalle]
        .sort((a, b) => {
          const pesoA = a.tipo === "TRIPLE" ? 0 : a.tipo === "DOBLE" ? 1 : 2;
          const pesoB = b.tipo === "TRIPLE" ? 0 : b.tipo === "DOBLE" ? 1 : 2;
          if (pesoA !== pesoB) return pesoA - pesoB;
          return a.riesgo - b.riesgo;
        })
        .slice(0, 8);'''

BLOQUE_ESTRATEGIA_NUEVO = r'''      const elige8Candidatos = candidatosElige8CobroWeb(detalle);'''

BLOQUE_GENERAR_ANTIGUO = r'''      const elige8Set = new Set();
      if (activarElige8) {
        const triplesPrimero = partidos
          .filter(p => triplesSet.has(p.num))
          .sort((a, b) => a.incertidumbre - b.incertidumbre);
        const doblesDespues = partidos
          .filter(p => doblesSet.has(p.num))
          .sort((a, b) => a.incertidumbre - b.incertidumbre);
        const fijosSeguros = partidos
          .filter(p => !triplesSet.has(p.num) && !doblesSet.has(p.num))
          .sort((a, b) => a.incertidumbre - b.incertidumbre);

        [...triplesPrimero, ...doblesDespues, ...fijosSeguros]
          .slice(0, 8)
          .forEach(p => elige8Set.add(p.num));
      }'''

BLOQUE_GENERAR_NUEVO = r'''      const elige8Set = new Set();
      if (activarElige8) {
        candidatosElige8CobroWeb(partidos.map(p => ({
          partido: p,
          num: p.num,
          tipo: p.tipo_apuesta,
          signos: p.signo_final,
          riesgo: p.incertidumbre
        }))).forEach(item => elige8Set.add(item.num));
      }'''

LECTURA_ANTIGUA = "porque concentra la proteccion en los partidos cubiertos y en los fijos mas limpios."
LECTURA_NUEVA = "porque marca los 8 partidos con mayor probabilidad cubierta por la jugada final: triples primero si existen, luego dobles fuertes y despues fijos fiables."


def reemplazar_funciones(html):
    inicio = html.find("    function probabilidadSignoElige8Web(item) {")
    if inicio == -1:
        inicio = html.find("    function signosElige8Web(item) {")
    if inicio != -1:
        fin = html.find("    function evaluarConfiguracionEstrategia(partidosBase, dobles, triples, elige8 = false) {", inicio)
        if fin == -1:
            raise SystemExit("No encuentro final del bloque de funciones Elige 8")
        return html[:inicio] + FUNCIONES + "\n" + html[fin:]

    marcador = "    function evaluarConfiguracionEstrategia(partidosBase, dobles, triples, elige8 = false) {"
    if marcador not in html:
        raise SystemExit("No encuentro donde insertar funciones de Elige 8")
    return html.replace(marcador, FUNCIONES + "\n" + marcador)


def main():
    html = INDEX.read_text(encoding="utf-8")
    original = html

    html = reemplazar_funciones(html)

    if BLOQUE_ESTRATEGIA_ANTIGUO in html:
        html = html.replace(BLOQUE_ESTRATEGIA_ANTIGUO, BLOQUE_ESTRATEGIA_NUEVO)

    if BLOQUE_GENERAR_ANTIGUO in html:
        html = html.replace(BLOQUE_GENERAR_ANTIGUO, BLOQUE_GENERAR_NUEVO)
    elif BLOQUE_GENERAR_NUEVO in html:
        pass
    else:
        raise SystemExit("No encuentro ni el bloque viejo ni el bloque nuevo de Elige 8 en generarBoletoIA")

    html = html.replace(LECTURA_ANTIGUA, LECTURA_NUEVA)

    if html != original:
        INDEX.write_text(html, encoding="utf-8")
        print("Elige 8 web corregido por probabilidad cubierta.")
    else:
        print("Elige 8 web ya estaba corregido por probabilidad cubierta.")


if __name__ == "__main__":
    main()
