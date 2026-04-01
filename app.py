"""Compatibility entrypoint: ``flask --app app run`` and ``from app import app``."""
from mimic import create_app

app = create_app()
