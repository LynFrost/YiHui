from __future__ import annotations

import json
import subprocess
from pathlib import Path


IMAGE_FILTER = (
    "Image files (*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif)|"
    "*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif|All files (*.*)|*.*"
)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
BACKUP_FILTER = "AI Image Manager restore (*.zip;*.json)|*.zip;*.json|All files (*.*)|*.*"


def ps_quote(value: str) -> str:
    return "'" + str(value or "").replace("'", "''") + "'"


def run_windows_forms_dialog(script: str):
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-STA",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "文件选择进程失败").strip())

    output = (result.stdout or "").strip()
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"文件选择返回内容无法解析：{output}") from exc


def choose_directory(initial_dir: str = "") -> str:
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '选择生成路径'
$initialDir = {ps_quote(initial_dir)}
if ($initialDir -and (Test-Path -LiteralPath $initialDir)) {{
  $dialog.SelectedPath = $initialDir
}}
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
  ConvertTo-Json -Compress -InputObject $dialog.SelectedPath
}} else {{
  ConvertTo-Json -Compress -InputObject ''
}}
"""
    value = run_windows_forms_dialog(script)
    return value if isinstance(value, str) else ""


def choose_images() -> list[str]:
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = '选择图片'
$dialog.Multiselect = $true
$dialog.Filter = {ps_quote(IMAGE_FILTER)}
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
  ConvertTo-Json -Compress -InputObject @($dialog.FileNames)
}} else {{
  ConvertTo-Json -Compress -InputObject @()
}}
"""
    value = run_windows_forms_dialog(script)
    if isinstance(value, list):
        return [str(path) for path in value if path]
    if isinstance(value, str) and value:
        return [value]
    return []


def choose_backup_file(initial_dir: str = "") -> str:
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = '选择备份文件'
$dialog.Multiselect = $false
$dialog.Filter = {ps_quote(BACKUP_FILTER)}
$initialDir = {ps_quote(initial_dir)}
if ($initialDir -and (Test-Path -LiteralPath $initialDir)) {{
  $dialog.InitialDirectory = $initialDir
}}
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
  ConvertTo-Json -Compress -InputObject $dialog.FileName
}} else {{
  ConvertTo-Json -Compress -InputObject ''
}}
"""
    value = run_windows_forms_dialog(script)
    return value if isinstance(value, str) else ""


def clipboard_image_paths() -> list[str]:
    script = """
Add-Type -AssemblyName System.Windows.Forms
if ([System.Windows.Forms.Clipboard]::ContainsFileDropList()) {
  $paths = @()
  $dropList = [System.Windows.Forms.Clipboard]::GetFileDropList()
  foreach ($path in $dropList) {
    $paths += [string]$path
  }
  ConvertTo-Json -Compress -InputObject @($paths)
} else {
  ConvertTo-Json -Compress -InputObject @()
}
"""
    value = run_windows_forms_dialog(script)
    if isinstance(value, str) and value:
        raw_paths = [value]
    elif isinstance(value, list):
        raw_paths = [str(path) for path in value if path]
    else:
        raw_paths = []

    paths: list[str] = []
    for path_text in raw_paths:
        path = Path(path_text)
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if not path.is_file():
            continue
        paths.append(str(path))
    return paths
