"""ASGI entry point: uvicorn api:app --host 0.0.0.0 --port 8000."""

from pastabar.app import create_app

app = create_app()
