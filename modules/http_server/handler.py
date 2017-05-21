# coding: utf8
import BaseHTTPServer

from modules.http_server.errors import HTTPError
from modules.http_server.router import Router


class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    router = Router()

    def _header(self, code):
        self.send_response(code)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

    def _error(self, code, message):
        self.send_error(code, message)

    def do_HEAD(self):
        self._header(200)

    def do_POST(self):
        try:
            result = self.router.execute(self.path)
            self._header(200)
            self.wfile.write(result)

        except HTTPError as http_err:
            self._error(http_err.code, http_err.message)

    def do_GET(self):
        """Respond to a GET request."""
        try:
            result = self.router.execute(self.path)
            self._header(200)
            self.wfile.write(result)

        except HTTPError as http_err:
            self._error(http_err.code, http_err.message)
