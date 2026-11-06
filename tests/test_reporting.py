import json
import sys

import pandas as pd
import pytest

from marketlens.reporting import main


def test_cli_generation_and_replay(tmp_path, monkeypatch, capsys):
    output = tmp_path / "original"
    replay = tmp_path / "replay"
    monkeypatch.setattr(
        sys, "argv", ["marketlens-experiment", "--trials", "2", "--output", str(output)]
    )
    main()
    assert "Exported 48 actual trial-policy outcomes" in capsys.readouterr().out
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "marketlens-experiment",
            "--manifest",
            str(output / "manifest.json"),
            "--output",
            str(replay),
        ],
    )
    main()
    for name in [
        "records.csv",
        "summary.csv",
        "paired.csv",
        "sensitivity.csv",
        "manifest.json",
        "joint_fills.csv",
    ]:
        assert (output / name).read_bytes() == (replay / name).read_bytes()
    assert len(pd.read_csv(output / "records.csv")) == 48


@pytest.mark.parametrize("arguments", [["--trials", "0"], ["--seed", "-1"], ["--penalty", "-1"]])
def test_cli_invalid_arguments(arguments, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["marketlens-experiment", *arguments])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


def test_cli_does_not_silently_replay_custom_policies(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"policies": [{"name": "custom"}]}))
    monkeypatch.setattr(sys, "argv", ["marketlens-experiment", "--manifest", str(manifest)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
