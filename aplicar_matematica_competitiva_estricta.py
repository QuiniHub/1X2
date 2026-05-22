from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTEXTO = ROOT / "generar_contexto_competitivo.py"
ACTUALIZAR = ROOT / "actualizar_todo.py"
WORKFLOW = ROOT / ".github" / "workflows" / "main.yml"


def cambia(texto, viejo, nuevo, etiqueta):
    if viejo in texto:
        return texto.replace(viejo, nuevo, 1), True
    if nuevo in texto:
        return texto, False
    raise SystemExit(f"No encuentro bloque: {etiqueta}")


def parchear_contexto():
    texto = CONTEXTO.read_text(encoding="utf-8")
    original = texto

    texto, _ = cambia(
        texto,
        '''ESTADOS_VIVOS = {
    "defiende_liderato",
    "defiende_plaza",
    "aspira_matematicamente",
    "aspira_por_desempate_o_fallo_ajeno",
    "en_descenso_con_opciones",
    "riesgo_descenso",
    "permanencia_por_cerrar",
}''',
        '''ESTADOS_VIVOS = {
    "defiende_liderato",
    "defiende_plaza",
    "aspira_matematicamente",
    "en_descenso_con_opciones",
    "riesgo_descenso",
    "permanencia_por_cerrar",
}''',
        "estados vivos",
    )

    texto = texto.replace('    "aspira_por_desempate_o_fallo_ajeno": 78,', '    "aspira_por_desempate_o_fallo_ajeno": 12,')
    texto = texto.replace('    salvado = equipo["puntos"] > equipo_descenso["maximo_puntos"]', '    salvado = equipo["puntos"] >= equipo_descenso["maximo_puntos"]')
    texto = texto.replace('    if dentro["puntos"] > fuera["maximo_puntos"]:', '    if dentro["puntos"] >= fuera["maximo_puntos"]:')
    texto = texto.replace('    if lider["puntos"] > segundo["maximo_puntos"]:', '    if lider["puntos"] >= segundo["maximo_puntos"]:')
    texto = texto.replace('if e["maximo_puntos"] < safe["puntos"]', 'if e["maximo_puntos"] <= safe["puntos"]')

    texto = texto.replace(
        '    puede_igualar = maximo >= dentro["puntos"]\n',
        '    puede_igualar = maximo == dentro["puntos"]\n',
    )
    texto = texto.replace(
        '        estado = "aspira_por_desempate_o_fallo_ajeno"\n        lectura = (\n            f"Solo puede igualar el corte de {etiqueta}; necesita pleno y dependería "\n            f"de desempates o fallos de {dentro[\'equipo\']}."\n        )',
        '        estado = "aspira_por_desempate_o_fallo_ajeno"\n        lectura = (\n            f"Solo puede igualar el corte de {etiqueta}; sin desempate favorable documentado no se considera objetivo vivo fuerte. "\n            f"Depende de desempates o fallos de {dentro[\'equipo\']}."\n        )',
    )
    texto = texto.replace(
        '        "vivo": estado in ESTADOS_VIVOS,\n        "terminal": estado == "sin_opciones_matematicas",',
        '        "vivo": estado in ESTADOS_VIVOS,\n        "terminal": estado in {"sin_opciones_matematicas", "aspira_por_desempate_o_fallo_ajeno"},',
        1,
    )
    texto = texto.replace(
        '    elif equipo["maximo_puntos"] >= lider["puntos"]:\n        estado = "aspira_por_desempate_o_fallo_ajeno"\n        lectura = f"Solo puede igualar al líder {lider[\'equipo\']} y dependería de desempates."',
        '    elif equipo["maximo_puntos"] == lider["puntos"]:\n        estado = "aspira_por_desempate_o_fallo_ajeno"\n        lectura = f"Solo puede igualar al líder {lider[\'equipo\']}; sin desempate favorable documentado no se considera pelea viva fuerte."',
    )
    texto = texto.replace(
        '        elif estado in {"aspira_por_desempate_o_fallo_ajeno", "ventaja_por_permanencia"}:\n            score += 1',
        '        elif estado in {"ventaja_por_permanencia"}:\n            score += 1',
    )

    if texto != original:
        CONTEXTO.write_text(texto, encoding="utf-8")
        return True
    return False


def inserta(path, marcador, linea):
    texto = path.read_text(encoding="utf-8")
    if linea in texto:
        return False
    if marcador not in texto:
        raise SystemExit(f"No encuentro marcador en {path.name}: {marcador}")
    texto = texto.replace(marcador, marcador + linea, 1)
    path.write_text(texto, encoding="utf-8")
    return True


def main():
    cambios = []
    if parchear_contexto():
        cambios.append("contexto")
    if inserta(ACTUALIZAR, '    "generar_contexto_competitivo.py",\n', '    "aplicar_matematica_competitiva_estricta.py",\n'):
        cambios.append("actualizar_todo")
    if inserta(WORKFLOW, "          python corregir_elige8_web.py\n", "          python aplicar_matematica_competitiva_estricta.py\n"):
        cambios.append("workflow")
    print("Matematica competitiva estricta:", ", ".join(cambios) if cambios else "sin cambios")


if __name__ == "__main__":
    main()
