import json

import aiohttp.web


class ServiceError(aiohttp.web.HTTPError):
    status_code = 500
    message = 'The service encountered an unknown error.'


class ElementDoesNotExist(ServiceError):
    status_code = 404


class ElementAlreadyExists(ServiceError):
    status_code = 460


class InvalidDataError(ServiceError):
    status_code = 461


class BatchContainsErrors(ServiceError):
    status_code = 462


class LanguageDoesNotExist(ElementDoesNotExist):
    message = json.dumps({
        'message': 'Language does not exist.'
    })


class WordDoesNotExist(ElementDoesNotExist):
    status_code = 404
    message = 'Word does not exist.'


class WordAlreadyExists(ElementAlreadyExists):
    message = 'Word already exists.'


class InvalidJsonReceived(InvalidDataError):
    message = 'Received JSON is invalid.'
