import subprocess
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent

def build_rcc_all():
    for qrc_file in ROOT.rglob("*.qrc"):
        output_py = qrc_file.with_name(f"{qrc_file.stem}.py")
        print(f"Building RCC: {qrc_file} → {output_py}")
        subprocess.run([
            "pyside6-rcc",
            "-o", str(output_py),
            str(qrc_file)
        ], check=True)
        print(f"RCC built: {output_py}")

def build_grpc_all():
    for proto_file in ROOT.rglob("*.proto"):
        print(f"Compiling gRPC: {proto_file}")

        subprocess.run([
            sys.executable, "-m", "grpc_tools.protoc",
            f"-I{ROOT}",
            f"--python_out={ROOT}",
            f"--grpc_python_out={ROOT}",
            str(proto_file)
        ], cwd=ROOT, check=True)
        print(f"gRPC generated: {proto_file}")

def main():
    build_rcc_all()
    build_grpc_all()

if __name__ == "__main__":
    main()