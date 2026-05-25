"""Capa HTTP (FastAPI).

Estructura:
- api/v1/: rutas versionadas
- api/v1/evaluations.py: POST/GET/LIST de evaluaciones (T0.11)
- api/v1/schemas.py: Pydantic request/response (separados de agents.contracts
  porque la shape HTTP no = shape interna del pipeline)
"""
