from api import entryprocessor
from api.config import BotjagwarConfig
from api.model.word import Entry
from api.output import Output
from api.rabbitmq import RabbitMqWikipageProducer
from redis_wikicache import RedisPage as Page, RedisSite as Site

config = BotjagwarConfig()
output = Output("mg")


class VerbFormGenerator:
    def __init__(self, root):
        self.root = root
        self.voices = {
            "": "fiendrika manano",
            "p": "fiendrika anoina",
        }
        self.tenses = {
            "": "ankehitriny",
            "ä": "lasa tsy efa",
            "e": "ankehitriny efa",
            "i": "lasa efa",
            "o": "ho avy",
            "ö": "ho avin'ny lasa",
            "u": "ho avy efa",
            "ü": "hoavin'ny lasa efa",
        }
        self.persons = {
            "ob": "Mpandray anjara voalohany",
            "ol": "Mpandray anjara faharoa",
            "on": "Mpandray anjara fahatelo",
            "obs": "Mpandray anjara voalohany ploraly",
            "ols": "Mpandray anjara faharoa ploraly",
            "ons": "Mpandray anjara fahatelo ploraly",
            "os": "Endrika tsy manonona mpandray anjara",
            "oy": "Mpandray anjara tsy voalaaza",
            "ods": "Mpandray anjara mifanao",
        }

    @property
    def forms(self):
        ret = []
        for tense in self.tenses:
            for voice in self.voices:
                for person in self.persons:
                    if voice == "p" and tense == "":
                        prefix_tense = "a"
                    else:
                        prefix_tense = tense
                    word = f"{voice}{prefix_tense}{self.root}{person}"
                    definition = f"{self.persons[person]} ny filazam-potoana {self.tenses[tense]} amin'ny {self.voices[voice]} "
                    definition += f"ny matoanteny [[{self.root}ön]]."
                    entry = Entry(
                        entry=word,
                        part_of_speech="e-mat",
                        definitions=[definition],
                        language="vo",
                    )
                    ret.append(entry)
        return ret


class VolapukImporter(object):
    def __init__(self):
        self.publisher = RabbitMqWikipageProducer("ikotobaity")

    def publish(self, entry):
        print(entry)
        target_page = Page(Site("mg", "wiktionary"), entry.entry, offline=False)

        if target_page.namespace().id != 0:
            raise Exception(
                f"Attempted to push translated page to {target_page.namespace().custom_name} "
                f"namespace (ns:{target_page.namespace().id}). "
                f"Can only push to ns:0 (main namespace)"
            )
        elif target_page.isRedirectPage():
            content = output.wikipages([entry])
            print(">>> " + entry.entry + " <<<")
            print(content)
            self.publisher.async_put(target_page, content, "/* {{=vo=}} */")
        else:
            # Get entries to aggregate
            original_content = ""
            if target_page.exists():
                wiktionary_processor_class = (
                    entryprocessor.WiktionaryProcessorFactory.create("mg")
                )
                wiktionary_processor = wiktionary_processor_class()
                wiktionary_processor.set_text(target_page.get())
                wiktionary_processor.set_title(entry)
                original_content = content = target_page.get()
                summary = "/* {{=vo=}} */"
                content = output.delete_section(entry.language, content)
                content += "\n"
                content += output.wikipages([entry]).strip()
            else:
                content = ""
                content += "\n"
                content += output.wikipages([entry]).strip()
                s = content.replace("\n", " ")
                # summary = f"Pejy noforonina tamin'ny « {s} »"
                summary = f"bika matoanteny volapoka vaovao"

            # Push aggregated content
            print(">>> " + entry.entry + " <<<")
            # print(content)
            if len(content) > len(original_content):
                self.publisher.async_put(target_page, content.strip("\n"), summary)

    def run(self):
        with open("user_data/list_mg_Matoanteny amin'ny teny volapoky") as pages:
            base_forms = [k.strip("\n") for k in pages.readlines()]
        print(f"There are {len(base_forms)} base forms")

        with open(
            "user_data/list_mg_Endriky ny matoanteny amin'ny teny volapoky", "r"
        ) as pages:
            page_already_created = set([k.strip("\n") for k in pages.readlines()])

        print(f"{len(page_already_created)} have already been created")
        count = 0
        page_dict = {}
        page_generated = set()
        for page in base_forms:
            if not page.endswith("ön"):
                continue
            main_form = VerbFormGenerator(page[:-2])
            for entry in main_form.forms:
                page_generated.add(entry.entry)
                page_dict[entry.entry] = entry
                count += 1

        pages_to_create = page_generated - page_already_created
        print(f"{len(pages_to_create)} pages are to be created")
        for page in pages_to_create:
            self.publish(page_dict[page])

        print(f"{count} forms were calculated")


if __name__ == "__main__":
    bot = VolapukImporter()
    bot.run()
