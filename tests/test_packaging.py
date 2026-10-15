import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from packaging.version import Version

ROOT = Path(__file__).resolve().parent.parent


def test_version_is_a_4x_release():
    import mcp_pypi

    assert Version(mcp_pypi.__version__).major == 4


def test_importing_package_does_not_import_server():
    code = "import sys, mcp_pypi; print('mcp_pypi.server' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


@pytest.mark.skipif(shutil.which("uv") is None, reason="needs uv to build the wheel")
def test_wheel_bundles_readme_and_changelog(tmp_path):
    """`mcp-pypi --readme` / `--changelog` read these from the installed package."""
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path), str(ROOT)],
        check=True,
        capture_output=True,
    )
    (wheel,) = tmp_path.glob("mcp_pypi-*.whl")
    names = zipfile.ZipFile(wheel).namelist()

    assert "mcp_pypi/README.md" in names
    assert "mcp_pypi/CHANGELOG.md" in names


def test_readme_has_no_relative_links():
    """PyPI renders README.md as the project page, where relative links 404."""
    import re

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    targets = re.findall(r"\]\(([^)\s]+)\)", readme)
    relative = [t for t in targets if not t.startswith(("http://", "https://", "#", "mailto:"))]

    assert relative == []
