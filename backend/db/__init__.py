"""Capa de persistencia (SQLAlchemy async + Postgres + RLS efectivo).

Ver:
- models.py: definición de tablas SQLAlchemy.
- session.py: async_sessionmaker + get_db() con RLS bindparams (ADR-008).
- migrations/: SQL versionado (001_initial, 002_effective_rls).
"""
