import time

from api.databasemanager import DictionaryDatabaseManager


class GarbageCollectorBot(object):
    def __init__(self, database_file='default'):
        self.input_database = DictionaryDatabaseManager(
            database_file=database_file)

    def start(self):
        used_definitions_q = "select distinct definition from dictionary"
        all_definitions_q = "select id from definitions"
        all_definitions = set()
        used_definitions = set()
        session = self.input_database.session
        session.begin(subtransactions=True)
        print("Fetching all definitions...")
        for k in session.execute(all_definitions_q).fetchall():
            all_definitions.add(k[0])
        print("Fetching used definitions...")
        for k in session.execute(used_definitions_q).fetchall():
            used_definitions.add(k[0])
        print(f"Definitions contains {len(all_definitions)} entries, of which {len(used_definitions)} are used.")
        unused = all_definitions - used_definitions
        unused_len = len(unused)
        print(f"{unused_len} entries will be deleted.")
        begin_time = time.time()
        print("Starting deletion...", time.time())
        data = [str(k) for k in unused]
        chunk = set()
        problematic_chunks = set()
        count = 0
        deleted = 0
        for d in data:
            d = str(d)
            count += 1
            chunk.add(d)
            if count >= 1000:
                deletion_query_definitions = "delete from definitions where id in ("
                deletion_query_definitions += ','.join(chunk)
                deletion_query_definitions += ')'
                deletion_query_mt_translated_definitions = "delete from mt_translated_definition where id in ("
                deletion_query_mt_translated_definitions += ','.join(chunk)
                deletion_query_mt_translated_definitions += ')'
                try:
                    session.execute(deletion_query_mt_translated_definitions)
                    session.execute(deletion_query_definitions)
                except Exception as exc:
                    print("Error! rollbacking", exc)
                    session.rollback()
                else:
                    session.commit()
                finally:
                    session.close()
                    session.begin(subtransactions=True)

                chunk = set()
                count = 0
                deleted += 1000
                print(f"Deleted {deleted}/{unused_len}")

        deletion_query_definitions = "delete from definitions where id in ("
        deletion_query_definitions += ','.join(chunk)
        deletion_query_definitions += ')'
        deletion_query_mt_translated_definitions = "delete from mt_translated_definition where id in ("
        deletion_query_mt_translated_definitions += ','.join(chunk)
        deletion_query_mt_translated_definitions += ')'
        try:
            session.execute(deletion_query_mt_translated_definitions)
            session.execute(deletion_query_definitions)
        except Exception as exc:
            print("Error! rollbacking", exc)
            session.rollback()
        else:
            session.commit()
        finally:
            end_time = time.time()
            print(f"Deletion complete. Took {end_time - begin_time} seconds")
            session.close()


if __name__ == '__main__':
    bot = GarbageCollectorBot()
    bot.start()
    print('Done.')
