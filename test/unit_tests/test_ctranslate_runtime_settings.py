"""Tests for per-request settings in the standalone NLLB services."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).parents[2]


def _load_translation_service(
    monkeypatch: pytest.MonkeyPatch,
    script_name: str,
) -> ModuleType:
    """Load a standalone service with its optional model dependencies stubbed."""
    gevent = ModuleType("gevent")
    pywsgi = ModuleType("gevent.pywsgi")
    pywsgi.WSGIServer = Mock  # type: ignore[attr-defined]
    gevent.pywsgi = pywsgi  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gevent", gevent)
    monkeypatch.setitem(sys.modules, "gevent.pywsgi", pywsgi)

    if script_name == "ctranslate.py":
        transformers = ModuleType("transformers")
        transformers.AutoModelForSeq2SeqLM = Mock  # type: ignore[attr-defined]
        transformers.AutoTokenizer = Mock  # type: ignore[attr-defined]
        modeling_utils = ModuleType("transformers.modeling_utils")
        modeling_utils.PreTrainedModel = object  # type: ignore[attr-defined]
        tokenization_utils = ModuleType("transformers.tokenization_utils_base")
        tokenization_utils.BatchEncoding = dict  # type: ignore[attr-defined]
        tokenization_utils.PreTrainedTokenizerBase = object  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "transformers", transformers)
        monkeypatch.setitem(sys.modules, "transformers.modeling_utils", modeling_utils)
        monkeypatch.setitem(
            sys.modules,
            "transformers.tokenization_utils_base",
            tokenization_utils,
        )
    else:
        ctranslate2 = ModuleType("ctranslate2")
        ctranslate2.Translator = Mock  # type: ignore[attr-defined]
        sentencepiece = ModuleType("sentencepiece")
        sentencepiece.SentencePieceProcessor = Mock  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "ctranslate2", ctranslate2)
        monkeypatch.setitem(sys.modules, "sentencepiece", sentencepiece)

    module_name = f"test_{script_name.removesuffix('.py').replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, ROOT / script_name)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def _validate_translation_quality(
    module: ModuleType,
    script_name: str,
    translated_text: str,
    enabled_override: bool,
) -> None:
    """Invoke either service's quality check with its native arguments."""
    if script_name == "ctranslate-lite.py":
        module.translator._validate_translation_quality(
            "source meaning",
            translated_text,
            "eng_Latn",
            "plt_Latn",
            beam_size=4,
            max_batch_size=32,
            roundtrip_validation_enabled=enabled_override,
        )
        return
    module.translator._validate_translation_quality(
        "source meaning",
        translated_text,
        "eng_Latn",
        "plt_Latn",
        roundtrip_validation_enabled=enabled_override,
    )


@pytest.mark.parametrize("script_name", ["ctranslate.py", "ctranslate-lite.py"])
@pytest.mark.parametrize(
    ("query_suffix", "expected_override"),
    [("", None), ("&roundtrip_validation=true", True), ("&roundtrip_validation=false", False)],
)
def test_translate_route_forwards_roundtrip_override(
    monkeypatch: pytest.MonkeyPatch,
    script_name: str,
    query_suffix: str,
    expected_override: bool | None,
) -> None:
    """Forward an optional request override without loading either NLLB model."""
    module = _load_translation_service(monkeypatch, script_name)
    translator = Mock()
    translator.translate.return_value = (
        ["translated"] if script_name == "ctranslate-lite.py" else "translated"
    )
    module.translator = translator

    response = module.app.test_client().get(
        "/translate/eng_Latn/plt_Latn?text=source" + query_suffix
    )

    assert response.status_code == 200
    assert response.get_json() == {"translated": "translated"}
    source_arg: str | list[str] = (
        ["source"] if script_name == "ctranslate-lite.py" else "source"
    )
    translator.translate.assert_called_once_with(
        source_arg,
        "eng_Latn",
        "plt_Latn",
        roundtrip_validation_enabled=expected_override,
    )


@pytest.mark.parametrize("script_name", ["ctranslate.py", "ctranslate-lite.py"])
def test_translate_route_rejects_invalid_roundtrip_override(
    monkeypatch: pytest.MonkeyPatch,
    script_name: str,
) -> None:
    """Reject ambiguous runtime values instead of silently changing safeguards."""
    module = _load_translation_service(monkeypatch, script_name)
    module.translator = Mock()

    response = module.app.test_client().get(
        "/translate/eng_Latn/plt_Latn?text=source&roundtrip_validation=sometimes"
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "roundtrip_validation must be true or false."
    }
    module.translator.translate.assert_not_called()


@pytest.mark.parametrize("script_name", ["ctranslate.py", "ctranslate-lite.py"])
def test_disabled_roundtrip_keeps_repeated_output_check(
    monkeypatch: pytest.MonkeyPatch,
    script_name: str,
) -> None:
    """Disabling back-translation never disables the local repetition guard."""
    module = _load_translation_service(monkeypatch, script_name)
    roundtrip = Mock(side_effect=AssertionError("round-trip translation ran"))
    module.translator._translate_without_quality_checks = roundtrip

    _validate_translation_quality(module, script_name, "translated meaning", False)
    roundtrip.assert_not_called()
    with pytest.raises(module.TranslationQualityError, match="repeats the term"):
        _validate_translation_quality(
            module,
            script_name,
            "term term term term",
            False,
        )


@pytest.mark.parametrize("script_name", ["ctranslate.py", "ctranslate-lite.py"])
def test_enabled_override_supersedes_disabled_process_default(
    monkeypatch: pytest.MonkeyPatch,
    script_name: str,
) -> None:
    """An enabled request override runs the check even if the process default is off."""
    module = _load_translation_service(monkeypatch, script_name)
    module.translator._roundtrip_validation_enabled = False
    roundtrip_result: str | list[str] = (
        ["source meaning"] if script_name == "ctranslate-lite.py" else "source meaning"
    )
    roundtrip = Mock(return_value=roundtrip_result)
    module.translator._translate_without_quality_checks = roundtrip
    monkeypatch.setattr(module, "cosine_similarity_for_texts", lambda *_args: 1.0)

    _validate_translation_quality(module, script_name, "translated meaning", True)

    if script_name == "ctranslate-lite.py":
        roundtrip.assert_called_once_with(
            ["translated meaning"],
            "plt_Latn",
            "eng_Latn",
            beam_size=4,
            max_batch_size=32,
        )
    else:
        roundtrip.assert_called_once_with(
            "translated meaning",
            "plt_Latn",
            "eng_Latn",
        )
