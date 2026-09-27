from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "app"


def test_v073_project_metadata_files_exist_and_match():
    assert (APP_ROOT / "VERSION").read_text(encoding="utf-8").strip() == "V0.73"
    assert (ROOT / "VERSION_V0.73.txt").is_file()

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "# 意绘（YiHui）" in readme
    assert "V0.73" in readme
    assert "Apache License 2.0" in readme

    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    assert "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION" in license_text
