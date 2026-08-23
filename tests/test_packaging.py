from configparser import ConfigParser
from pathlib import Path


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
