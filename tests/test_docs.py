"""The documentation gate, and the proof that it can say no."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
import check_docs  # noqa: E402


def test_the_documents_are_clean():
    assert check_docs.problems() == []


def test_a_broken_link_and_an_unindexed_document_are_both_caught(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("see [the plan](docs/PLAN.md) and [gone](docs/GONE.md)\n", encoding="utf-8")
    (tmp_path / "docs" / "README.md").write_text("# index\n\n[plan](PLAN.md)\n", encoding="utf-8")
    (tmp_path / "docs" / "PLAN.md").write_text("plan\n", encoding="utf-8")
    (tmp_path / "docs" / "ORPHAN.md").write_text("nobody links me\n", encoding="utf-8")
    found = check_docs.problems(tmp_path)
    assert any("docs/GONE.md does not resolve" in p for p in found)
    assert any("does not index ORPHAN.md" in p for p in found)
    assert not any("PLAN.md does not resolve" in p for p in found)
