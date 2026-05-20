from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

HELPERS = r'''
    function textoCompetitivoBoleto(equipo) {
      const objetivos = (equipo?.objetivos || [])
        .map(o => `${o.objetivo || ""} ${o.estado || ""} ${o.lectura || ""}`)
        .join(" ");
      return `${objetivos} ${equipo?.situacion_competitiva || ""} ${equipo?.motivacion_competitiva || ""} ${equipo?.motivacion || ""}`.toLowerCase();
    }

    function equipoObjetivoCerradoBoleto(equipo) {
      if (!equipo) return false;
      if ((equipo.objetivos_vivos || []).length) return false;
      const texto = textoCompetitivoBoleto(equipo);
      return texto.includes("asegurado matematicamente")
        || texto.includes("campeon matematico")
        || texto.includes("salvado matematicamente")
        || texto.includes("descendido matematicamente")
        || texto.includes("sin opciones matematicas")
        || texto.includes("sin opciones")
        || texto.includes("no se juega nada");
    }

    function equipoNecesidadVivaBoleto(equipo) {
      if (!equipo) return false;
      if (equipoObjetivoCerradoBoleto(equipo)) return false;
      const texto = textoCompetitivoBoleto(equipo);
      const motivacion = valorMotivacionCompetitiva(equipo);
      return (equipo.objetivos_vivos || []).length > 0
        || motivacion >= 2
        || texto.includes("defiende")
        || texto.includes("aspira")
        || texto.includes("riesgo")
        || texto.includes("descenso")
        || texto.includes("permanencia")
        || texto.includes("playoff")
        || texto.includes("ascenso")
        || texto.includes("conference")
        || texto.includes("europa")
        || texto.includes("champions");
    }

    function contieneDescensoVivoBoleto(equipo) {
      if (!equipo || equipoObjetivoCerradoBoleto(equipo)) return false;
      const texto = textoCompetitivoBoleto(equipo);
      return texto.includes("descenso") || texto.includes("permanencia") || texto.includes("salvarse");
    }

    function signoTopProbabilidad(probs) {
      return Object.entries(probs || {}).sort((a, b) => b[1] - a[1])[0]?.[0] || "X";
    }

    function bonusRiesgoCompetitivo(localComp, visitanteComp, probs) {
      const localVivo = equipoNecesidadVivaBoleto(localComp);
      const visitanteVivo = equipoNecesidadVivaBoleto(visitanteComp);
      const localCerrado = equipoObjetivoCerradoBoleto(localComp);
      const visitanteCerrado = equipoObjetivoCerradoBoleto(visitanteComp);
      const top = signoTopProbabilidad(probs);
      const valores = Object.values(probs || {}).sort((a, b) => b - a);
      const margen = valores.length > 1 ? valores[0] - valores[1] : 0;
      let bonus = 0;

      if (localVivo || visitanteVivo) bonus += 10;
      if (localVivo && visitanteVivo) bonus += 8;
      if (localVivo && visitanteCerrado) bonus += 16;
      if (visitanteVivo && localCerrado) bonus += 16;
      if (visitanteVivo && top === "1") bonus += 16;
      if (localVivo && top === "2") bonus += 16;
      if (contieneDescensoVivoBoleto(localComp) || contieneDescensoVivoBoleto(visitanteComp)) bonus += 10;
      if ((probs?.["X"] || 0) >= 30) bonus += 6;
      if (margen < 18) bonus += 8;
      if (valores[0] < 55) bonus += 8;

      return Math.min(bonus, 44);
    }

    function puntosCasaFueraTexto(equipo, condicion) {
      const datos = equipo?.[condicion] || {};
      const pj = datos.pj || datos.partidos || datos.jugados || 0;
      const pts = datos.puntos ?? datos.pts ?? datos.puntos_totales;
      if (!pj && pts === undefined) return "sin dato suficiente";
      return `${pts ?? 0} pts en ${pj || "-"} partidos`;
    }
'''

