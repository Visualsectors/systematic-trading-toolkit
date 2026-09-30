"""Run risk management through the shared toolkit CLI."""

import sys

from visualsectors_toolkit.cli import main


if __name__ == "__main__":
    raise SystemExit(main(("risk", *sys.argv[1:])))
