"""
SafaraOne — extensions.py
==========================
THE FIX FOR ALL CIRCULAR IMPORTS.

This file is the single source of truth for all Flask extensions.
It creates the extension objects WITHOUT binding them to an app.
The app is bound later in app.py via db.init_app(app).

WHY THIS WORKS:
  Old pattern (circular):
    app.py      → imports services → services import 'from app import db'
                                     (circular dependency — breaks on startup)

  New pattern (clean):
    extensions.py  (no dependencies at all)
         ↑
    models.py      imports 'from extensions import db'
         ↑
    services/      import db directly from extensions module
         ↑
    app.py         imports db from extensions, calls db.init_app(app)

USAGE AFTER THIS CHANGE:
  In models.py:       from extensions import db
  In all services:    from extensions import db
  In app.py:          from extensions import db
                      db.init_app(app)
"""

from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager

# Create extension instances — not bound to any app yet.
# app.py calls db.init_app(app) and jwt.init_app(app) during startup.
db  = SQLAlchemy()
jwt = JWTManager()
