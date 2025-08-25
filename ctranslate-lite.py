import ctranslate2
import sentencepiece as spm

import sys
from flask import Flask, request, jsonify
from gevent.pywsgi import WSGIServer

# Initialize the Flask app
app = Flask(__name__)
# Set the paths to the CTranslate2 model and the SentencePiece model
ct_model_path = "/opt/ctranslate/nllb-200-3.3B-int8"
sp_model_path = "/opt/ctranslate/nllb-200-3.3B-int8/flores200_sacrebleu_tokenizer_spm.model"


class CustomTranslator:
    def __init__(self, ct_model_path, sp_model_path, device="cuda"):
        """
        Initializes the CustomTranslator with the specified paths to the CTranslate2 model
        and the SentencePiece model.

        Args:
            ct_model_path (str): Path to the CTranslate2 model.
            sp_model_path (str): Path to the SentencePiece model.
            device (str): Device to run the model on ("cuda" or "cpu").
        """
        self._device = device  # Use CUDA or CPU
        self._ct_model_path = ct_model_path
        self._sp_model_path = sp_model_path
        self._translator = None
        self.sp = spm.SentencePieceProcessor()

        # Load the SentencePiece model (separately from the Translator)
        self.sp.load(self._sp_model_path)
        print(f"SentencePiece model loaded from {self._sp_model_path}")

    @property
    def translator(self):
        """Lazy-loads the CTranslate2 translator."""
        if not self._translator:
            # Initialize the CTranslate2 Translator without the sp_model_path
            self._translator = ctranslate2.Translator(self._ct_model_path, device=self._device)
        return self._translator

    def translate(self, source_sents, src_lang, tgt_lang, beam_size=4, max_batch_size=32):
        """
        Translates a list of source sentences from the source language to the target language.

        Args:
            source_sents (list): A list of source sentences to translate.
            src_lang (str): The source language code.
            tgt_lang (str): The target language code.
            beam_size (int): The beam size for translation.
            max_batch_size (int): The maximum batch size for the translation.

        Returns:
            list: The translated sentences.
        """
        # Subword the source sentences
        source_sents_subworded = [self.sp.encode_as_pieces(sent.strip()) for sent in source_sents]
        source_sents_subworded = [[src_lang] + sent + ["</s>"] for sent in
                                  source_sents_subworded]  # Add source language and EOS token

        print("First subworded source sentence:", source_sents_subworded[0])

        # Prepare the target prefix for all sentences
        target_prefix = [[tgt_lang]] * len(source_sents_subworded)

        # Translate the sentences using the ctranslate2 Translator
        translations_subworded = self.translator.translate_batch(
            source_sents_subworded,
            batch_type="tokens",
            max_batch_size=max_batch_size,
            beam_size=beam_size,
            target_prefix=target_prefix
        )

        # Extract the first hypothesis from each translation
        translations_subworded = [translation.hypotheses[0] for translation in translations_subworded]

        # Remove the target language token (tgt_lang) from the translation
        translations_subworded = [list(filter(lambda x: x != tgt_lang, trans)) for trans in translations_subworded]

        # Desubword the target sentences (convert pieces back to text)
        translations = [self.sp.decode(trans) for trans in translations_subworded]

        # Output the first sentence and its translation
        #print("First sentence and translation:", source_sents[0], translations[0], sep="\n• ")
        print('TRANSLATED >> ', translations)
        return translations


# Initialize the CustomTranslator with both model paths
translator = CustomTranslator(ct_model_path, sp_model_path, device="cuda")


@app.route("/translate/<source>/<target>", methods=["POST", "GET"])
def translate(source, target):
    text = request.args.get("text")
    try:
        # Use the CustomTranslator to perform the translation
        translated_text = translator.translate([text], source, target)[0]
        return jsonify({"translated": translated_text})
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 500


try:
    PORT = int(sys.argv[1])
except Exception as e:
    PORT = 8888

if __name__ == "__main__":
    # Start the web server with gevent
    http_server = WSGIServer(("0.0.0.0", PORT), app)
    http_server.serve_forever()