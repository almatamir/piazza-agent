import json
import os
from http.server import BaseHTTPRequestHandler

from supabase import create_client


def _get_client():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def _extract_course_id(url: str) -> str | None:
    if "piazza.com/class/" not in url:
        return None
    # Strip fragments (#), query params (?), and trailing slashes
    url = url.split("#")[0].split("?")[0].rstrip("/")
    return url.split("/")[-1] or None


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))

            email = (body.get("email") or "").strip()
            piazza_email = (body.get("piazza_email") or "").strip()
            piazza_password = (body.get("piazza_password") or "").strip()
            course_url = (body.get("course_url") or "").strip()

            if not all([email, piazza_email, piazza_password, course_url]):
                return self._respond(400, {"error": "All fields are required."})

            course_id = _extract_course_id(course_url)
            if not course_id:
                return self._respond(400, {"error": "Invalid Piazza URL."})

            client = _get_client()
            client.table("users").insert({
                "email": email,
                "piazza_email": piazza_email,
                "piazza_password": piazza_password,
                "piazza_course_id": course_id,
            }).execute()

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
