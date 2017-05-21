from renderers import SimplePageRenderer


class HTTPError(Exception, SimplePageRenderer):
    code = 500
    title = "WTF mate?"
    body = "Something wrong"


class HTTPClientError(HTTPError):
    code = 400
    body = "You've given shit to me. I'm giving shit to you."


class HTTPNotFoundError(HTTPError):
    code = 404
    body = "I can't find your damn thing."


class HTTPServerError(HTTPError):
    code = 500
    message = "I fucked up mate."
