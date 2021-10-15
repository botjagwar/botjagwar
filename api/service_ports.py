import random

service_ports = {
    'entry_translator': 8000,
}
used_ports = []
random_port_ranges = [10000, 20000]


def get_service_port(service_name):
    if service_name in service_ports:
        return service_ports[service_name]
    else:
        return generate_service_port()


def generate_service_port():
    min_port, max_port = random_port_ranges
    port = random.randint(min_port, max_port)
    used_ports.append(port)
    return port


__all__ = ['get_service_port']
