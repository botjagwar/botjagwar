#coding: utf8

import os
import pywikibot as pwbot


mt_data_file = os.getcwd() + '/user_data/dikantenyvaovao/'


def analyse_translations(arg2):
    arg2 = int(arg2)
    missing_tran = MissingTranslations(mt_data_file)
    missing_tran.analyse(arg2)


def analyse_edit_hours(arg2):
    tran_per_hour = Translations_per_day_hour(mt_data_file)
    tran_per_hour.analyse()
    tran_per_hour.cleanup()


class Translations_per_day_hour(object):
    """Edit counter. Sorted by hour of the day. Uses a file."""

    def __init__(self, data_file):
        self.translations_per_hour = {}
        self.data_file = data_file
        self.retrieve()

    def cleanup(self):
        self.retrieve()
        self.update()

    def retrieve(self):
        try:
            translation_needed_file = open(self.data_file + 'dikantenyvaovao_dikanteny_isakora.txt', 'r')
        except IOError:
            return

        for i in range(24):
            self.translations_per_hour[str(i)] = 0

        for line in translation_needed_file.readlines():
            line = line.strip('\n')
            line = line.split("::")
            if len(line) < 2:
                continue

            self.translations_per_hour[line[0]] += int(line[1].replace(':', ''))

        translation_needed_file.close()

    def add(self, word):
        try:
            self.translations_per_hour[word] += 1
        except KeyError:
            self.translations_per_hour[word] = 1
        return self.translations_per_hour[word]

    def update(self):
        translation_needed_file = open(self.data_file + 'dikantenyvaovao_dikanteny_isakora.txt', 'w')
        for translation in self.translations_per_hour:
            try:
                filestr = "%s::%d\n" % (translation, self.translations_per_hour[translation])
                translation_needed_file.write(filestr.encode('utf8'))
            except UnicodeError:
                continue
        translation_needed_file.close()

    def analyse(self):
        if len(self.translations_per_hour) == 0:
            self.retrieve()
        translation_list = []
        for translation in self.translations_per_hour:
            translation_list.append((int(translation), int(self.translations_per_hour[translation])))
        translation_list.sort()
        pwbot.output(" Isa | Ora\n" + 30 * '-')

        for tr in translation_list:
            pwbot.output('%4d | %d' % tr)


class MissingTranslations(object):
    def __init__(self, data_file):
        self.data_file = data_file
        self.missing_translations = {}
        self.retrieve()

    def retrieve(self):
        file_name = self.data_file + 'dikantenyvaovao_ilaina.txt'
        try:
            translation_needed_file = open(file_name, 'r')
        except IOError:
            return

        for line in translation_needed_file.readlines():
            line = line.strip('\n')
            line = line.split("::")
            try:
                self.missing_translations[line[0]] += int(line[1].replace(':', ''))
            except KeyError:
                self.missing_translations[line[0]] = 1
        translation_needed_file.close()

    def add(self, word):
        try:
            self.missing_translations[word] += 1
        except KeyError:
            self.missing_translations[word] = 1
        return self.missing_translations[word]

    def update(self):
        translation_needed_file = open(self.data_file + 'dikantenyvaovao_ilaina.txt', 'w')
        for translation in self.missing_translations:
            try:
                filestr = "%s::%d\n" % (translation, self.missing_translations[translation])
                translation_needed_file.write(filestr.encode('utf8'))
            except UnicodeError:
                continue
        translation_needed_file.close()

    def analyse(self, n_display=10):
        if len(self.missing_translations) == 0:
            self.retrieve()
        translation_list = []
        for translation in self.missing_translations:
            translation_list.append((int(self.missing_translations[translation]), translation))
        translation_list.sort()
        tr_list = translation_list[::-1]
        pwbot.output(" N° Tranga | Teny\n" + 30 * '-')
        tr_list = tr_list[:n_display]

        for tr in tr_list:
            pwbot.output('%10d | %s' % tr)

