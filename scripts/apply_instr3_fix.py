from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

motor = ROOT / "motor_prediccion_quiniela.py"
text = motor.read_text(encoding="utf-8")
old = '    detalle["activo"] = bool(detalle["alertas"] or any(abs(v) > 0 for v in detalle["ajuste_por_signo"].values()))\n    detalle["clasificacion_losilla"] = {"local": liga_ctx["1"], "visitante": liga_ctx["2"]}\n    return detalle\n'
new = '    detalle["activo"] = bool(detalle["alertas"] or any(abs(v) > 0 for v in detalle["ajuste_por_signo"].values()))\n    detalle["clasificacion_losilla"] = {"local": liga_ctx["1"], "visitante": liga_ctx["2"]}\n    detalle = reforzar_ajuste_por_memoria_sorpresas(partido, detalle)\n    return detalle\n'
if old in text and 'detalle = reforzar_ajuste_por_memoria_sorpresas(partido, detalle)\n    return detalle' not in text:
    text = text.replace(old, new, 1)
    motor.write_text(text, encoding="utf-8")
    print("PATCHED motor_prediccion_quiniela.py refuerzo memoria")
else:
    print("UNCHANGED motor_prediccion_quiniela.py")

diario = ROOT / "generar_diario_aprendizaje.py"
text = diario.read_text(encoding="utf-8")
old = '            "explicacion": explicar(pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera),\n            "aprendizaje": aprendizaje(pron, tipo, real, ok, fav, score, margen_val, tercera),\n'
new = '            "explicacion": explicacion_especifica(partido, pred, pron, tipo, real, ok, probs, fav, score, categoria, margen_val, tercera),\n            "ajuste_recomendado": ajuste_recomendado_especifico(partido, pred, pron, tipo, real, ok, probs, fav, score, margen_val, tercera),\n            "aprendizaje": aprendizaje(pron, tipo, real, ok, fav, score, margen_val, tercera),\n'
if old in text:
    text = text.replace(old, new, 1)
    diario.write_text(text, encoding="utf-8")
    print("PATCHED generar_diario_aprendizaje.py explicacion especifica")
else:
    print("UNCHANGED generar_diario_aprendizaje.py")
