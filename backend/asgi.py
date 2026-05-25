"""ASGI entrypoint para uvicorn.

Uso:
    uvicorn asgi:app --host 0.0.0.0 --port 8000

Separado de main.py para que `import main` (en tests) no ejecute
create_app() eager y dispare la validación de .env.
"""

from main import create_app

app = create_app()
