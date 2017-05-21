# coding: utf8
import threading

from BaseHTTPServer import HTTPServer

from modules.http_server.handler import RequestHandler
from modules.http_server.router import Router
from modules.http_server.services import example


class Server(object):
    router = Router()

    def __init__(self, port):
        self.port = port

        self.handler = RequestHandler
        self.handler.router = self.router

        self.server = HTTPServer
        self.httpd = None

    def set_server_type(self, server_type):
        self.server = server_type

    def set_handler(self, handler_class):
        self.handler = handler_class

    def run(self):
        server_address = ('', self.port)
        self.httpd = self.server(server_address, self.handler)
        self.httpd.serve_forever()


def serve(**params):
    server = Server(params['port'])
    server.router.bind(params['route'], params['function'])
    server.run()


def main():
    serve(function=example, route='/ekemi', port=8100)


if __name__ == '__main__':
    main()
