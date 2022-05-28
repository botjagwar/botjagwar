from copy import deepcopy

from api.model import TypeCheckedObject, Property


class Word(TypeCheckedObject):
    _additional = False
    properties_types = dict(
        entry=str,
        part_of_speech=str,
        language=str
    )


class Entry(TypeCheckedObject):
    _additional = True
    additional_data_types = {}
    properties_types = dict(
        entry=str,
        part_of_speech=str,
        definitions=list,
        language=str,
    )

    def __init__(self, **properties):
        super(Entry, self).__init__(**properties)
        self.entry = properties['entry']
        self.part_of_speech = properties['part_of_speech']
        self.definitions = properties['definitions']
        if 'language' in properties:
            self.language = properties['language']

        if 'additional_data' in properties:
            self.additional_data = properties['additional_data']

        if 'references' in properties:
            self.references = properties['references']

    @classmethod
    def from_word(cls, model):
        return cls(
            entry=model.word,
            part_of_speech=model.part_of_speech,
            language=model.language,
            definitions=deepcopy(model.definitions),
            additional_data=deepcopy(model.additional_data)
        )

    def to_tuple(self):
        return self.entry, self.part_of_speech, self.language, self.definitions

    def to_dict(self) -> dict:
        ret = TypeCheckedObject.to_dict(self)

        ret['additional_data'] = {}
        for key in self.additional_data_types.keys():
            if hasattr(self, key):
                value = getattr(self, key)
                ret['additional_data'][key] = {}
                if isinstance(value, Property):
                    ret['additional_data'][key] = value.serialise()
                elif hasattr(value, '__iter__'):
                    ret['additional_data'][key] = [v.serialise() if isinstance(v, Property) else v
                                                   for v in value]
                else:
                    ret['additional_data'][key] = value

        return ret

    def __lt__(self, other):
        """
        Used for sorting entries. Language code will be considered
        :param other:
        :return:
        """
        return self.__cmp__(other) < 0

    def __cmp__(self, other):
        """
        Comparison, in the following order: language > entry > part_of_speech
        :param other:
        :return:
        """
        if hasattr(self, 'language') and hasattr(other, 'language'):
            if self.language == other.language:
                if hasattr(self, 'entry') and hasattr(other, 'entry'):
                    if self.entry == other.entry:  # noqa
                        if hasattr(self, 'part_of_speech') and hasattr(other, 'part_of_speech'):
                            if self.part_of_speech == other.part_of_speech:
                                return 0
                            elif self.part_of_speech < other.part_of_speech:
                                return -1
                            else:
                                return 1
                        else:
                            return 0
                    elif self.entry < other.entry:
                        return -1
                    else:
                        return 1
                else:
                    return 0
            elif self.language < other.language:
                return -1
            else:
                return 1
        else:
            return 1

    def overlay(self, other):
        self.language = other.language
        self.part_of_speech = other.part_of_speech
        self.definitions = other.definitions
        for apt, ap_type in other.properties_types.items():
            print(other)
            if hasattr(other, apt):
                setattr(self, apt, deepcopy(getattr(other, apt)))

        return deepcopy(self)

    def __repr__(self):
        # return str(self.__dict__)
        props = ''
        additional_data = ''
        for d in self.properties_types:
            if hasattr(self, d):
                props += d + '=' + str(getattr(self, d)) + '; '

        for k, v in self.additional_data_types.items():
            if hasattr(self, k):
                additional_data += str(k) + '=' + str(getattr(self, k))

        if additional_data:
            return "Entry{%s | additional_data %s}" % (props, additional_data)

        return "Entry{%s}" % (props)


class Translation(TypeCheckedObject):
    _additional = False
    properties_types = dict(
        word=str,
        language=str,
        part_of_speech=str,
        translation=str
    )


__all__ = ['Word', 'Entry', 'Translation']
