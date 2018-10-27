#!/usr/bin/python3.6
import traceback

import pywikibot

from api.databasemanager import DictionaryDatabaseManager


class DefinitionModificationManagerBot(object):
    def __init__(self, database_file='default'):
        self.input_database = DictionaryDatabaseManager(database_file=database_file)

    def start(self):
        query_string = """
        select 
            wrd.word, 
            wrd.language,
            wrd.part_of_speech,
            edc.definition_id,
            edc.old_definition as old,
            edc.new_definition as new_
        from
            events_definition_changed edc
            join definitions def on (
                edc.definition_id = def.id)
            join dictionary dict on (
                def.id = dict.definition)
            join word wrd on (
                dict.word = wrd.id)
        where status = 'PENDING'
        """
        with self.input_database.engine.connect() as connection:
            query = connection.execute(query_string)
            for line in query.fetchall():
                changes = 0
                word, language, pos, definition_id, old_definition, new_definition = line
                try:
                    print('>>>>', old_definition, '/', word, '<<<<')
                    mg_word_page = pywikibot.Page(pywikibot.Site('mg', 'wiktionary'), word)
                    if mg_word_page.exists() and not mg_word_page.isRedirectPage():
                        content = mg_word_page.get()
                        new_content = content.replace(f'[[{old_definition}]]', f'[[{new_definition}]]')
                        pywikibot.showDiff(content, new_content)
                        if content != new_content:
                            mg_word_page.put(new_content, f'fanitsiana: -{old_definition} +{new_definition}')
                            changes += 1
                    else:
                        continue
                except Exception as exc:
                    status = 'FAILED'
                    comment = traceback.format_exc(exc)
                else:
                    status = 'DONE'
                    comment = f'{changes} changes applied.'

                connection.execute(f"""
                    UPDATE events_definition_changed SET
                        status = '{status}',
                        status_datetime = CURRENT_TIMESTAMP(),
                        commentary = '{comment}'
                    WHERE definition_id = {definition_id}"""
                )


if __name__ == '__main__':
    bot = DefinitionModificationManagerBot()
    bot.start()