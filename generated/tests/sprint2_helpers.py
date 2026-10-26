import json
import threading
from http.client import HTTPConnection

from generated.api import make_server
from generated.database import Database


class ApiFixture:
    def start_api(self):
        self.db = Database(":memory:")
        self.server = make_server(port=0, database=self.db)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def stop_api(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.db.close()

    def request(self, method, path, body=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = None if body is None else json.dumps(body)
        connection.request(method, path, payload, {"Content-Type": "application/json"})
        response = connection.getresponse()
        raw = response.read()
        result = (response.status, dict(response.getheaders()), json.loads(raw) if raw else None)
        connection.close()
        return result


def placement(lines=None, **options):
    return {
        "customer_name": "Sprint Two",
        "items": lines or [{"product_sku": "FIRST-SPROUT", "quantity": 1}],
        **options,
    }
