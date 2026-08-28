"""
cPanel / Phusion Passenger entry point (single-domain deployment).

cPanel "Setup Python App" runs WSGI, but FastAPI is ASGI, so we wrap it with
a2wsgi. Passenger looks for a module-level `application`.

Single-domain note: the Python app is mounted at the sub-path /api, so Passenger
sends requests with SCRIPT_NAME=/api and PATH_INFO=/health. Starlette strips
root_path while routing, which would make /api/health return 404. We fold
SCRIPT_NAME back into PATH_INFO so the app always sees the full "/api/..." path
and its routes resolve correctly.
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
        "    pip install -r requirements-cpanel.txt\n"
        "then Restart the Python App.\n\n"
    )
    raise

from server import app as asgi_app  # noqa: E402

_wsgi_app = ASGIMiddleware(asgi_app)


def application(environ, start_response):
    script_name = environ.get("SCRIPT_NAME", "")
    if script_name:
        environ["PATH_INFO"] = script_name + environ.get("PATH_INFO", "")
        environ["SCRIPT_NAME"] = ""
    return _wsgi_app(environ, start_response)
