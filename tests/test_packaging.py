import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_dependencies_match_requirements_file():
    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    declared = set(pyproject["project"]["dependencies"])
    required = {
        line.strip()
        for line in (PROJECT_ROOT / "requirements.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    }

    assert declared == required


def test_vercel_entrypoint_is_exported_by_main_module():
    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    main_source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")

    assert pyproject["tool"]["vercel"]["entrypoint"] == "main:app"
    assert "app = create_app()" in main_source
