import os, json

EQUIPOS_LIGA = {
    "primera": ["Barcelona", "Real Madrid", "Ath Madrid", "Ath Bilbao", "Sociedad", "Betis", "Villarreal", "Valencia", "Sevilla", "Osasuna", "Girona", "Vallecano", "Celta", "Getafe", "Mallorca", "Alaves", "Valladolid", "Leganes", "Espanyol", "Elche", "Oviedo", "Levante"],
    "segunda": ["Santander", "Mirandés", "Zaragoza", "Burgos", "Sporting", "Castellón", "Huesca", "Oviedo", "Eibar", "Elche", "Albacete", "Almería", "Málaga", "Eldense", "Córdoba", "Cádiz", "Granada", "Ferrol", "Cartagena", "Tenerife", "Andorra", "Ceuta", "La Coruna", "Las Palmas", "Sp Gijon", "Sociedad B", "Cultural Leonesa"]
}

def procesar():
    salida = {}
    for tipo in ["primera", "segunda"]:
        tabla = {eq: {"equipo": eq, "Equipo": eq, "pj": 0, "PJ": 0, "g": 0, "G": 0, "e": 0, "E": 0, "p": 0, "P": 0, "gf": 0, "GF": 0, "gc": 0, "GC": 0, "pts": 0, "PTS": 0} for eq in EQUIPOS_LIGA[tipo]}
        ruta = f"data/partidos_{tipo}.json"
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f: partidos = json.load(f)
            for p in partidos:
                gl, gv = p.get("goles_local"), p.get("goles_visitante")
                if gl and gv and str(gl).isdigit() and str(gv).isdigit():
                    l, v = p["local"], p["visitante"]
                    # Mapeo elástico para el sumador de puntos
                    l_key = next((k for k in tabla if k.lower() in l.lower() or l.lower() in k.lower()), None)
                    v_key = next((k for k in tabla if k.lower() in v.lower() or v.lower() in k.lower()), None)
                    if l_key and v_key:
                        intl, intv = int(gl), int(gv)
                        tabla[l_key]["pj"]+=1; tabla[l_key]["PJ"]+=1; tabla[v_key]["pj"]+=1; tabla[v_key]["PJ"]+=1
                        tabla[l_key]["gf"]+=intl; tabla[l_key]["GF"]+=intl; tabla[v_key]["gf"]+=intv; tabla[v_key]["GF"]+=intv
                        tabla[l_key]["gc"]+=intv; tabla[l_key]["GC"]+=intv; tabla[v_key]["gc"]+=intl; tabla[v_key]["GC"]+=intl
                        if intl > intv: tabla[l_key]["pts"]+=3; tabla[l_key]["PTS"]+=3; tabla[l_key]["g"]+=1; tabla[l_key]["G"]+=1; tabla[v_key]["p"]+=1; tabla[v_key]["P"]+=1
                        elif intl < intv: tabla[v_key]["pts"]+=3; tabla[v_key]["PTS"]+=3; tabla[v_key]["g"]+=1; tabla[v_key]["G"]+=1; tabla[l_key]["p"]+=1; tabla[l_key]["P"]+=1
                        else: tabla[l_key]["pts"]+=1; tabla[l_key]["PTS"]+=1; tabla[v_key]["pts"]+=1; tabla[v_key]["PTS"]+=1; tabla[l_key]["e"]+=1; tabla[l_key]["E"]+=1; tabla[v_key]["e"]+=1; tabla[v_key]["E"]+=1
        salida[tipo] = sorted(tabla.values(), key=lambda x: (x["pts"], x["gf"]-x["gc"]), reverse=True)
    with open("clasificaciones.json", "w", encoding="utf-8") as f: json.dump(salida, f, indent=4, ensure_ascii=False)

if __name__ == "__main__": procesar()
