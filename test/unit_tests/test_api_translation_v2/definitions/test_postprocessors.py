
from api.translation_v2.functions.definitions import postprocessors


def test_remove_definition_if_too_many_foreign_words(monkeypatch, tmp_path):
    cfg = tmp_path / "config.ini"
    cfg.write_text("[nllb]\nremaining_words_threshold = 0\n")
    monkeypatch.setattr(postprocessors, "CONFIG_PATH", cfg)

    result = postprocessors.remove_definition_if_too_many_foreign_words("you and me")
    assert result is None

    result = postprocessors.remove_definition_if_too_many_foreign_words("miarahaba anao tompoko")
    assert result is not None
    assert result == "miarahaba anao tompoko"
