SERVER = 'localhost:8001'


def render_definitions(definitions):
    return ', '.join([definition['definition'] for definition in definitions])
