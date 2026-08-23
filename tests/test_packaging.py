from configparser import ConfigParser
from pathlib import Path
from shlex import split


def test_pyside_deploy_spec_has_complete_nuitka_arguments() -> None:
    project_root = Path(__file__).parents[1]
    config = ConfigParser()
    config.read(project_root / "deployment" / "pysidedeploy.spec")

    assert config["app"]["title"] == "MatterContext"
    assert (project_root / config["app"]["input_file"]).is_file()
    assert config["app"]["exec_directory"] == "artifacts/package-smoke"
    assert config["python"]["packages"]
    assert config["qt"]["modules"] == "Core,Gui,Widgets"
    assert config["nuitka"]["mode"] == "onefile"
    assert config["nuitka"]["extra_args"]


def test_pyside_deploy_spec_includes_only_the_sqlite_sqlalchemy_dialect() -> None:
    project_root = Path(__file__).parents[1]
    config = ConfigParser()
    config.read(project_root / "deployment" / "pysidedeploy.spec")

    nuitka_args = set(split(config["nuitka"]["extra_args"]))

    assert "--include-package=sqlalchemy.dialects.sqlite" in nuitka_args
    assert {
        "--nofollow-import-to=sqlalchemy.dialects.mssql",
        "--nofollow-import-to=sqlalchemy.dialects.mysql",
        "--nofollow-import-to=sqlalchemy.dialects.oracle",
        "--nofollow-import-to=sqlalchemy.dialects.postgresql",
    } <= nuitka_args
