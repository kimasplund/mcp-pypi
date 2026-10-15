import subprocess
import sys


def test_version_is_literal_4():
    import mcp_pypi

    assert mcp_pypi.__version__ == "4.0.0"


def test_importing_package_does_not_import_server():
    code = "import sys, mcp_pypi; print('mcp_pypi.server' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
