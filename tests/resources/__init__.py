from pathlib import Path

here = Path(__file__).parent


def get_test_resource_path(*pathsegments: str) -> Path:
    return here.joinpath(*pathsegments)
