"""Calculadoras puras del dominio.

Sin LLM, sin I/O. Funciones determinísticas testeables por tabla.

- financial.py: margen, ROI, equilibrio, sensibilidad TC ±10%.
- market.py: ratio precio/costo, margen vs sector, tier de volumen.
- risk.py: exposición TC, concentración de costos, margen de seguridad.
- scoring.py: weighted_final_score con pesos ADR.
"""
