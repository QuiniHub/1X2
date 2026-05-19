from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

OLD_ALIAS = '''        const piezas = n.match(/[a-z0-9]{4,}/g) || [];
        const score = q.includes(n) ? 100 : piezas.filter(p => q.includes(p)).length * 25;
        if (score >= 25 && !candidatos.some(c => norm(c.equipo) === n)) {
'''
NEW_ALIAS = '''        const sinPrefijo = n.replace(/^(ca|rcd|rc|cf|fc|cd|sd|ud)/, "");
        const alias = Array.from(new Set([n, sinPrefijo].filter(a => a && a.length >= 4)));
        const piezas = alias.flatMap(a => a.match(/[a-z0-9]{4,}/g) || []);
        const score = alias.some(a => q.includes(a)) ? 100 : piezas.filter(p => q.includes(p)).length * 25;
        if (score >= 25 && !candidatos.some(c => norm(c.equipo) === n)) {
'''

OLD_ASCENSO = '''      if (incluye(q, ["ascenso", "subir", "suben", "playoff", "play off", "segunda"])) {
        return respuestaAscensoSegunda(data.clasif);
      }
'''
NEW_ASCENSO = '''      if (incluye(q, ["ascenso", "subir", "suben", "playoff", "play off", "segunda"]) && !incluye(q, ["descenso", "bajar", "permanencia", "salvar"])) {
        return respuestaAscensoSegunda(data.clasif);
      }
'''

CALL_APRENDIZAJE = '''      const aprendizajeErrores = respuestaAprendizajeErrores(q, data);
      if (aprendizajeErrores) return aprendizajeErrores;
'''

