"""Allow `python -m tokenguard ...` (useful when the console script is not on PATH)."""

from tokenguard.cli import main

if __name__ == "__main__":
    main()
