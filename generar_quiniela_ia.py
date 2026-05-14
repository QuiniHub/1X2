"""Compatibilidad: usa el motor predictivo oficial.

Este archivo existe para que cualquier llamada antigua a generar_quiniela_ia.py
no ejecute un segundo motor distinto. La unica fuente valida de prediccion es
motor_prediccion_quiniela.py.
"""

from motor_prediccion_quiniela import main


if __name__ == "__main__":
    main()
