import configparser
import subprocess
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / ".build"
ICON_PATH = ROOT / "images/logo.png"

def init_spec_file(module_path: pathlib.Path, main_file: pathlib.Path):
    print(f"Initializing spec: {module_path.name}")
    subprocess.run([
            "pyside6-deploy",
            "--init",
            str(main_file)
        ], 
        cwd=module_path, 
        check=True
    )
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
    subprocess.run([
            "pyside6-deploy", 
            "-c", 
            spec_file
        ], 
        cwd=module_path, 
        check=True
    )
    print(f"Deployed: {module_path.name}")

def deploy_module(module_path: pathlib.Path):
    main_file = module_path / "__main__.py"

    if not main_file.exists():
        return

    spec_file = module_path / "pysidedeploy.spec"
    if not spec_file.exists():
        init_spec_file(module_path, main_file)

    update_spec_file(module_path, spec_file)
    deploy_spec_file(module_path, spec_file)


def deploy_pyside6_apps():
    for module_dir in ROOT.iterdir():
        if not module_dir.is_dir():
            continue
        deploy_module(module_dir)

def main():
    deploy_pyside6_apps()

if __name__ == "__main__":
    main()