FUNCIONES_APRENDIZAJE = r'''
    function jornadasPedidas(q, aprendizaje) {
      const nums = (q.match(/\b\d{1,3}\b/g) || []).map(Number).filter(n => n > 0 && n < 100);
      if (nums.length) return Array.from(new Set(nums));
      const detalle = aprendizaje?.detalle || [];
      const todas = Array.from(new Set(detalle.map(d => Number(d.jornada)).filter(Boolean))).sort((a, b) => a - b);
      if (incluye(q, ["ultimas", "ultimos", "recientes", "anteriores"])) return todas.slice(-5);
      return todas.slice(-5);
    }

    function tipoFalloAprendizaje(item) {
      if (item.acierto) return "Acierto";
      const pronostico = String(item.pronostico || "").toUpperCase().replace(/[^1X2]/g, "");
      const real = String(item.signo_real || "").toUpperCase();
      if (real === "X" && !pronostico.includes("X")) return "No cubrio empate";
      if (pronostico.length <= 1) return "Fijo fallado";
      return "Doble insuficiente";
    }

    function resumenJornadasAprendizaje(detalle) {
      const porJornada = {};
      detalle.forEach(item => {
        const j = Number(item.jornada);
        if (!porJornada[j]) porJornada[j] = { jornada: j, partidos: 0, aciertos: 0, fallos: 0 };
        porJornada[j].partidos += 1;
        if (item.acierto) porJornada[j].aciertos += 1;
        else porJornada[j].fallos += 1;
      });
      return Object.values(porJornada).sort((a, b) => a.jornada - b.jornada);
    }

    function aprendizajesDesdeFallos(fallos, fallosPorTipo) {
      const ideas = [];
      const fijos = fallosPorTipo["Fijo fallado"] || 0;
      const empates = fallosPorTipo["No cubrio empate"] || 0;
      const dobles = fallosPorTipo["Doble insuficiente"] || 0;
      if (fijos) ideas.push(`He fallado ${fijos} fijo(s): debo bajar confianza cuando el favorito tiene margen corto, mala racha o rival con necesidad competitiva.`);
      if (empates) ideas.push(`He dejado fuera ${empates} empate(s): debo subir el peso de la X en partidos cerrados, equipos necesitados de puntuar y cuotas/probabilidades muy juntas.`);
      if (dobles) ideas.push(`He tenido ${dobles} doble(s) insuficiente(s): no basta cubrir dos signos si el signo excluido tiene contexto fuerte de sorpresa.`);
      if (fallos.some(f => String(f.partido || "").toLowerCase().includes("huesca") || String(f.partido || "").toLowerCase().includes("osasuna"))) {
        ideas.push("En equipos metidos en descenso o permanencia, la motivacion puede cambiar el valor del empate o del visitante aunque la forma reciente sea mala.");
      }
      if (!ideas.length) ideas.push("En las jornadas filtradas no veo fallos suficientes para extraer una correccion fuerte; mantendria el modelo actual.");
      return ideas;
    }

    function respuestaAprendizajeErrores(q, data) {
      const preguntaAprendizaje = incluye(q, ["que has aprendido", "aprendido", "aprendizaje", "errores", "fallos", "fallado", "ultimas jornadas", "anteriores predicciones", "resultados reales", "predicciones vs resultados"]);
      if (!preguntaAprendizaje) return "";

      const aprendizaje = data.aprendizaje || {};
      const detalleCompleto = aprendizaje.detalle || [];
      if (!detalleCompleto.length) {
        return "Todavia no tengo detalle suficiente de predicciones nuestras contra resultados reales. Necesito boletos validados en memoria real para aprender con precision.";
      }

      const jornadas = jornadasPedidas(q, aprendizaje);
      const detalle = detalleCompleto.filter(item => jornadas.includes(Number(item.jornada)));
      const base = detalle.length ? detalle : detalleCompleto.slice(-70);
      const fallos = base.filter(item => !item.acierto);
      const aciertos = base.length - fallos.length;
      const fallosPorTipo = fallos.reduce((acc, item) => {
        const tipo = tipoFalloAprendizaje(item);
        acc[tipo] = (acc[tipo] || 0) + 1;
        return acc;
      }, {});
      const resumenJornadas = resumenJornadasAprendizaje(base);
      const precision = base.length ? ((aciertos / base.length) * 100).toFixed(1) : "0.0";
      const peores = fallos.slice(-8).reverse();

      return [
        `He revisado ${base.length} partidos de las jornadas ${resumenJornadas.map(j => j.jornada).join(", ")}. Aciertos: ${aciertos}. Fallos: ${fallos.length}. Precision del bloque: ${precision}%.`,
        `Precision global guardada: ${aprendizaje.precision ?? "-"}% sobre ${aprendizaje.partidos_revisados ?? base.length} partidos revisados.`,
        "",
        "Resumen por jornada:",
        ...resumenJornadas.map(j => `- Jornada ${j.jornada}: ${j.aciertos}/${j.partidos} aciertos, ${j.fallos} fallos.`),
        "",
        "Tipos de error detectados:",
        ...Object.entries(fallosPorTipo).map(([tipo, total]) => `- ${tipo}: ${total}`),
        "",
        "Lo que aprendo:",
        ...aprendizajesDesdeFallos(fallos, fallosPorTipo).map(x => `- ${x}`),
        "",
        "Fallos recientes que debo recordar:",
        ...(peores.length ? peores.map(f => `- J${f.jornada} ${f.partido}: jugue ${f.pronostico}, salio ${f.signo_real} (${f.resultado}). Error: ${tipoFalloAprendizaje(f)}.`) : ["- No hay fallos en este filtro."]),
        "",
        "Decision practica: en la siguiente quiniela debo justificar mejor los fijos, usar dobles cuando haya necesidad real de puntuar y no dejar fuera la X si el partido huele a marcador corto."
      ].join("\n");
    }
'''


def patch(html):
    if OLD_ALIAS in html:
        html = html.replace(OLD_ALIAS, NEW_ALIAS, 1)
    if OLD_ASCENSO in html:
        html = html.replace(OLD_ASCENSO, NEW_ASCENSO, 1)
    if "function respuestaAprendizajeErrores" not in html:
        marcador = "    function respuestaDebatePartido(q, data) {"
        if marcador not in html:
            raise SystemExit("No encuentro respuestaDebatePartido para insertar aprendizaje.")
        html = html.replace(marcador, FUNCIONES_APRENDIZAJE + "\n" + marcador, 1)
    if "const aprendizajeErrores = respuestaAprendizajeErrores(q, data);" not in html:
        marcador = "      const debatePartido = respuestaDebatePartido(q, data);\n      if (debatePartido) return debatePartido;\n"
        if marcador not in html:
            raise SystemExit("No encuentro llamada al debate para insertar aprendizaje.")
        html = html.replace(marcador, CALL_APRENDIZAJE + marcador, 1)
    return html


def main():
    html = INDEX.read_text(encoding="utf-8")
    nuevo = patch(html)
    if nuevo != html:
        INDEX.write_text(nuevo, encoding="utf-8")
        print("Asistente corregido: entiende Osasuna sin prefijo, descenso no dispara ascenso y responde aprendizaje de errores.")
    else:
        print("Asistente ya corregido para objeciones y aprendizaje.")


if __name__ == "__main__":
    main()
