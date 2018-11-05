#!/usr/bin/python3.6
import time

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
            change_map = {}
            fail_map = {}
            for line in query.fetchall():
                word, language, pos, definition_id, old_definition, new_definition = line
                if definition_id not in change_map:
                    change_map[definition_id] = 0
                try:
                    print('>>>>', old_definition, '/', word, '<<<<')
                    mg_word_page = pywikibot.Page(pywikibot.Site('mg', 'wiktionary'), word)
                    if mg_word_page.exists() and not mg_word_page.isRedirectPage():
                        content = mg_word_page.get()
                        new_content = content.replace(f'[[{old_definition}]]', f'[[{new_definition}]]')
                        pywikibot.showDiff(content, new_content)
                        if content != new_content:
                            mg_word_page.put(new_content, f'fanitsiana: -{old_definition} +{new_definition}')
                            change_map[definition_id] += 1
                    else:
                        continue
                except Exception as exc:
                    if definition_id not in fail_map:
                        fail_map[definition_id] = "%s failed: %s" % (word, str(exc))
                    else:
                        fail_map[definition_id] += "\n%s failed: %s" % (word, str(exc))

            for definition_id, changes in change_map.items():
                comment = f'{changes} changes applied.'
                status = 'DONE'
                connection.execute(f"""
                    UPDATE events_definition_changed SET
                        status = '{status}',
                        status_datetime = CURRENT_TIMESTAMP(),
                        commentary = '{comment}'
                    WHERE definition_id = {definition_id}""")

            for definition_id, comment in fail_map.items():
                status = 'FAILED'
                connection.execute(f"""
                    UPDATE events_definition_changed SET
                        status = '{status}',
                        status_datetime = CURRENT_TIMESTAMP(),
                        commentary = '{comment}'
                    WHERE definition_id = {definition_id}""")


async def start_robot():
    bot = DefinitionModificationManagerBot()
    while True:
        bot.start()
        print('Done.')
        time.sleep(5)



if __name__ == '__main__':
    import asyncio
    loop = asyncio.get_event_loop()
    task = loop.create_task(start_robot())
    loop.run_until_complete(task)