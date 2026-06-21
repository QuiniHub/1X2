from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
VERSION_JS = "20260621-bloqueo-prediccion"


def asegurar_bloqueo_prediccion_web(texto: str) -> str:
    helper = '''
    function prediccionBloqueadaQuinielaIA(prediccion = {}) {
      const estado = String(prediccion?.estado || "").toLowerCase();
      return prediccion?.prediccion_disponible === false
        || prediccion?.aprendizaje_pendiente === true
        || estado.includes("bloqueada")
        || estado.includes("pendiente_cierre");
    }

'''
    if "function prediccionBloqueadaQuinielaIA" not in texto:
        texto = texto.replace("    async function abrirQuinielaIA(jornada) {", helper + "    async function abrirQuinielaIA(jornada) {")

    viejo = '''      const data = await fetchJSON(`data/jornadas/jornada_${jornada}.json`, null);
      if (!data) {
        const alternativa = jornadaAlternativaQuinielaIA(jornada);
        if (alternativa && alternativa !== Number(jornada)) {
          await abrirQuinielaIA(alternativa);
          return;
        }
        document.getElementById("boleto-ia").innerHTML = "No se pudo cargar esta jornada.";
        return;
      }

      partidosJornadaIA = data.partidos || [];
      pleno15JornadaIA = data.pleno15 || null;
'''
    nuevo = '''      const data = await fetchJSON(`data/jornadas/jornada_${jornada}.json`, null);
      const prediccionEstado = await fetchJSON(`data/predicciones/jornada_${jornada}.json`, {});
      const prediccionBloqueada = prediccionBloqueadaQuinielaIA(prediccionEstado);
      if (!data) {
        const alternativa = jornadaAlternativaQuinielaIA(jornada);
        if (alternativa && alternativa !== Number(jornada)) {
          await abrirQuinielaIA(alternativa);
          return;
        }
        document.getElementById("boleto-ia").innerHTML = "No se pudo cargar esta jornada.";
        return;
      }

      partidosJornadaIA = data.partidos || [];
      pleno15JornadaIA = data.pleno15 || null;
'''
    texto = texto.replace(viejo, nuevo)

    viejo = '''      const validacion = cargarValidacionLocal(jornada);
      const estado = estadoMemoriaJornada(validacion);
      document.getElementById("titulo-jornada-ia").innerHTML = validacion
        ? `Jornada ${jornada} <span class="${estado.clase}">· ${estado.etiqueta}</span>`
        : `Jornada ${jornada}`;

      if (validacion) pintarBoletoValidadoEnQuinielas(data, validacion);
      else pintarBoletoVacioIA();
      calcularImporteIA();
'''
    nuevo = '''      const validacion = prediccionBloqueada ? null : cargarValidacionLocal(jornada);
      const estado = estadoMemoriaJornada(validacion);
      document.getElementById("titulo-jornada-ia").innerHTML = prediccionBloqueada
        ? `Jornada ${jornada} <span class="small-muted">· Predicción bloqueada</span>`
        : validacion
          ? `Jornada ${jornada} <span class="${estado.clase}">· ${estado.etiqueta}</span>`
          : `Jornada ${jornada}`;

      if (prediccionBloqueada) {
        ultimoBoletoIAGenerado = null;
        document.getElementById("activar-elige8").checked = false;
        pintarBoletoVacioIA();
        const aviso = prediccionEstado?.mensaje || "Predicción bloqueada hasta cerrar y aprender la jornada anterior.";
        document.getElementById("boleto-ia").insertAdjacentHTML("afterbegin", `<p class="small-muted">${aviso}</p>`);
      } else if (validacion) pintarBoletoValidadoEnQuinielas(data, validacion);
      else pintarBoletoVacioIA();
      calcularImporteIA();
'''
    texto = texto.replace(viejo, nuevo)
    return texto


def aplicar_reemplazos(texto: str) -> str:
    texto = texto.replace("\n        && !activarElige8", "")
    texto = texto.replace("\n        && !activarElige8\n", "\n")
    texto = texto.replace(
        "        && dobles === 0\n        && triples === 0\n        && prediccionBackend.configuracion?.cobertura_auto;",
        "        && ((dobles === 0 && triples === 0) || (dobles === Number(prediccionBackend.resumen?.dobles ?? prediccionBackend.configuracion?.dobles ?? 0) && triples === Number(prediccionBackend.resumen?.triples ?? prediccionBackend.configuracion?.triples ?? 0)))\n        && prediccionBackend.configuracion?.cobertura_auto;",
    )
    texto = texto.replace(
        '<script src="resumen_rapido_metricas.js"></script>',
        f'<script src="resumen_rapido_metricas.js?v={VERSION_JS}"></script>',
    )
    texto = texto.replace(
        'pronostico: pleno.pronostico || pleno.signo_nuestro || pleno.resultado || "1-1",',
        'pronostico: (pleno.pronostico && !["Pendiente", "No jugada", "No validada"].includes(pleno.pronostico)) ? pleno.pronostico : "1-1",',
    )
    texto = asegurar_bloqueo_prediccion_web(texto)
    return texto


def main() -> None:
    if not INDEX.exists():
        raise SystemExit("No existe index.html")
    original = INDEX.read_text(encoding="utf-8")
    actualizado = aplicar_reemplazos(original)
    if actualizado != original:
        INDEX.write_text(actualizado, encoding="utf-8")
        print("Web estabilizada: bloqueo predictivo, Elige 8, Pleno al 15 y cache JS.")
    else:
        print("Web ya estaba estabilizada.")


if __name__ == "__main__":
    main()
