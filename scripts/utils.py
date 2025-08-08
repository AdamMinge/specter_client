import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def find_package_roots():
    package_roots = []

    for top_level in ROOT.iterdir():
        if top_level.is_dir():
            for sub in top_level.iterdir():
                if sub.is_dir() and (sub / "__init__.py").exists():
                    package_roots.append(sub.resolve())

    return package_roots
