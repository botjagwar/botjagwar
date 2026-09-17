import os
import sys
import json
import time
from pprint import pprint

import html2text

import requests

import pywikibot

from google import genai
from tenacity import retry, wait_random_exponential, stop_after_attempt

from api.output import Entry
from api.page_renderer import WikiPageRendererFactory

from api.config import BotjagwarConfig

config = BotjagwarConfig()

FORMAT_PROMPT = """
 I need you to act as a parser/reformulator for the Malagasy dictionary website tenymalagasy.org.

The user is looking for the definition of the word: "{{word}}" on tenymalagasy.org.

Please find the dictionary entry for this word using the markdown page dump below.

You must strictly format the output as a JSON object with the following structure:
{
  "entry": "the entry name, word name",
  "part_of_speech": "part of speech: use 'ana' for nouns, 'mpam' for adjectives, 'mat' for verbs, 'e-mat' for verb forms",
  "language": "2-letter ISO code for the language, often mg, fr or en",
  "definitions": [
    {"definition_language": "mg", "definition": "the reformulated definition in malagasy",
       "example": ['please generate an example sentence here containing the word or one of its forms.']
       },
  ]
}

Rules:
0. If you CANNOT find any definitions on the page dump below; ONLY RETURN an empty JSON file.
1. Find definitions in Malagasy (mg) if available.
2. IMPORTANT: For the Malagasy (mg) definitions, do NOT copy the text word-for-word.
   You MUST reformulate or paraphrase the Malagasy explanation to avoid copyright issues, while strictly preserving the original meaning.
3. If you DID NOT find a malagasy defintion BUT INSTEAD found an English definition, translate that English definition into malagasy
4. Return ONLY the JSON object. Do not include any markdown formatting, code fences, or explanatory text.
5. If you find MULTIPLE definitions, include them in the array.
6. Part of speech SHOULD BE abbreviated as follows:
    - 'ana' for nouns, 'e-ana' for noun forms,
    - 'mpam' for adjectives, 'e-mpam' for adjective forms,
    - 'mat' for verbs, 'e-mat' for verb forms
    - 'tamb' for adverbs.
    - 'tovona' for prefixes.
    - 'tovana' for suffixes.
    ONLY use one part of speech. DO NOT combine them in the same field.
7. If there is NO explanatory text in the Malagasy definition, ONLY mention that it is a derived term from the root specified in the "fototeny" row, or obetween parantheses.
8. If you DID NOT find a malagasy, french, or english definition, ONLY mention that it is a derived term from the root specified in the "fototeny" row, or obetween parantheses.
   DO NOT attempt to define the word on your own in that case. DO NOT create any examples sentences in that case.

The Markdown content of the page is:
```markdown

{{pagedump}}

```

"""




class LlmWordFixer:
    def __init__(self, model='gemini-2.5-flash-lite'):
        self.model = model
        self.renderer = WikiPageRendererFactory("mg")()

    @retry(wait=wait_random_exponential(min=1, max=240), stop=stop_after_attempt(6))
    def get_gemini_answer(self, prompt: str):
        """
        Initializes the Gemini client and sends a prompt to the model.

        Args:
            prompt: The text prompt to send to the Gemini model.
        """
        api_key = config.get("gemini_api_key", "global")
        os.environ["GEMINI_API_KEY"] = api_key

        if not api_key:
            print("🚨 Error: GEMINI_API_KEY environment variable not set.")
            print("Please set the environment variable to your actual API key.")
            return

        client = genai.Client()
        # model = 'gemini-2.5-flash'
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        text = response.text.replace("```json", "").replace("```", "").strip()
        print(text)
        return text

    def get_entry(self, word: str):
        headers = {'User-Agent': 'Botjagwar Mozilla/5.0 (Windows NT 10.0; Win64'}
        resp = requests.get(f'https://tenymalagasy.org/bins/teny2/{word}', headers=headers, verify=False)
        if resp.status_code != 200:
            raise ValueError(f"Word '{word}' not found on tenymalagasy.org")
        else:
            pagedump = resp.text.replace('  ', '')

            # tokens are expensive lol don't process unless we're sure there's definitions
            if "Teny mitovitovy amin'ny" in pagedump:
                raise ValueError(f"No word matching '{word}' on tenymalagasy.org")
            if "Fanazavàna teny malagasy" not in pagedump:
                if "Sokajin-teny" not in pagedump:
                    raise ValueError(f"No definitions found for word '{word}' on tenymalagasy.org")

        # stop before word forms
        if 'haiendriteny' in pagedump.lower():
            pagedump = pagedump[:pagedump.lower().find('haiendriteny')]

        # put HTML page into markdown to spare LLM tokens and for better understanding by LLM
        text = html2text.html2text(pagedump).strip()
        prompt = FORMAT_PROMPT.replace("{{word}}", word).replace('{{pagedump}}', text)

        # print(prompt)
        response = self.get_gemini_answer(prompt)
        try:
            response = json.loads(response)
        except Exception as error:
            print(response)
            raise error
        if 'entry' not in response or 'definitions' not in response:
            print(response)
            raise ValueError("Invalid response format")
        if not response['definitions']:
            print(response)
            raise ValueError("No definitions found")
        if response['entry'] != word:
            print(response)
            raise ValueError("Entry name does not match the requested word")
        if not all('definition_language' in d and 'definition' in d for d in response['definitions']):
            print(response)
            raise ValueError("Definitions are missing required fields")
        return response

    def process_entry(self, entry_dict: dict):
        """
        Entry to wiki page
        """
        print(">>>> ", entry_dict['entry'], ' <<<<')
        pprint(entry_dict)
        wiki_page = pywikibot.Page(pywikibot.Site("mg", "wiktionary"), entry_dict['entry'])

        if wiki_page.exists():
            page_content = old_content = wiki_page.get()
        else:
            page_content = old_content = ''

        # rm old contents
        page_content = self.renderer.delete_section('mg', page_content)
        entry_dict['additional_data'] = {
            "examples": [
                d['example']
                for d in entry_dict['definitions']
                if 'example' in d and d['definition_language'] == 'mg'
            ]
        }
        entry_dict['definitions'] = [d['definition'] for d in entry_dict['definitions'] if
                                     d['definition_language'] == 'mg']

        entry = Entry.from_dict(entry_dict)
        print(entry)
        rendered = self.renderer.render(entry)

        page_content = rendered + '\n' + page_content
        pywikibot.showDiff(old_content, page_content)
        wiki_page.put(page_content, 'fanitsiana')


def main(filename):
    entries = []
    with open(filename) as f:
        entries = [k.strip() for k in f.readlines()]

    # print(entries)
    llm_fixer = LlmWordFixer()
    for word in entries:
        # if 'ampahibemaso' in word:
        #     start = True
        # if not start:
        #     print(f"Skipping word '{word}'")
        #     continue
        try:
            entry = llm_fixer.get_entry(word)
            if isinstance(entry, list):
                entry = entry[0]

            llm_fixer.process_entry(entry)
            time.sleep(1)
            # print(json.dumps(entry, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Error processing word '{word}': {e}")


if __name__ == "__main__":
    category = sys.argv[1]
    main(category)
    # entry = get_entry("anilana")
    # process_entry(entry)
