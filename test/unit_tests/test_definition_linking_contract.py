import json
from pathlib import Path

from api.page_renderer.mg import link_definition_segments


CONTRACT_PATH = Path(__file__).parents[2] / "definition_linking_contract.json"


def test_backend_follows_shared_definition_linking_contract() -> None:
    """Backend definition segments follow the same contract as Atlas."""
    examples = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    for example in examples:
        actual = [
            {"text": text, **({"target": target} if target else {})}
            for text, target in link_definition_segments(
                example["definition"],
                frozenset(example["candidates"]),
                example["currentWord"],
            )
        ]
        assert actual == example["expected"], example["name"]


def test_linkable_headword_migration_exposes_restricted_rpc() -> None:
    """The compact link candidate RPC filters rows and grants only execution."""
    migration = (Path(__file__).parents[2] / "data/migrations/005_add_linkable_lexicon_headwords.sql").read_text(
        encoding="utf-8"
    )

    assert "CREATE OR REPLACE FUNCTION public.linkable_lexicon_headwords()" in migration
    assert "source.language = 'mg'" in migration
    assert "source.part_of_speech IN ('ana', 'mat', 'mpam')" in migration
    assert "char_length(source.word::text) > 4" in migration
    assert "REVOKE ALL ON FUNCTION public.linkable_lexicon_headwords() FROM PUBLIC" in migration
    assert "GRANT EXECUTE ON FUNCTION public.linkable_lexicon_headwords() TO botjagwar" in migration
    assert "NOTIFY pgrst, 'reload schema'" in migration
