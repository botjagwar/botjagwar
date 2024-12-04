from logging import getLogger

try:
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, Trainer
except ImportError:
    raise ImportError(
        "This API needs transformers module to be installed. Please install it and try again"
    )

from api.decorator import singleton

log = getLogger("openmt")


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

    def get_translation_path(self, source, target):
        pass

    def load_models(self, source="en", target="mg"):
        if (source, target) not in self.loaded_languages:
            log.info(
                f"opus-mt-{source}-{target} has not been loaded yet, loading model..."
            )
            try:
                self.loaded_languages.add((source, target))
                self.tokenizers[(source, target)] = AutoTokenizer.from_pretrained(
                    f"data/opus-mt-{source}-{target}"
                )
                self.models[(source, target)] = AutoModelForSeq2SeqLM.from_pretrained(
                    f"data/opus-mt-{source}-{target}"
                )
            except OSError:
                log.warning(
                    f"Direct translation is not possible with {source} to {target}."
                )

        else:
            self.tokenizer = self.tokenizers[(source, target)]
            self.model = self.models[(source, target)]

    def train(self, seconds=3600):
        self.trainer = Trainer(
            model=self.model,
            args=None,
            data_collator=None,
        )

    def translate(self, text):
        batch = self.tokenizer([text], return_tensors="pt")
        gen = self.model.generate(**batch)
        if self.tokenizer is None:
            raise TranslationError(
                "No translation model loaded! Please call load_model(...) before translate."
            )

        out_text = self.tokenizer.batch_decode(gen, skip_special_tokens=True)
        # print(text, '=> ', ' '.join(out_text))
        return " ".join(out_text)
