"""
cPanel / Phusion Passenger entry point.

cPanel's "Setup Python App" runs WSGI, but FastAPI is ASGI, so we wrap the
FastAPI app with a2wsgi. Passenger looks for a module-level `application`.
a2wsgi runs the ASGI app (including FastAPI startup/seed events) on its own
persistent event loop, which keeps Motor/MongoDB happy.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a2wsgi import ASGIMiddleware  # noqa: E402
from server import app as asgi_app  # noqa: E402

application = ASGIMiddleware(asgi_app)