AJUSTAR_OLD = r'''    function ajustarPorMotivacionCompetitiva(probs, localComp, visitanteComp) {
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

AJUSTAR_NEW = r'''    function ajustarPorMotivacionCompetitiva(probs, localComp, visitanteComp) {
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


def reemplazar_obligatorio(html, viejo, nuevo, descripcion):
    if nuevo.strip() in html:
        return html
    if viejo not in html:
        raise SystemExit(f"No encuentro bloque para {descripcion}.")
    return html.replace(viejo, nuevo, 1)


def patch(html):
    if "function bonusRiesgoCompetitivo" not in html:
        marcador = "\n\n    function objetivoPrincipalCompetitivo(equipo) {"
        if marcador not in html:
            raise SystemExit("No encuentro objetivoPrincipalCompetitivo.")
        html = html.replace(marcador, "\n" + HELPERS + marcador, 1)

    if "const localVivo = equipoNecesidadVivaBoleto(localComp);" not in html:
        html = reemplazar_obligatorio(html, AJUSTAR_OLD, AJUSTAR_NEW, "ajuste por motivacion")

    inc_old = '''    function incertidumbre(probs, riesgo) {
      const valores = Object.values(probs).sort((a, b) => b - a);
      let puntos = 100 - (valores[0] - valores[1]) + probs["X"] * 0.35;
      if (riesgo === "Alto") puntos += 12;
      if (riesgo === "Medio") puntos += 6;
      return puntos;
    }
'''
    inc_new = '''    function incertidumbre(probs, riesgo, bonusCompetitivo = 0) {
      const valores = Object.values(probs).sort((a, b) => b - a);
      let puntos = 100 - (valores[0] - valores[1]) + probs["X"] * 0.35;
      if (riesgo === "Alto") puntos += 12;
      if (riesgo === "Medio") puntos += 6;
      return puntos + bonusCompetitivo;
    }
'''
    if "bonusCompetitivo = 0" not in html:
        html = reemplazar_obligatorio(html, inc_old, inc_new, "incertidumbre competitiva")

    base_old = '''          const riesgo = analisis?.riesgo_sorpresa || "Alto";
          const signoBase = signoMasProbable(probs);

          return {
'''
    base_new = '''          const riesgo = analisis?.riesgo_sorpresa || "Alto";
          const signoBase = signoMasProbable(probs);
          const bonusCompetitivo = bonusRiesgoCompetitivo(contextoCompetitivoLocal, contextoCompetitivoVisitante, probs);

          return {
'''
    if "const bonusCompetitivo = bonusRiesgoCompetitivo" not in html:
        html = reemplazar_obligatorio(html, base_old, base_new, "bonus por necesidad")

    riesgo_old = '''            confianza: analisis?.confianza || "Baja",
            riesgo,
            incertidumbre: incertidumbre(probs, riesgo)
'''
    riesgo_new = '''            confianza: analisis?.confianza || "Baja",
            riesgo,
            bonus_competitivo: bonusCompetitivo,
            riesgo_necesidad: bonusCompetitivo >= 18,
            incertidumbre: incertidumbre(probs, riesgo, bonusCompetitivo)
'''
    if "bonus_competitivo: bonusCompetitivo" not in html:
        html = reemplazar_obligatorio(html, riesgo_old, riesgo_new, "riesgo de necesidad")

    tipo_old = '      let lecturaTipo = "Se deja fijo porque el signo principal mantiene ventaja suficiente frente a las alternativas.";\n'
    tipo_new = '''      let lecturaTipo = partido.riesgo_necesidad
        ? "No es un fijo tranquilo: queda como signo base solo si faltan dobles/triples, porque la necesidad competitiva obliga a revisar cobertura."
        : "Se deja fijo porque el signo principal mantiene ventaja suficiente frente a las alternativas.";
'''
    if "No es un fijo tranquilo" not in html:
        html = reemplazar_obligatorio(html, tipo_old, tipo_new, "texto de fijo con necesidad")

    forma_old = '''      const formaLocal = leerTendencia(local, "forma_5_pts");
      const formaVisitante = leerTendencia(visitante, "forma_5_pts");
'''
    forma_new = '''      const formaLocal = leerTendencia(local, "forma_5_pts");
      const formaVisitante = leerTendencia(visitante, "forma_5_pts");
      const forma10Local = leerTendencia(local, "forma_10_pts");
      const forma10Visitante = leerTendencia(visitante, "forma_10_pts");
'''
    if "forma10Local" not in html:
        html = reemplazar_obligatorio(html, forma_old, forma_new, "forma ultimos 10")

    lectura_old = '''      const lecturaForma = `Dinámica reciente: ${partido.local} suma ${formaLocal} puntos en los últimos 5 y ${partido.visitante} suma ${formaVisitante}. ${diferenciaForma > 2 ? "La forma local llega mejor." : diferenciaForma < -2 ? "La forma visitante llega mejor." : "La forma reciente está bastante equilibrada."}`;
      const lecturaGoles = `Goles: ${partido.local} promedia ${numeroSeguro(gfLocal)} a favor y ${numeroSeguro(gcLocal)} en contra; ${partido.visitante} promedia ${numeroSeguro(gfVisitante)} a favor y ${numeroSeguro(gcVisitante)} en contra.`;
'''
    lectura_new = '''      const lecturaForma = `Dinámica reciente: ${partido.local} suma ${formaLocal}/${forma10Local} puntos en últimos 5/10 y ${partido.visitante} suma ${formaVisitante}/${forma10Visitante}. ${diferenciaForma > 2 ? "La forma local llega mejor." : diferenciaForma < -2 ? "La forma visitante llega mejor." : "La forma reciente está bastante equilibrada."}`;
      const lecturaCasaFuera = `Casa/fuera: ${partido.local} en casa ${puntosCasaFueraTexto(local, "local")}; ${partido.visitante} fuera ${puntosCasaFueraTexto(visitante, "visitante")}.`;
      const lecturaGoles = `Goles: ${partido.local} promedia ${numeroSeguro(gfLocal)} a favor y ${numeroSeguro(gcLocal)} en contra; ${partido.visitante} promedia ${numeroSeguro(gfVisitante)} a favor y ${numeroSeguro(gcVisitante)} en contra.`;
'''
    if "const lecturaCasaFuera" not in html:
        html = reemplazar_obligatorio(html, lectura_old, lectura_new, "lectura casa/fuera")

    return_old = '''      return `${lecturaPuntos} ${lecturaForma} ${lecturaGoles} ${lecturaRachas} ${lecturaProb} ${contextoLocal} ${contextoVisitante} ${lecturaAlertas} ${lecturaTipo} Decisión final: ${signo}.`;
'''
    return_new = '''      const lecturaNecesidad = partido.riesgo_necesidad ? `Riesgo competitivo extra: ${partido.bonus_competitivo} puntos; conviene desconfiar del fijo si no entra en cobertura.` : "";
      return `${lecturaPuntos} ${lecturaForma} ${lecturaCasaFuera} ${lecturaGoles} ${lecturaRachas} ${lecturaProb} ${contextoLocal} ${contextoVisitante} ${lecturaAlertas} ${lecturaNecesidad} ${lecturaTipo} Decisión final: ${signo}.`;
'''
    if "Riesgo competitivo extra" not in html:
        html = reemplazar_obligatorio(html, return_old, return_new, "explicacion de necesidad")

    ui_old = '<small>Confianza: ${p.confianza} · Riesgo: ${p.riesgo}</small>'
    ui_new = '<small>Confianza: ${p.confianza} · Riesgo: ${p.riesgo}${p.riesgo_necesidad ? " · Necesidad competitiva alta" : ""}</small>'
    if "Necesidad competitiva alta" not in html:
      if ui_old not in html:
        raise SystemExit("No encuentro linea de confianza/riesgo.")
      html = html.replace(ui_old, ui_new, 1)

    return html


def main():
    html = INDEX.read_text(encoding="utf-8")
    nuevo = patch(html)
    if nuevo != html:
        INDEX.write_text(nuevo, encoding="utf-8")
        print("Coberturas por necesidad competitiva reforzadas en el boleto IA.")
    else:
        print("Coberturas por necesidad competitiva ya estaban aplicadas.")


if __name__ == "__main__":
    main()
