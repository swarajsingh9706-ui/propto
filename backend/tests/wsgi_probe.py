"""Simulates the cPanel a2wsgi serving path. Confirms requests return promptly
(don't hang) even if the background seed is slow. Run: python tests/wsgi_probe.py"""
import io, sys, time
sys.path.insert(0, "/app/backend")
from passenger_wsgi import application


def call(method, path, body=b""):
    captured = {}
    def start_response(status, headers, exc_info=None):
        captured["status"] = status
    environ = {
        "REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": "",
        "SERVER_NAME": "localhost", "SERVER_PORT": "80", "SERVER_PROTOCOL": "HTTP/1.1",
        "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(body)),
        "wsgi.version": (1, 0), "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(body), "wsgi.errors": sys.stderr,
        "wsgi.multithread": True, "wsgi.multiprocess": False, "wsgi.run_once": False,
    }
    t = time.time()
    out = b"".join(application(environ, start_response))
    return captured.get("status"), round(time.time() - t, 2), out[:120]


for m, p, b in [("GET", "/api/health", b""),
                ("GET", "/api/whapi/webhook", b""),
                ("POST", "/api/whapi/webhook", b"{}")]:
    print(m, p, "->", call(m, p, b))
