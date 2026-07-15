from pathlib import Path

from speccheck.cli import main

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def test_main_version(capsys):
    import pytest

    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert "speccheck" in capsys.readouterr().out


def test_main_verify_text_output_exit_code():
    rc = main(
        [
            "verify",
            str(SAMPLES / "spec_096813.txt"),
            str(SAMPLES / "submittal_096813.txt"),
        ]
    )
    assert rc == 2  # sample submittal is intentionally non-compliant


def test_main_verify_json_output_to_file(tmp_path):
    out = tmp_path / "report.json"
    rc = main(
        [
            "verify",
            str(SAMPLES / "spec_096813.txt"),
            str(SAMPLES / "submittal_096813.txt"),
            "--format",
            "json",
            "-o",
            str(out),
        ]
    )
    assert rc == 2
    assert out.read_text(encoding="utf-8").startswith("{")


def test_main_verify_html_format(capsys):
    main(
        [
            "verify",
            str(SAMPLES / "spec_096813.txt"),
            str(SAMPLES / "submittal_096813.txt"),
            "--format",
            "html",
        ]
    )
    assert "<table>" in capsys.readouterr().out


def test_main_verify_save_and_history(monkeypatch, capsys):
    monkeypatch.setattr("speccheck.cli.save_review", lambda report: 42)

    rc = main(
        [
            "verify",
            str(SAMPLES / "spec_096813.txt"),
            str(SAMPLES / "submittal_096813.txt"),
            "--save",
        ]
    )
    assert rc == 2
    assert "saved review #42" in capsys.readouterr().err


def test_main_verify_against_missing_review(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)  # speccheck.db gets created here, not the repo
    rc = main(
        [
            "verify",
            str(SAMPLES / "spec_096813.txt"),
            str(SAMPLES / "submittal_096813.txt"),
            "--against",
            "999999",
        ]
    )
    assert rc == 1
    assert "no saved review" in capsys.readouterr().err


def test_main_history_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("speccheck.cli.list_reviews", lambda: [])
    rc = main(["history"])
    assert rc == 0
    assert "no reviews recorded" in capsys.readouterr().out
