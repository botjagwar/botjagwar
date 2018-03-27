import aiohttp.web
import json


class ServiceError(aiohttp.web.HTTPError):
    pass


class WordDoesNotExistException(ServiceError):
    status_code = 404
    message = json.dumps({
        'message': 'Word does not exist.'
    })


class WordAlreadyExistsException(ServiceError):
    status_code = 460
    message = json.dumps({
        'message': 'Word already exists.'
    })


class InvalidJsonReceivedException(ServiceError):
    status_code = 461
    message = json.dumps({
        'message': 'Received JSON is invalid.'
    })