from object_model import TypeCheckedObject


class Word(TypeCheckedObject):
    _additional = False
    properties_types = dict(
        entry=str,
        part_of_speech=str,
        language=str)


class Entry(TypeCheckedObject):
    _additional = True
    properties_types = dict(
        entry=str,
        part_of_speech=str,
        entry_definition=list,
        language=str,
        origin_wiktionary_edition=str,
        origin_wiktionary_page_name=str,
        etymology=str,
        reference=list,
        examples=list
    )

    def to_tuple(self):
        return self.entry, self.part_of_speech, self.language, self.entry_definition

    def to_dict(self):
        ret = {}
        for key in self.properties_types.keys():
            if hasattr(self, key):
                ret[key] = getattr(self, key)
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
                    if self.entry == other.entry:
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

    def __repr__(self):
        #return str(self.__dict__)
        props = ''
        for d in self.properties_types:
            if hasattr(self, d):
                props += d + '=' + str(getattr(self, d)) + '; '

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
