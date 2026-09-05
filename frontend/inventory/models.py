"""No frontend database models are required.

This Django project renders the UI and sends server-to-server requests to
FastAPI through ``inventory/service.py``. FastAPI owns the inventory models,
validation, persistence, and authorization.
"""
