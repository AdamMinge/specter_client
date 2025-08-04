import subprocess
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

def find_modules_with_main():
    for subdir in ROOT.iterdir():
        main_file = subdir / "__main__.py"
        if subdir.is_dir() and main_file.exists():
            yield subdir

def create_deploy_configs():
    for module_dir in find_modules_with_main():
        print(f"Creating deploy config for: {module_dir.name}")
        subprocess.run([
            "pyside6-deploy",
            "--init", str(module_dir / "__main__.py")
        ], check=True)
        print(f"Deploy config created for {module_dir.name}\n")

def main():
    create_deploy_configs()

if __name__ == "__main__":
    main()