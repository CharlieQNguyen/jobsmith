"""jobsmith: keep your job search in plain files and let an agent do the busywork."""

__version__ = "0.3.0"


def main() -> None:
    from jobsmith.cli import app

    app()
