
## What is `botjagwar` for?

Bot-Jagwar is a side project which aims to automate editing on the Malagasy Wiktionary as much as possible.

## [Current build status](https://travis-ci.com/radomd92/botjagwar/branches)
master : ![master](https://app.travis-ci.com/radomd92/botjagwar.svg?branch=master)
dev: ![dev](https://app.travis-ci.com/radomd92/botjagwar.svg?branch=dev)

## Prerequisites
- Linux-like environment (if you're on Windows, WSL will do)
- Python 3.8 (pip is used for requirements) or later versions
- PostgreSQL 11 server or later versions, used with psycopg2


## Installation

In the project directory, run `install.sh`. The Python virtual environment as well as the scripts and the required configuration will be deployed on the target machine at `/opt/botjagwar`. They can be removed by removing the install folder.

If you intend to use the bot for editing on Wiktionary, you need to set up your pywikibot instance.
Visit [Pywikibots installation manual](https://www.mediawiki.org/wiki/Manual:Pywikibot/Installation) for more details on how to do that.

To confirm whether you have a working installation, run `test.sh`. All tests should pass.
However, some of them may not pass on the Raspberry Pi due files not being deleted after teardowns.

## Running
- Go to `/opt/botjagwar`
- Run `python3 wiktionary_irc.py` in a screen instance
- Run `python3 dictionary_service.py` in a screen instance, serves on 8001
- Run `python3 entry_translator.py`in a screen instance, serves on 8000

Alternatively, a supervisor script `supervisor-botjagwar.conf` can help you configure the program above as services.


## Components and scripts

### Real-time lemma translator

Connects to the recent changes real time feed of French and English Wiktionaries on `irc.wikimedia.org` and attempts to translate every entries
that are being created.

#### wiktionary_irc.py

This is an IRC client and connects to entry_translator.py REST API for translations.

#### dictionary_service.py

Word storage engine. REST API required by the `wiktionary_irc.py` to store and get translations.

Default engine is SQLite, please see `database_uri` at `conf/config.ini` for a change. It is used by SQLAschemy to connect to the database backend.

This API has been tested and used on MySQL (manual test), SQLite (automatic test) and PostgreSQL databases (manual test) thanks to SQLAlchemy. For the best performance and mostly if you want to use the frontend application, please use PostgreSQL.

##### Front-end application
You might also be interested in the associated frontend: [dictionary frontend](https://github.com/radomd92/botjagwar-frontend)
which provides an interface to manage dictionary in a more user-friendly manner. It will allow you to edit link and delete words and definitions as well as an access to a per-language dictionary.

The frontend application makes use of VueJS, and Nginx. With PostgreSQL backend, Postgrest is used to lessen the load on `dictionary_service` for read operations. Nginx acts as a proxy which redirect requests to either `dictionary_service` or PostgREST API.

#### entry_translator.py

Wiki page handling that also uses translation and page rendering APIs. Side effects are page updates and creations to the target wiki.
REST service required by `wiktionary_irc.py`

### word_forms.py

Independent script to translate non-lemma entries on the English Wiktionary into Malagasy.

### list_wikis.py

Independent script that updates the statistics table for each Wiktionary, Wikipedia and Wikibooks and stores it to the user's subpage on the Malagasy Wiktionary

### unknown_language_management.py

Independent script, which, in detail:
- fetches the words created in the last 30 days;
- checks the missing language templates, and translates them in malagasy with a basic phonetic transcription algorithm;
- if the language name could be translated: creates the templates and categories for the missing language; or
- stores a list of untranslated language names in a table, stored on the Malagasy wiktionary at `Mpikambana:<USERNAME>/Lisitry ny kaodim-piteny tsy voafaritra`

## Copyright

© 2018 Rado A. (Terakasorotany) -- MIT Licence.
