
## What is `botjagwar` for?

Bot-Jagwar is a side project which aims to automate editing on the Malagasy Wiktionary as much as possible.


## Prerequisites

### Mandatory
- Linux-like environment (if you're on Windows, WSL will do)
- Python 3.9, 3.10, 3.11 or 3.12. `pip` is used for requirements It can work on later or earlier versions
  of Python 3, but their compatibility with those earlier versions is not tested.
- PostgreSQL 11 server or later versions, used with psycopg2
 - Create a database for botjagwar to populate
- HAProxy, used for the NLLB inference server and to load balance between `entry_translator` instances.
- Supervisor, to manage the load balancer and other services
- PostgREST, used for `entry_translator
 - Change the configuration in `conf/config.ini` with appropriate credentials to point to the database for botjagwar  
- Pywikibot, to access Wiktionary through its API
- RabbitMQ
- Redis server

### Optional
- Screen, to run the services in the background
- Nginx, used for the frontend application
- VueJS, used for the frontend application
- ctranslate2, used for the NLLB inference server, used by `entry_translator` 

## Installation

In the project directory, run `install.sh`. The Python virtual environment as well as the scripts and the required configuration will be deployed on the target machine at `/opt/botjagwar`. They can be removed by removing the install folder.
The installation procedure will install Python3 Virtualenv, Redis, HAProxy and Supervisor, using APT package manager. It will _not_ install PostgreSQL or RabbitMQ. If you don't have a PostgreSQL or RabbitMQ, please install them. 

If you intend to use the bot for editing on Wiktionary, you need to set up your pywikibot instance.
Visit [Pywikibots installation manual](https://www.mediawiki.org/wiki/Manual:Pywikibot/Installation) for more details on how to do that.

To confirm whether you have a working installation, run `test.sh`. All tests should pass.
However, some of them may not pass on the Raspberry Pi due files not being deleted after teardowns.

## Running
![image](https://github.com/user-attachments/assets/59a458bf-167c-4f8d-a7a0-803253c6ce40)

The `supervisor` has been parametered to run a bunch of services upon install. To see which services are started and which ones are not, see `conf/supervisor-botjagwar.conf`.

`translator_X` services are installed separately through `install-ctranslate.sh`. 30 GB of free space is required for the virtual environment and the model. Approximately 15 GB of RAM or VRAM (if running on GPU) is required _for each_ translator. Their run is managed here.

##  Components and scripts

### Real-time lemma translator

Connects to the recent changes real time feed of French and English Wiktionaries on `irc.wikimedia.org` and attempts to translate every entries
that are being created.

#### wiktionary_irc.py

This is an IRC client and connects to entry_translator.py REST API for translations.

#### dictionary_service.py

Word storage engine. REST API required by the `wiktionary_irc.py` to store and get translations.

Default engine is SQLite, please see `database_uri` at `conf/config.ini` for a change. 
It is used by SQLAschemy to connect to the database backend.

This API has been tested and used on MySQL (manual test), SQLite (automatic test)
and PostgreSQL databases (manual test) thanks to SQLAlchemy.
For the best performance and mostly if you want to use the frontend application, please use PostgreSQL.

##### Front-end application
You might also be interested in the associated frontend: [dictionary frontend](https://github.com/radomd92/botjagwar-frontend)
which provides an interface to manage dictionary in a more user-friendly manner. 
It will allow you to edit link and delete words and definitions as well as 
an access to a per-language dictionary.

The frontend application makes use of VueJS, and Nginx. With PostgreSQL backend,
Postgrest is used to lessen the load on `dictionary_service` for read operations.
Nginx acts as a proxy which redirect requests to either `dictionary_service` or PostgREST API.

#### entry_translator.py

Wiki page handling that also uses translation and page rendering APIs. 
Side effects are page updates and creations to the target wiki.
REST service required by `wiktionary_irc.py`

The requirements for this script are:
- NLLB inference server (`ctranslate.py`) being installed and running (see below for more information). You can install it using `install-ctranslate.sh` script.
- A running instance of the `dictionary_service.py` script.


#### ctranslate.py NLLB inference 

This script uses the NLLB 3.3B model to run. It has its own requirements that have minimal impact on the rest of the project.
However, for your convenience, it must be separately installed, as the whole deployment environment requires
30+ gigabytes of storage. If you ever choose to, you can install it on a separate machine. If you do that, do not forget to change 
the HAProxy settings (`translator_<x>` backends) in `conf/haproxy.conf`, so as not to break `entry_translator.py`.


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
