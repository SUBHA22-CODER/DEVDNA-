import io
import stat
import zipfile

import pytest

from app.analyzer.ingest import ZipSecurityError, safe_extract_zip, scan_tree
from app.analyzer.redact import REDACTED, redact
from app.config import settings


def make_zip(entries: dict[str, bytes], symlink: str | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
        if symlink:
            info = zipfile.ZipInfo(symlink)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, "/etc/passwd")
    return buf.getvalue()


@pytest.mark.parametrize("name", ["../evil.py", "a/../../evil.py", "/abs/evil.py", "C:/evil.py", "..\\evil.py"])
def test_rejects_path_traversal(tmp_path, name):
    with pytest.raises(ZipSecurityError):
        safe_extract_zip(make_zip({"ok.py": b"x=1", name: b"bad"}), tmp_path / "out")
    assert not (tmp_path / "evil.py").exists()


def test_rejects_symlinks(tmp_path):
    with pytest.raises(ZipSecurityError, match="symbolic link"):
        safe_extract_zip(make_zip({"ok.py": b"x=1"}, symlink="link"), tmp_path / "out")


def test_rejects_too_many_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_zip_entries", 5)
    with pytest.raises(ZipSecurityError, match="entries"):
        safe_extract_zip(make_zip({f"f{i}.py": b"" for i in range(6)}), tmp_path / "out")


def test_rejects_zip_bomb(tmp_path):
    bomb = make_zip({"bomb.txt": b"\0" * (5 * 1024 * 1024)})  # compresses ~1000:1
    with pytest.raises(ZipSecurityError, match="ZIP bomb"):
        safe_extract_zip(bomb, tmp_path / "out")


def test_rejects_oversized_uncompressed(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_uncompressed_bytes", 1000)
    with pytest.raises(ZipSecurityError, match="uncompressed"):
        safe_extract_zip(make_zip({"a.py": b"x" * 2000}), tmp_path / "out")


def test_rejects_non_zip(tmp_path):
    with pytest.raises(ZipSecurityError, match="not a valid ZIP"):
        safe_extract_zip(b"hello", tmp_path / "out")


def test_skips_sensitive_and_ignored_files_and_strips_top_folder(tmp_path):
    data = make_zip({
        "repo-main/app.py": b"print(1)",
        "repo-main/.env": b"SECRET=1",
        "repo-main/.env.example": b"SECRET=",
        "repo-main/keys/id_rsa": b"key",
        "repo-main/node_modules/x/index.js": b"",
        "repo-main/.git/config": b"",
        "repo-main/__pycache__/app.cpython-314.pyc": b"",
    })
    stats = safe_extract_zip(data, tmp_path / "out")
    files = sorted(p.relative_to(tmp_path / "out").as_posix() for p in (tmp_path / "out").rglob("*") if p.is_file())
    assert files == [".env.example", "app.py"]
    assert stats["skipped_sensitive"] == 2 and stats["skipped_ignored"] == 3


def test_scan_tree_ignores_sensitive(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / ".env").write_text("K=v")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text("")
    s = scan_tree(tmp_path)
    assert s["files"] == ["a.py"] and s["skipped_sensitive"] == [".env"]


@pytest.mark.parametrize("text,secret", [
    ('api_key = "sk-live-abcdef1234567890XYZ"', "sk-live-abcdef1234567890XYZ"),
    ("password: 'hunter2hunter2'", "hunter2hunter2"),
    ("postgres://admin:s3cr3tpw@db.example.com/x", "s3cr3tpw"),
    ("key = AIza" + "B" * 35, "AIza" + "B" * 35),
    ("token ghp_" + "a" * 36, "ghp_" + "a" * 36),
    ("Authorization: Bearer abcdefghijklmnopqrstuvwx", "abcdefghijklmnopqrstuvwx"),
])
def test_redaction(text, secret):
    out, n = redact(text)
    assert secret not in out and REDACTED in out and n >= 1


def test_redaction_leaves_normal_code_alone():
    code = 'self.base_url = os.environ["SHIPPING_API_URL"]'
    assert redact(code) == (code, 0)
