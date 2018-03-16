
## Prerequisites

You'll need a working Python 3.6 interpreter to run the python scripts of this project.


## Installation

In the project directory, type `make all`. This will install shell scripts in your home directory. 

If you intend to use the bot for editing on Wiktionary, you need to set up your pywikibot instance. 
Visit [Pywikibots installation manual](https://www.mediawiki.org/wiki/Manual:Pywikibot/Installation) for more details on how to do that.

To confirm whether you have a working installation, run `make test`. All tests should pass.
However, some of them may not pass on the Raspberry Pi due files not being deleted after teardowns.
Let me know about any solution to robustify those tests on Raspberry Pi. Those tests make use of the 
Pywikibot framework and will fail if the latter is not properly configured. No worries though, mocks have been set
up not to edit on-wiki.

The Python scripts and the required configuration will be deployed on the target machine at `/opt/botjagwar`. They can be removed with
`make uninstall`. 

## Components 

### wiktionary_irc.py

Connects to the recent changes real time feed of French and English Wiktionaries on `irc.wikimedia.org` and attempts to translate every entries
that are being created.

### dictionary_service.py

Word storage engine. REST API required by the `wiktionary_irc.py` to store and get translations.

### entry_translator.py

Wiki page handling that also uses translation and page rendering APIs. Side effects are page updates and creations to the target wiki.
REST service required by `wiktionary_irc.py`  


## Copyright

© 2018 Rado A. (Terakasorotany) -- MIT Licence.
