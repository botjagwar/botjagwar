import ctranslate2
from gevent.pywsgi import WSGIServer
from flask import Flask, jsonify, request
import sentencepiece as spm
from flask import Flask, jsonify, request
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pytorch_utils

app = Flask(__name__)


class Translator:
    def __init__(self, model_name='nllb-200-distilled-3.3B'):
        self._device = "cpu"
        # self._device = "cuda:0" if pytorch_utils.torch.cuda.is_available() else "cpu"
        self._tokenizer = None
        self._model = None
        self._model_name = model_name

        sp_model_path = "sentencepiece.bpe.model"
        # Load the source SentecePiece model
        self.sp = spm.SentencePieceProcessor()
        self.sp.load(sp_model_path)

        print("Model loaded")


    @property
    def model(self):
        if not self._model:
            # self._model = ctranslate2.Translator(self._model_name)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(self._model_name).to(self._device)
        return self._model

    @property
    def tokenizer(self):
        if not self._tokenizer:
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
        return self._tokenizer

    def translate(self, text, source, target):
        inputs = self.tokenizer(text, return_tensors="pt").to(self._device)
        translated_tokens = self.model.generate(
            **inputs, forced_bos_token_id=self.tokenizer.lang_code_to_id[target], max_length=1000
        )
        translated = self.tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
        return translated
    #
    # def translate(self, text, source, target):
    #     #
    #     source_sents_subworded = self.sp.encode_as_pieces([text])
    #     source_sents_subworded = [[source] + sent + ["</s>"] for sent in source_sents_subworded]
    #
    #     # Translate the source sentences
    #     translations_subworded = self.model.translate_batch(source_sents_subworded, batch_type="tokens",
    #                                                         max_batch_size=2024, beam_size=4, target_prefix=[[target]])
    #     translations_subworded = [translation[0]['tokens'] for translation in translations_subworded]
    #     for translation in translations_subworded:
    #         if target in translation:
    #             translation.remove(target)
    #
    #     # Desubword the target sentences
    #     translations = self.sp.decode(translations_subworded)
    #
    #     return translations[0]


class CTranslator:
    def __init__(self, model_name='nllb-200-distilled-3.3B'):
        self._device = "cpu"
        self._tokenizer = None
        self._model = None
        self._model_name = model_name

        sp_model_path = "flores200_sacrebleu_tokenizer_spm.model"

        # Load the source SentecePiece model
        self.sp = spm.SentencePieceProcessor()
        self.sp.load(sp_model_path)

        print("Model loaded")

    @property
    def model(self):
        if not self._model:
            self._model = ctranslate2.Translator(self._model_name, self._device)
            # self._model = AutoModelForSeq2SeqLM.from_pretrained(self._model_name).to(self._device)
        return self._model

    def translate(self, text, source, target):
        #
        source_sents_subworded = self.sp.encode_as_pieces([text])
        source_sents_subworded = [[source] + sent + ["</s>"] for sent in source_sents_subworded]

        # Translate the source sentences
        translations_subworded = self.model.translate_batch(source_sents_subworded, batch_type="tokens",
                                                            max_batch_size=2024, beam_size=4, target_prefix=[[target]])
        translations_subworded = [translation[0]['tokens'] for translation in translations_subworded]
        for translation in translations_subworded:
            if target in translation:
                translation.remove(target)

        # Desubword the target sentences
        translations = self.sp.decode(translations_subworded)

        return translations[0]


# translator = CTranslator('nllb-200-3.3B-int8')
translator = Translator('nllb-200-3.3B')


@app.route('/translate/<source>/<target>', methods=['POST', 'GET'])
def translate(source, target):
    text = request.args.get('text')
    return jsonify({
        'translated': translator.translate(text, source, target)
    })


PORT = 8888

# if __name__ == '__main__':
#    HOST = environ.get('SERVER_HOST', '0.0.0.0')
#    try:
#        PORT = int(environ.get('SERVER_PORT', PORT))
#    except ValueError:
#        PORT = 8000
#    app.run(HOST, PORT)

if __name__ == '__main__':
    http_server = WSGIServer(('0.0.0.0', PORT), app)
    http_server.serve_forever()
