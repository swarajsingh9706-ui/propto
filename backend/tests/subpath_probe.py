"""Simulate cPanel Passenger mounting the app at sub-path /api.

Passenger sets SCRIPT_NAME=/api and PATH_INFO=/health for a request to
/api/health. We verify the FastAPI /api/* routes resolve through the
passenger_wsgi.application wrapper (which folds SCRIPT_NAME into PATH_INFO).
"""
import io
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passenger_wsgi import application


def call(script_name, path_info):
    environ = {
        "REQUEST_METHOD": "GET",
        "SCRIPT_NAME": script_name,
        "PATH_INFO": path_info,
        "QUERY_STRING": "",
        "SERVER_NAME": "manage.propto.app",
        "SERVER_PORT": "443",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.url_scheme": "https",
        "wsgi.input": io.BytesIO(b""),
        "CONTENT_LENGTH": "0",
    }
    status_holder = {}

    def start_response(status, headers, exc_info=None):
        status_holder["status"] = status

    body = b"".join(application(environ, start_response))
    return status_holder.get("status"), body[:120]


print("A) sub-path mount  SCRIPT_NAME=/api PATH_INFO=/health ->", call("/api", "/health"))
print("B) sub-path webhook SCRIPT_NAME=/api PATH_INFO=/whapi/webhook ->", call("/api", "/whapi/webhook"))
print("C) root mount      SCRIPT_NAME=''   PATH_INFO=/api/health ->", call("", "/api/health"))
