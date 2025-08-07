import configparser
import subprocess
import pathlib

from .utils import find_package_roots

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / ".build"
ICON_PATH = ROOT / "images/logo.png"


def init_spec_file(module_path: pathlib.Path, main_file: pathlib.Path):
    print(f"Initializing spec: {module_path.name}")
    subprocess.run(
        ["pyside6-deploy", "--init", str(main_file)], cwd=module_path, check=True
    )

    spec_file = main_file.parent / "pysidedeploy.spec"
    target_path = main_file.parent.parent / "pysidedeploy.spec"
    spec_file.rename(target_path)

    print(f"Initialized spec: {module_path.name}")


def update_spec_file(module_path: pathlib.Path, spec_file: pathlib.Path):
    print(f"Updating spec: {module_path.name}")

    config = configparser.ConfigParser()
    config.optionxform = str
    config.read(spec_file)

    build_path = BUILD_DIR / module_path.name
    build_path.mkdir(parents=True, exist_ok=True)

    icon_path = (module_path / ICON_PATH).resolve()

    config["app"]["title"] = module_path.name
    config["app"]["exec_directory"] = str(build_path)
    config["app"]["icon"] = str(icon_path)

    with open(spec_file, "w") as f:
        config.write(f)

    print(f"Updated spec: {module_path.name}")


def deploy_spec_file(module_path: pathlib.Path, spec_file: pathlib.Path):
    print(f"Deploying {module_path.name}")
    subprocess.run(["pyside6-deploy", "-c", spec_file], cwd=module_path, check=True)
    print(f"Deployed: {module_path.name}")


def deploy_module(module_path: pathlib.Path):
    main_file = module_path / "__main__.py"

    if not main_file.exists():
        return

    spec_file = module_path.parent / "pysidedeploy.spec"
    if not spec_file.exists():
        init_spec_file(module_path, main_file)

    update_spec_file(module_path, spec_file)
    deploy_spec_file(module_path, spec_file)


def deploy_pyside6_apps():
    package_roots = find_package_roots()
    for package_root in package_roots:
        deploy_module(package_root)


def main():
    deploy_pyside6_apps()


if __name__ == "__main__":
    main()
