from logging import getLogger

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from api.decorator import singleton

log = getLogger('openmt')


class TranslationError(Exception):
    pass


@singleton
class OpusMtTransformer:
    def __init__(self):
        self.loaded_languages = set()
        self.tokenizers = {}
        self.models = {}
        self.tokenizer = None
        self.model = None

    def load_model(self, source='en', target='mg'):
        if (source, target) not in self.loaded_languages:
            log.info(f"opus-mt-{source}-{target} has not been loaded yet, loading model...")
            self.loaded_languages.add((source, target))
            self.tokenizers[(source, target)] = AutoTokenizer.from_pretrained(f"user_data/opus-mt-{source}-{target}")
            self.models[(source, target)] = AutoModelForSeq2SeqLM.from_pretrained(f"user_data/opus-mt-{source}-{target}")

        self.tokenizer = self.tokenizers[(source, target)]
        self.model = self.models[(source, target)]

    def translate(self, text):
        batch = self.tokenizer([text], return_tensors="pt")
        gen = self.model.generate(**batch)
        if self.tokenizer is None:
            raise TranslationError("No translation model loaded! Please call load_model(...) before translate.")

        out_text = self.tokenizer.batch_decode(gen, skip_special_tokens=True)
        # print(text, '=> ', ' '.join(out_text))
        return ' '.join(out_text)
