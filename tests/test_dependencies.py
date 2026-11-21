"""Dependencies stay minimal and pinned, and the dev setup keeps Streamlit's own protections on.

Security criterion: "dependencies minimal, pinned, without known vulnerabilities". pip-audit (CI)
checks the vulnerabilities; these tests check the rest.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIN = re.compile(r"^[A-Za-z0-9_.-]+==\d+(\.\d+)*$")


def requirement_lines(name):
    lines = (ROOT / name).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def test_every_app_dependency_is_pinned_to_an_exact_version():
    lines = requirement_lines("requirements.txt")
    assert lines
    assert [line for line in lines if not PIN.match(line)] == []


def test_the_app_does_not_install_test_tools():
    names = {line.split("==")[0].lower() for line in requirement_lines("requirements.txt")}
    assert "pytest" not in names


def test_dev_requirements_add_only_pinned_test_tools_on_top_of_the_app():
    lines = requirement_lines("requirements-dev.txt")
    assert "-r requirements.txt" in lines
    extra = [line for line in lines if line != "-r requirements.txt"]
    assert any(line.startswith("pytest==") for line in extra)
    assert [line for line in extra if not PIN.match(line)] == []


def test_ci_installs_and_audits_the_dev_requirements():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "pip install -r requirements-dev.txt" in workflow
    assert "pip-audit -r requirements-dev.txt" in workflow


def dev_container():
    text = (ROOT / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8")
    text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)  # the file has // comments
    return json.loads(text)


def test_the_dev_container_keeps_cors_and_xsrf_protection_on():
    config = json.dumps(dev_container())
    assert "enableXsrfProtection false" not in config
    assert "enableCORS false" not in config


def test_the_dev_container_installs_only_the_pinned_requirements():
    command = dev_container()["updateContentCommand"]
    installs = re.findall(r"pip3? install [^;&]*", command)
    assert installs
    assert all("-r requirements" in install for install in installs), installs
