import aiohttp.web
import json


class ServiceError(aiohttp.web.HTTPError):
    message = 'The service encountered an unknown error.'


class ElementDoesNotExistException(ServiceError):
    status_code = 404


class ElementAlreadyExistsException(ServiceError):
    status_code = 460


class InvalidDataException(ServiceError):
    status_code = 461


class LanguageDoesNotExistsException(ElementDoesNotExistException):
    message = json.dumps({
        'message': 'Language does not exist.'
    })


class WordDoesNotExistException(ElementDoesNotExistException):
    status_code = 404
    message = 'Word does not exist.'


class WordAlreadyExistsException(ElementAlreadyExistsException):
    message = 'Word already exists.'


class InvalidJsonReceivedException(InvalidDataException):
    message = json.dumps({
        'message': 'Received JSON is invalid.'
    })