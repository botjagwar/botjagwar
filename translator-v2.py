from api.translation_v2.functions import translate_using_postgrest_json_dictionary

if __name__ == '__main__':
    defn = translate_using_postgrest_json_dictionary(
        'mat', '[[mine|Mine]]', 'en', 'mg'
    )
    print(defn, defn.__class__)
