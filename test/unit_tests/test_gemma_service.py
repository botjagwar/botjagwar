"""Offline tests for the standalone local Gemma chat service."""

from __future__ import annotations

import sys
import types
from typing import Any

import gemma_service


class FakeModel:
    """Capture generation options for deterministic generation assertions."""

    def __init__(self) -> None:
        self.options: dict[str, Any] = {}

    def create_chat_completion(self, **options: Any) -> dict[str, Any]:
        """Return a fixed OpenAI-compatible response."""
        self.options = options
        return {"choices": [{"message": {"content": "  valiny  "}}]}


def test_health_does_not_load_model(monkeypatch: Any) -> None:
    """Health remains available before heavyweight model initialization."""
    monkeypatch.setattr(gemma_service.runtime, "_load", lambda: (_ for _ in ()).throw(AssertionError("loaded")))

    response = gemma_service.app.test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_completion_uses_chat_template_and_deterministic_generation(monkeypatch: Any) -> None:
    """Temperature zero disables sampling and returns OpenAI-compatible content."""
    model = FakeModel()
    local_runtime = gemma_service.GemmaRuntime("/local/model", "cpu", 37)
    monkeypatch.setattr(local_runtime, "_load", lambda: model)
    monkeypatch.setattr(gemma_service, "runtime", local_runtime)

    response = gemma_service.app.test_client().post(
        "/v1/chat/completions",
        json={
            "model": "gemma-4-e2b-it-q4-k-m",
            "messages": [{"role": "user", "content": "Salama"}],
            "temperature": 0,
            "response_format": {"type": "text"},
        },
    )

    assert response.status_code == 200
    assert response.get_json()["choices"][0]["message"]["content"] == "valiny"
    assert model.options == {
        "messages": [{"role": "user", "content": "Salama"}],
        "max_tokens": 37,
        "temperature": 0.0,
    }


def test_model_dependency_loads_all_gguf_layers_on_gpu(tmp_path: Any, monkeypatch: Any) -> None:
    """Lazy loading sends every GGUF layer to the GPU by default."""
    model_file = tmp_path / "model.gguf"
    model_file.write_bytes(b"GGUF")
    calls: list[dict[str, Any]] = []

    class Llama:
        def __init__(self, **kwargs: Any) -> None:
            calls.append(kwargs)

    fake_llama_cpp = types.ModuleType("llama_cpp")
    fake_llama_cpp.Llama = Llama
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_llama_cpp)

    gemma_service.GemmaRuntime(str(model_file), "auto", 10)._load()

    assert calls == [
        {
            "model_path": str(model_file),
            "n_ctx": 4096,
            "n_gpu_layers": -1,
            "verbose": False,
        }
    ]


def test_model_directory_requires_exactly_one_gguf(tmp_path: Any) -> None:
    """Ambiguous or empty model directories fail before loading llama.cpp."""
    try:
        gemma_service.GemmaRuntime(str(tmp_path), "auto", 10)._load()
    except RuntimeError as error:
        assert "exactly one GGUF file" in str(error)
    else:
        raise AssertionError("empty model directory unexpectedly loaded")


def test_completion_rejects_non_text_content() -> None:
    """Multimodal message structures are rejected by the text-only service."""
    response = gemma_service.app.test_client().post(
        "/v1/chat/completions",
        json={"model": "gemma", "messages": [{"role": "user", "content": [{"type": "image"}]}]},
    )

    assert response.status_code == 400
    assert "text content" in response.get_json()["error"]["message"]


def test_main_binds_to_all_ipv4_interfaces(monkeypatch: Any) -> None:
    """The deployed HTTP endpoint is reachable through non-loopback interfaces."""
    addresses: list[tuple[str, int]] = []

    def create_server(address: tuple[str, int], application: Any) -> Any:
        addresses.append(address)
        assert application is gemma_service.app
        return types.SimpleNamespace(serve_forever=lambda: None)

    monkeypatch.setattr(gemma_service, "WSGIServer", create_server)
    monkeypatch.setattr(
        gemma_service,
        "parse_args",
        lambda: types.SimpleNamespace(port=8891, model_path="/model.gguf", device="cpu", max_tokens=10),
    )

    gemma_service.main()

    assert addresses == [("0.0.0.0", 8891)]
