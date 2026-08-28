"""
cPanel / Phusion Passenger entry point.

cPanel's "Setup Python App" runs WSGI, but FastAPI is ASGI, so we wrap the
FastAPI app with a2wsgi. Passenger looks for a module-level `application`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from a2wsgi import ASGIMiddleware
except ImportError:
    sys.stderr.write(
        "\nFATAL: 'a2wsgi' is not installed in this virtualenv.\n"
        "Enter the app's virtualenv and run:\n"
        "    pip install a2wsgi\n"
        "  (or)  pip install -r requirements-cpanel.txt\n"
        "then Restart the Python App.\n\n"
    )
    raise

from server import app as asgi_app  # noqa: E402

application = ASGIMiddleware(asgi_app)
