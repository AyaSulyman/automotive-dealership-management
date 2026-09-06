"""No frontend database models are required.

This Django project renders the UI and sends server-to-server requests to
the REST backend through ``inventory/service.py``. The backend owns the
inventory models, validation, persistence, and authorization.
"""
