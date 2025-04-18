import time

import requests
from api.config import BotjagwarConfig
from api.databasemanager import DictionaryDatabaseManager


class GarbageCollectorBot(object):
    def __init__(self, database_file="default"):
        self.input_database = DictionaryDatabaseManager(database_file=database_file)

    def start(self):
        server = BotjagwarConfig().get("global", "postgrest_backend_address")
        used_definitions_q = "select distinct definition from dictionary"
        all_definitions_q = "select id from definitions"
        session = self.input_database.session
        session.begin(subtransactions=True)
        print("Fetching all definitions...")
        all_definitions = {k[0] for k in session.execute(all_definitions_q).fetchall()}
        print("Fetching used definitions...")
        used_definitions = {
            k[0] for k in session.execute(used_definitions_q).fetchall()
        }
        print(
            f"Definitions contains {len(all_definitions)} entries, of which {len(used_definitions)} are used."
        )
        unused = all_definitions - used_definitions
        unused_len = len(unused)
        print(f"{unused_len} entries will be deleted.")
        begin_time = time.time()
        print("Starting deletion...", time.time())
        data = [str(k) for k in unused]
        chunk = set()
        count = 0
        deleted = 0
        for d in data:
            d = str(d)
            count += 1
            chunk.add(d)
            if count >= 100:
                response = requests.delete(
                    f"http://{server}/mt_translated_definition?id=in.("
                    + ",".join([str(k) for k in chunk])
                    + ")"
                )
                if response.status_code >= 400:
                    print("Error!", response.json())
                # else:
                # print('Success!', response.status_code)

                response = requests.delete(
                    f"http://{server}:8100/definitions?id=in.("
                    + ",".join([str(k) for k in chunk])
                    + ")"
                )
                if response.status_code >= 400:
                    print("Error!", response.json())
                # else:
                #     print('Success!', response.status_code)

                chunk = set()
                count = 0
                deleted += 100
                print(f"Deleted {deleted}/{unused_len}")


if __name__ == "__main__":
    bot = GarbageCollectorBot()
    bot.start()
    print("Done.")
