from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_launcher_is_suitable_for_double_clicking():
    launcher = (ROOT / "Open-AIImageManager.cmd").read_text(encoding="utf-8")

    assert "python app.py --open" not in launcher
    assert ".venv\\Scripts\\python.exe" in launcher
    assert "C:\\ProgramData\\anaconda3\\python.exe" in launcher
    assert "py -3.12" in launcher
    assert "Could not find Python with Flask installed" in launcher
    assert "Get-NetTCPConnection" in launcher
    assert "Start-Process" in launcher
    assert "title AI Image Manager V0.67" in launcher
    assert "app.py --host %HOST% --port %PORT%" in launcher
    assert "Close the old service and restart V0.67 in this CMD" in launcher
    assert "Stop-Process -Id $conn.OwningProcess -Force" in launcher
    assert "Port %PORT% released." in launcher
    assert "AIImageManager-V0.67.log" in launcher
    assert "Tee-Object -FilePath '%LOG_FILE%' -Append" in launcher
    assert "pause" in launcher.lower()













