import re

from api.importer.wiktionary import \
    SubsectionImporter as BaseSubsectionImporter

part_of_speech_translation = {
    '動詞': 'mat',
    '形容詞': 'mpam',
    '連詞': 'mpampitohy',
    '限定詞': 'mpam',
    '成語': 'fomba fiteny',
    '短語': 'fomba fiteny',
    '諺語': 'ohabolana',
    '數字': 'isa',
    '名詞': 'ana',
    '形容詞 noun': 'mpam',
    '粒子': 'kianteny',
    '副詞': 'tamb',
    '根': 'fototeny',
    '代詞': 'solo-ana',
    '介詞': 'mp.ank-teny',
    '收縮': 'fanafohezana',
    '信': 'litera',
    '恰當的 noun': 'ana-pr',
    '字首': 'tovona',
    '羅馬化': 'rômanizasiona',
    '後綴': 'tovana',
    '象徵': 'eva',
    '分詞': 'ova-mat',
    '欹': 'tenim-piontanana',
    '中綴': 'tsofoka',
}


class SubsectionImporter(BaseSubsectionImporter):
    section_name = ''
    # True if the section contains a number e.g. Etymology 1, Etymology 2, etc.
    numbered = False
    level = 3

    def __init__(self, **params):
        super(SubsectionImporter, self).__init__(**params)

    def set_whole_section_name(self, section_name: str):
        self.section_name = section_name

    def get_data(self, template_title, wikipage: str, language: str) -> list:
        def retrieve_subsection(wikipage_, regex):
            retrieved_ = []
            target_subsection_section = re.search(regex, wikipage_)
            if target_subsection_section is not None:
                section = target_subsection_section.group()
                pos1 = wikipage_.find(section) + len(section)
                # section end is 2 newlines
                pos2 = wikipage_.find('\n\n', pos1)
                if pos2 != -1:
                    wikipage_ = wikipage_[pos1:pos2]
                else:
                    wikipage_ = wikipage_[pos1:]

                # More often than we'd like to admit,
                #   the section level for the given sub-section is one level deeper than expected.
                # As a consequence, a '=<newline>' can appear before the sub-section content.
                # That often happens for references, derived terms, synonyms, etymologies and part of speech.
                # We could throw an Exception,
                #   but there are 6.5M pages and God knows how many more cases to handle;
                #   so we don't: let's focus on the job while still keeping it simple.
                # Hence, the hack below can help the script fall back on its feet while still doing its job
                #   of fetching the subsection's content.
                # I didn't look for sub-sections that are actually 2 levels or more deeper than expected.
                # Should there be any of that, copy and adapt the condition.
                #   I didn't do it here because -- I.M.H.O -- Y.A.G.N.I right now.
                # My most sincere apologies to perfectionists.
                if wikipage_.startswith('=\n'):
                    wikipage_ = wikipage_[2:]

                retrieved_.append(wikipage_.lstrip('\n'))

            return retrieved_

        retrieved = []
        # Retrieving and narrowing to target section
        if self.numbered:
            number_rgx = ' [1-9]+'
        else:
            number_rgx = ''

        target_language_section = re.search(
            '==[ ]?' + self.iso_codes[language] + '[ ]?==', wikipage)
        if target_language_section is not None:
            section_begin = wikipage.find(str(target_language_section.group(), 'utf8'))
            section_end = wikipage.find('----', section_begin)
            if section_end != -1:
                lang_section_wikipage = wikipage = wikipage[section_begin:section_end]
            else:
                lang_section_wikipage = wikipage = wikipage[section_begin:]
        else:
            return []

        for regex_match in re.findall('=' * self.level + '[ ]?' + self.section_name + number_rgx + '=' * self.level,
                                      wikipage):
            retrieved += retrieve_subsection(wikipage, regex_match)
            wikipage = lang_section_wikipage

        returned_subsections = [s for s in retrieved if s]
        # print(returned_subsections)
        return returned_subsections  # retrieved
