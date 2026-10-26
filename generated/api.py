import json
import logging
import os
import re
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

if __package__ in (None, ""):
    from database import Database
else:
    from generated.database import Database


LOGGER = logging.getLogger("hcc.api")


def make_server(host="127.0.0.1", port=8000, database=None):
    db = database or Database()

    class Handler(BaseHTTPRequestHandler):
        server_version = "HCC/1.0"

        def log_message(self, format_string, *args):
            LOGGER.info("%s - %s", self.address_string(), format_string % args)

        def _json(self, status, payload, headers=None):
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(encoded)

        def _error(self, status, message, allow=None):
            headers = {"Allow": allow} if allow else None
            self._json(status, {"error": message}, headers)

        def _path(self):
            return urlsplit(self.path).path

        def _route(self):
            path = self._path()
            if path in ("/products", "/orders"):
                return path, None
            match = re.fullmatch(r"/products/([^/]+)", path)
            if match:
                return "/products/{sku}", unquote(match.group(1))
            match = re.fullmatch(r"/orders/([^/]+)", path)
            if match:
                return "/orders/{id}", match.group(1)
            return None, None

        def _read_json(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ValueError("invalid Content-Length") from exc
            if length <= 0:
                raise ValueError("request body is required")
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("invalid JSON") from exc

        def _dispatch(self):
            route, parameter = self._route()
            if route is None:
                self._error(404, "Not found")
                return
            if route == "/products" and self.command == "GET":
                self._json(200, db.list_products())
            elif route == "/products/{sku}" and self.command == "GET":
                product = db.get_product(parameter)
                if product is None:
                    self._error(404, "Unknown product")
                else:
                    self._json(200, product)
            elif route == "/orders" and self.command == "GET":
                self._json(200, db.list_orders())
            elif route == "/orders/{id}" and self.command == "GET":
                if not re.fullmatch(r"[0-9]+", parameter):
                    self._error(400, "order ID must be an integer")
                    return
                order = db.get_order(int(parameter))
                if order is None:
                    self._error(404, "Order not found")
                else:
                    self._json(200, order)
            elif route == "/orders" and self.command == "POST":
                try:
                    request = self._read_json()
                    order = db.create_order(request)
                except LookupError as exc:
                    self._error(404, str(exc))
                    return
                except OverflowError as exc:
                    self._error(409, str(exc))
                    return
                except (ValueError, TypeError) as exc:
                    self._error(400, str(exc))
                    return
                self._json(201, order)
            else:
                allow = "GET" if route != "/orders" else ("GET, POST" if self.command not in ("GET", "POST") else "GET")
                self._error(405, "Method not allowed", allow)

        def _handle(self):
            try:
                self._dispatch()
            except Exception:
                LOGGER.error("Unhandled request failure:\n%s", traceback.format_exc())
                if not self.wfile.closed:
                    self._error(500, "Internal server error")

        do_GET = _handle
        do_POST = _handle
        do_PUT = _handle
        do_DELETE = _handle
        do_PATCH = _handle
        do_OPTIONS = _handle
        do_HEAD = _handle

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    server = Server((host, port), Handler)
    server.database = db
    return server


def main():
    logging.basicConfig(level=logging.INFO)
    host = os.environ.get("HCC_API_HOST", "127.0.0.1")
    port = int(os.environ.get("HCC_API_PORT", "8000"))
    server = make_server(host, port)
    print(f"HCC API listening at http://{host}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.database.close()


if __name__ == "__main__":
    main()
