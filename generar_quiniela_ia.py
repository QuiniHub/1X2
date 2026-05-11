import json, os

def generar_pronostico_inteligente():
    if not os.path.exists("data/analisis_ia.json"): return
    with open("data/analisis_ia.json", "r", encoding="utf-8") as f: analisis = json.load(f)
    
    boleto_pronosticado = []
    # Consolidar ambos bloques en el orden del boleto físico de La Quiniela
    todos_partidos = analisis.get("primera", []) + analisis.get("segunda", [])
    
    for idx, p in enumerate(todos_partidos[:15]):
        # Lógica de asignación de signos basada en el peso analítico de la IA
        signo_base = "1" if int(p["probabilidades"]["1"].replace("%","")) > 45 else "X"
        signo_doble = "2" if p["alerta_bomba"] else ""
        
        if idx == 14: # Regla específica del Pleno al 15
            boleto_pronosticado.append({"partido": idx+1, "pronostico": "2-1", "tipo": "Pleno15"})
        else:
            boleto_pronosticado.append({
                "partido": idx+1, "local": p["local"], "visitante": p["visitante"],
                "signo_fijo": signo_base, "signo_doble": signo_doble,
                "elige8": idx < 8
            })
            
    with open("data/quiniela_ia_pronostico.json", "w", encoding="utf-8") as f:
        json.dump({"jornada": "61", "pronosticos": boleto_pronosticado}, f, indent=4, ensure_ascii=False)

if __name__ == "__main__": generar_pronostico_inteligente()
