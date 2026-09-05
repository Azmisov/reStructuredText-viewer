"""`python -m rstview`.

The VS Code extension spawns the interpreter it resolved rather than a
console script, which may not be on PATH for that interpreter at all.
"""
from rstview.cli import main

if __name__ == "__main__":
    main()
