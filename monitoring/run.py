"""Run position monitoring through the shared toolkit CLI."""

import sys

from visualsectors_toolkit.cli import main


if __name__ == "__main__":
    raise SystemExit(main(("monitor", *sys.argv[1:])))
