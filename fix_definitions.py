import psycopg2

from api.config import BotjagwarConfig

config = BotjagwarConfig()
host = config.get('postgrest_backend_address')
conn = psycopg2.connect(f"dbname='botjagwar' user='postgres' host='{host}' password='isa'")

def fetch_mg_definitions():
    cur = conn.cursor()
    cur.execute("select definition from definitions where definition_language='mg';")
    return set([i[0] for i in cur.fetchall()])

def fetch_mg_words():
    cur = conn.cursor()
    cur.execute("select definition from definitions where definition_language='mg';")
    return set([i[0]for i in cur.fetchall()])

def fetch_en_words():
    cur = conn.cursor()
    cur.execute("select word from word where language='en';")
    return set([i[0] for i in cur.fetchall()])


def change_definition_language(definition, language):
    cur = conn.cursor()
    template = "update definitions " \
               "set definition_language = %s " \
               "where definition_language = 'mg' and definition = %s;"
    sql = cur.mogrify(template, (language, definition))
    print(sql)
    cur.execute(sql)


def main():
    en_words = fetch_en_words()
    mg_deftn = fetch_mg_definitions()
    mg_words = fetch_mg_words()

    en_words_ci = set([w.lower() for w in en_words])
    mg_words_ci = set([w.lower() for w in mg_words])

    definitions_to_change = []
    for defn in mg_deftn:
        defin = defn
        defn = defn.split()
        wc = len(defn)
        enc = 0
        for w in defn:
            if w.lower() in en_words_ci and w.lower() not in mg_words_ci:
                enc += 1

        if wc != 0:
            if enc/wc > .75:
                definitions_to_change.append((enc/wc, defin))

    for rate, defn in definitions_to_change:
        print(rate)
        change_definition_language(defn, 'en')

    print(len(definitions_to_change), 'definitions to change')

if __name__ == '__main__':
    main()
    conn.commit()
    conn.close()


