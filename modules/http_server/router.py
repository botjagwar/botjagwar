# coding: utf8

from modules.http_server.errors import HTTPError, HTTPNotFoundError, HTTPServerError
from modules.http_server.services import example


class Router(object):
    """
    Services must return a string object (even empty). 
    """
    def __init__(self):
        self.path = None
        self.services = {}

    def execute(self, path):
        """
        Returns a str() object from the service. If an error occurred, HTTPServerError is used
        Args:
            path: the GET string as got by handler.
        Returns:

        """
        self.path = path
        component, get_params = self._parse()
        print "component '%s'; params: %s" % (component, str(get_params))
        if component not in self.services:
            raise HTTPNotFoundError
        try:
            ret = self.services[component](**get_params)
            assert type(ret) is str
            return ret
        except Exception as e:
            if isinstance(e, HTTPError):
                raise e
            else:
                raise HTTPServerError

    def set_services(self, new_services):
        """
        Overrides the current list of services with the provided new_services.        
        Args:
            new_services: dict() object. keys must be str() objects and values must be callable 
        Returns:
        """
        # check
        assert type(new_services) is dict
        for name, service in new_services.items():
            assert callable(service)
            assert type(name) in [str, unicode]
        # set
        self.services = new_services

    def _parse(self):
        """
        Parse parametres passed through GET. Splits component and parametres into
        two different variables.
        Examples:
            /foo?a=1&b=2&c=3 will recognise foo as component and {'a':1, 'b':2, 'c':3} 
        Returns:
            component, dict(GET_PARAMS)
        """
        component_end = self.path.find(u'?')
        if component_end > 0:
            component = self.path[:component_end]
            params_str = self.path[1+component_end:]
        else:
            component = self.path
            params_str = ''

        GET_req_params_dict = {}
        # builing params_dict
        params_str = unicode(params_str)
        param_list = params_str.split(u'&')
        if param_list > 2:
            for param in param_list:
                name = param[:param.find(u'=')]
                value = param[param.find(u'=')+1:]
                GET_req_params_dict[name] = value

        return component, GET_req_params_dict

    def bind(self, path, service):
        """
        Associat a given route for a given service.
        Args:
            path: str() for path.
            service: callable accepting keyword arguments

        Returns:

        """
        # TODO: use regex?
        assert callable(service)
        assert type(path) in [str, unicode]
        self.services[path] = service
