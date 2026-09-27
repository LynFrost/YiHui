import sys
import json
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.file_dialogs as file_dialogs


def test_file_dialog_module_does_not_depend_on_tkinter_main_loop():
    source = Path(file_dialogs.__file__).read_text(encoding="utf-8")

    assert "tkinter" not in source
    assert "mainloop" not in source.lower()


def test_choose_images_parses_powershell_json(monkeypatch):
    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout='["D:\\\\Images\\\\one.png","D:\\\\Images\\\\two.png"]',
            stderr="",
        )

    monkeypatch.setattr(file_dialogs.subprocess, "run", fake_run)

    assert file_dialogs.choose_images() == [
        "D:\\Images\\one.png",
        "D:\\Images\\two.png",
    ]


def test_choose_directory_cancel_returns_empty_string(monkeypatch):
    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout='""', stderr="")

    monkeypatch.setattr(file_dialogs.subprocess, "run", fake_run)

    assert file_dialogs.choose_directory("D:\\Start") == ""


def test_dialog_subprocess_error_raises_runtime_error(monkeypatch):
    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="dialog failed")

    monkeypatch.setattr(file_dialogs.subprocess, "run", fake_run)

    try:
        file_dialogs.choose_images()
    except RuntimeError as exc:
        assert "dialog failed" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_restore_file_filter_supports_zip_and_json():
    assert "*.zip;*.json" in file_dialogs.BACKUP_FILTER


def test_clipboard_image_paths_reads_original_file_drop_list(monkeypatch, tmp_path):
    first = tmp_path / "one.png"
    second = tmp_path / "two.webp"
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps([str(first), str(second)]),
            stderr="",
        )

    monkeypatch.setattr(file_dialogs.subprocess, "run", fake_run)

    assert file_dialogs.clipboard_image_paths() == [str(first), str(second)]


def test_clipboard_image_paths_filters_non_images_and_missing_files(monkeypatch, tmp_path):
    image = tmp_path / "ok.jpg"
    text = tmp_path / "note.txt"
    missing = tmp_path / "missing.png"
    image.write_bytes(b"image")
    text.write_text("note", encoding="utf-8")

    def fake_run(*args, **kwargs):
        paths = [str(image), str(text), str(missing)]
        return SimpleNamespace(returncode=0, stdout=json.dumps(paths), stderr="")

    monkeypatch.setattr(file_dialogs.subprocess, "run", fake_run)

    assert file_dialogs.clipboard_image_paths() == [str(image)]




