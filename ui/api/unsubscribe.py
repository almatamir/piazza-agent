import json
import os
from http.server import BaseHTTPRequestHandler

from supabase import create_client


def _get_client():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))

            email = (body.get("email") or "").strip().lower()
            if not email:
                return self._respond(400, {"error": "Email is required."})

            client = _get_client()
            result = (
                client.table("users")
                .update({"active": False})
                .eq("email", email)
                .execute()
            )

            if not result.data:
                return self._respond(404, {"error": "Email not found in our system."})

            self._respond(200, {"success": True})

        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _respond(self, status: int, body: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, *args):
        pass
