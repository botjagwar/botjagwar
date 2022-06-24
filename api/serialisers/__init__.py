
class Builder(object):
    def __init__(self):
        self.mapped_variables = []

    def serialise(self):
        raise NotImplementedError()

