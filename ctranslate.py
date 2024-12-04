import sys
from gevent.pywsgi import WSGIServer
from flask import Flask
import sentencepiece as spm
from flask import Flask, jsonify, request
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

app = Flask(__name__)


class TranslatorError(Exception):
    pass


class Translator:
    def __init__(self, model_name="nllb-200-distilled-3.3B"):
        self._device = "cpu"
        # self._device = "cuda:0" if pytorch_utils.torch.cuda.is_available() else "cpu"
        self._tokenizer = None
        self._model = None
        self._model_name = f"/opt/ctranslate/{model_name}"

        sp_model_path = "/opt/ctranslate/sentencepiece.bpe.model"
        # Load the source SentecePiece model
        self.sp = spm.SentencePieceProcessor()
        self.sp.load(sp_model_path)

        print("Model loaded")

    @property
    def model(self):
        if not self._model:
            self._model = AutoModelForSeq2SeqLM.from_pretrained(self._model_name).to(
                self._device
            )
        return self._model

    @property
    def tokenizer(self):
        if not self._tokenizer:
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
        return self._tokenizer

    def translate(self, text, source, target):
        inputs = self.tokenizer(text, return_tensors="pt").to(self._device)
        translated_tokens = self.model.generate(
            **inputs,
            forced_bos_token_id=self.tokenizer.encode(target)[1],
            max_length=1000,
        )
        if len(translated_tokens) > 512:
            raise TranslatorError(
                f"Text too long. Maximum translatable tokens is 512"
                f" but tokenised input contained {len(translated_tokens)} tokens."
                f" This limit has been set because translation quality will strongly degrade."
            )
        return self.tokenizer.batch_decode(
            translated_tokens, skip_special_tokens=True
        )[0]


translator = Translator("nllb-200-3.3B")


@app.route("/translate/<source>/<target>", methods=["POST", "GET"])
def translate(source, target):
    text = request.args.get("text")
    return jsonify({"translated": translator.translate(text, source, target)})


try:
    PORT = int(sys.argv[1])
except Exception as e:
    PORT = 8888

if __name__ == "__main__":
    http_server = WSGIServer(("0.0.0.0", PORT), app)
    http_server.serve_forever()
