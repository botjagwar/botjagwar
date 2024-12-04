import re

import psycopg2.errors

from api.config import BotjagwarConfig

config = BotjagwarConfig()


def refine_ipa(data: str) -> str:
    lines = data.split("\n")
    for line in lines:
        if "{{audio|" in line:
            rgx = re.search("\\{\\{[Aa]udio\\|(.*)\\|(.*)\\|[A-Za-z]+", line)
            if rgx is not None:
                return rgx.groups()[1]
            else:
                print("yielded None:", line)


class AdditionalDataRefiner(object):
    input_additional_data_type = "pronunciation"
    output_additional_data_type = "audio"

    def __init__(self):
        self.pgsql_conn = psycopg2.connect(config.get("database_uri"))

    def __del__(self):
        self.pgsql_conn.close()

    def insert(self, entries: dict):
        cursor = self.pgsql_conn.cursor()

        insert_sql = b"insert into additional_word_information (word_id, type, information) values "
        for wid, output_additional_data_type, ipa_pronunciation in entries:
            insert_sql += cursor.mogrify(
                "(%s, %s, %s),", (wid, output_additional_data_type, ipa_pronunciation)
            )

        print(f"uploading 10000 entries...")
        insert_sql = insert_sql[:-1]

        try:
            cursor.execute(insert_sql)
        except psycopg2.Error as error:
            print(error)
            self.pgsql_conn.rollback()
        else:
            print(f"  uploaded!")

            self.pgsql_conn.commit()

    def process(self):
        cursor = self.pgsql_conn.cursor()
        sql = (
            b"select word_id, type, information from additional_word_information where "
        )
        sql += cursor.mogrify("type = %s", (self.input_additional_data_type,))
        print(sql)
        cursor.execute(sql)
        count = 0
        entries = {}
        for wid, wtype, data in cursor:
            ipa_pronunciation = refine_ipa(data)
            if ipa_pronunciation is not None:
                count += 1
                entries[(wid, self.output_additional_data_type, ipa_pronunciation)] = 0

            if count > 5000:
                count = 0
                self.insert(entries)
                entries = {}

    def run(self):
        self.process()


def main():
    bot = AdditionalDataRefiner()
    bot.run()


if __name__ == "__main__":
    main()
