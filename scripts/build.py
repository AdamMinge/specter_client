import subprocess
import sys

from .utils import find_package_roots


def build_rcc_all():
    package_roots = find_package_roots()
    for package_root in package_roots:
        for qrc_file in package_root.rglob("*.qrc"):
            output_py = qrc_file.with_name(f"{qrc_file.stem}.py")
            print(f"Building RCC: {qrc_file} → {output_py}")
            subprocess.run(
                ["pyside6-rcc", "-o", str(output_py), str(qrc_file)], check=True
            )
            print(f"RCC built: {output_py}")


def build_grpc_all():
    package_roots = find_package_roots()
    for package_root in package_roots:
        for proto_file in package_root.rglob("*.proto"):
            print(f"Compiling gRPC: {proto_file}")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "grpc_tools.protoc",
                    f"-I{package_root.parent}",
                    f"--python_out={package_root.parent}",
                    f"--grpc_python_out={package_root.parent}",
                    str(proto_file),
                ],
                cwd=package_root,
                check=True,
            )
            print(f"gRPC generated: {proto_file}")


def main():
    build_rcc_all()
    build_grpc_all()


if __name__ == "__main__":
    main()
