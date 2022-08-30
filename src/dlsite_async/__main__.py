"""Command-line interface."""
import click


@click.command()
@click.version_option()
def main() -> None:
    """DLsite Async."""  # noqa: D403


if __name__ == "__main__":
    main(prog_name="dlsite-async")  # pragma: no cover
