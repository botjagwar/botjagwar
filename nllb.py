from os import environ

from flask import Flask, jsonify, request

try:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pytorch_utils
except ImportError as e:
    raise ImportError(
        "This API needs transformers module to be installed. Please install it and try again"
    ) from e

app = Flask(__name__)


class Translator:
    def __init__(self, model_name="nllb-200-distilled-1.3B"):
        self._device = "cuda:0" if pytorch_utils.torch.cuda.is_available() else "cpu"
        self._tokenizer = None
        self._model = None
        self._model_name = model_name
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

    def translate(self, text):
        inputs = self.tokenizer(text, return_tensors="pt").to(self._device)
        translated_tokens = self.model.generate(
            **inputs,
            forced_bos_token_id=self.tokenizer.lang_code_to_id["plt_Latn"],
            max_length=1000
        )
        return self.tokenizer.batch_decode(
            translated_tokens, skip_special_tokens=True
        )[0]


translator = Translator()


@app.route("/translate/<source>/<target>", methods=["POST", "GET"])
def translate(source, target):
    text = request.args.get("text")
    return jsonify({"translated": translator.translate(text)})


PORT = 8888

if __name__ == "__main__":
    HOST = environ.get("SERVER_HOST", "0.0.0.0")
    try:
        PORT = int(environ.get("SERVER_PORT", PORT))
    except ValueError:
        PORT = 8000
    app.run(HOST, PORT)
