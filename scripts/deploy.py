import subprocess
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def build_from_deploy_specs():
    for subdir in ROOT.iterdir():
        if not subdir.is_dir():
            continue

        spec_file = subdir / "pysidedeploy.spec"
        if spec_file.exists():
            print(f"Building deploy from spec for: {subdir.name}")
            subprocess.run([
                "pyside6-deploy",
                "-c", str(spec_file)
            ], cwd=subdir, check=True)
            print(f"Build complete for {subdir.name}\n")

def main():
    build_from_deploy_specs()

if __name__ == "__main__":
    main()