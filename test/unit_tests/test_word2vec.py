import sys
import types
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from api.utils import word2vec


def build_fake_gensim_modules(mock_load: MagicMock) -> dict[str, types.ModuleType]:
    """Build fake Gensim modules around a mocked downloader loader."""
    gensim_module = types.ModuleType("gensim")
    downloader_module = types.ModuleType("gensim.downloader")
    downloader_module.load = mock_load
    gensim_module.downloader = downloader_module
    return {
        "gensim": gensim_module,
        "gensim.downloader": downloader_module,
    }


class TestWord2VecCache(unittest.TestCase):
    def tearDown(self):
        """Clear the process-level model cache after each test."""
        word2vec.clear_model_cache()

    @patch("api.utils.word2vec.get_model")
    def test_text_to_vector_returns_mean_of_known_tokens(self, mock_get_model):
        fake_model = MagicMock()
        fake_model.__contains__ = MagicMock(return_value=True)
        fake_model.__getitem__ = MagicMock(
            side_effect=lambda token: np.array([1.0, 0.0, 0.0], dtype=np.float32)
        )
        mock_get_model.return_value = fake_model

        vector = word2vec.text_to_vector("hello world", model_name="test-model")

        np.testing.assert_array_equal(vector, np.array([1.0, 0.0, 0.0], dtype=np.float32))
        mock_get_model.assert_called_with("test-model")

    @patch("api.utils.word2vec.get_model")
    def test_text_to_vector_returns_zero_vector_when_all_oov(self, mock_get_model):
        fake_model = MagicMock()
        fake_model.__contains__ = MagicMock(return_value=False)
        mock_get_model.return_value = fake_model

        vector = word2vec.text_to_vector("xyz", model_name="test-model")

        np.testing.assert_array_equal(
            vector,
            np.zeros(word2vec.VECTOR_DIM, dtype=np.float32),
        )

    @patch("api.utils.word2vec.get_model")
    def test_text_to_vector_returns_none_when_model_unavailable(self, mock_get_model):
        mock_get_model.return_value = None

        self.assertIsNone(word2vec.text_to_vector("hello"))

    def test_get_model_loads_once_and_caches(self):
        """The model is loaded only once and reused for subsequent calls."""
        fake_model = MagicMock()
        fake_model.__len__ = MagicMock(return_value=3000000)
        mock_load = MagicMock(return_value=fake_model)

        with patch.dict(sys.modules, build_fake_gensim_modules(mock_load)):
            model_1 = word2vec.get_model("word2vec-google-news-300")
            model_2 = word2vec.get_model("word2vec-google-news-300")

        self.assertIs(model_1, fake_model)
        self.assertIs(model_2, fake_model)
        mock_load.assert_called_once_with("word2vec-google-news-300")

    def test_get_model_loads_different_model_names(self):
        """Each distinct model name is loaded once."""
        model_a = MagicMock()
        model_b = MagicMock()
        model_a.__len__ = MagicMock(return_value=3000000)
        model_b.__len__ = MagicMock(return_value=1000000)
        mock_load = MagicMock(side_effect=[model_a, model_b])

        with patch.dict(sys.modules, build_fake_gensim_modules(mock_load)):
            self.assertIs(word2vec.get_model("model-a"), model_a)
            self.assertIs(word2vec.get_model("model-b"), model_b)
            self.assertIs(word2vec.get_model("model-a"), model_a)
            self.assertIs(word2vec.get_model("model-b"), model_b)
        self.assertEqual(mock_load.call_count, 2)

    def test_get_model_failure_returns_none_and_does_not_cache(self):
        """Failed loads return None and allow a retry on the next call."""
        mock_load = MagicMock(side_effect=RuntimeError("download failed"))

        with patch.dict(sys.modules, build_fake_gensim_modules(mock_load)):
            self.assertIsNone(word2vec.get_model("word2vec-google-news-300"))
            self.assertEqual(len(word2vec._model_cache), 0)

            fake_model = MagicMock()
            fake_model.__len__ = MagicMock(return_value=3000000)
            mock_load.side_effect = None
            mock_load.return_value = fake_model
            self.assertIs(word2vec.get_model("word2vec-google-news-300"), fake_model)

    def test_clear_model_cache_empties_cache(self):
        """clear_model_cache removes every cached model."""
        fake_model = MagicMock()
        fake_model.__len__ = MagicMock(return_value=3000000)
        mock_load = MagicMock(return_value=fake_model)
        with patch.dict(sys.modules, build_fake_gensim_modules(mock_load)):
            word2vec.get_model("word2vec-google-news-300")

        self.assertEqual(len(word2vec._model_cache), 1)
        word2vec.clear_model_cache()
        self.assertEqual(len(word2vec._model_cache), 0)

    def test_is_sentence_transformer_model_detects_repo_ids(self):
        """Model names containing a '/' are treated as sentence-transformers repo ids."""
        self.assertTrue(word2vec._is_sentence_transformer_model("BAAI/bge-small-en"))
        self.assertFalse(word2vec._is_sentence_transformer_model("word2vec-google-news-300"))

    @patch("api.utils.word2vec.get_sentence_transformer_model")
    def test_text_to_vector_uses_sentence_transformer_for_repo_id(self, mock_get_st_model):
        fake_model = MagicMock()
        fake_model.encode = MagicMock(return_value=np.array([0.1, 0.2, 0.3], dtype=np.float32))
        mock_get_st_model.return_value = fake_model

        vector = word2vec.text_to_vector("hello world", model_name="BAAI/bge-small-en")

        np.testing.assert_array_equal(vector, np.array([0.1, 0.2, 0.3], dtype=np.float32))
        mock_get_st_model.assert_called_with("BAAI/bge-small-en")
        fake_model.encode.assert_called_once_with("hello world")

    @patch("api.utils.word2vec.get_sentence_transformer_model")
    def test_text_to_vector_returns_none_when_sentence_transformer_unavailable(self, mock_get_st_model):
        mock_get_st_model.return_value = None

        vector = word2vec.text_to_vector("hello world", model_name="BAAI/bge-small-en")

        self.assertIsNone(vector)

    @patch("api.utils.word2vec.get_sentence_transformer_model")
    def test_text_to_vector_returns_none_when_encoding_fails(self, mock_get_st_model):
        fake_model = MagicMock()
        fake_model.encode = MagicMock(side_effect=RuntimeError("encode failed"))
        mock_get_st_model.return_value = fake_model

        vector = word2vec.text_to_vector("hello world", model_name="BAAI/bge-small-en")

        self.assertIsNone(vector)

    def test_get_sentence_transformer_model_loads_once_and_caches(self):
        fake_model = MagicMock()
        fake_module = types.ModuleType("sentence_transformers")
        fake_module.SentenceTransformer = MagicMock(return_value=fake_model)

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            model_1 = word2vec.get_sentence_transformer_model("BAAI/bge-small-en")
            model_2 = word2vec.get_sentence_transformer_model("BAAI/bge-small-en")

        self.assertIs(model_1, fake_model)
        self.assertIs(model_2, fake_model)
        fake_module.SentenceTransformer.assert_called_once_with("BAAI/bge-small-en")

    def test_get_sentence_transformer_model_failure_returns_none_and_does_not_cache(self):
        fake_module = types.ModuleType("sentence_transformers")
        fake_module.SentenceTransformer = MagicMock(side_effect=RuntimeError("download failed"))

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            self.assertIsNone(word2vec.get_sentence_transformer_model("BAAI/bge-small-en"))

        self.assertEqual(len(word2vec._sentence_transformer_cache), 0)


if __name__ == "__main__":
    unittest.main()
