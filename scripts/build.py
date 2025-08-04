import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def build_rcc_all():
    for subdir in ROOT.iterdir():
        qrc_files = list((subdir / "resources").glob("*.qrc"))
        for qrc_file in qrc_files:
            output_py = qrc_file.with_name("rcc.py")
            print(f"Building RCC: {qrc_file} → {output_py}")
            subprocess.run([
                "pyside6-rcc",
                "-o", str(output_py),
                str(qrc_file)
            ], check=True)
            print(f"RCC built at {output_py}")

def build_grpc_all():
    for subdir in ROOT.iterdir():
        proto_dir = subdir / "proto"
        if not proto_dir.exists():
            continue

        for proto_file in proto_dir.glob("*.proto"):
            rel_proto_path = proto_file.relative_to(ROOT)
            print(f"Compiling gRPC: {rel_proto_path}")

            subprocess.run([
                "python", "-m", "grpc_tools.protoc",
                "-I", str(ROOT),
                "--python_out=.",
                str(rel_proto_path),
                "--grpc_python_out=."
            ], cwd=ROOT, check=True)

            print(f"gRPC generated from {rel_proto_path.name}")

def main():
    build_rcc_all()
    build_grpc_all()

if __name__ == "__main__":
    main()