#!/usr/bin/env python3
"""
Simple Python terminal - run with: python terminal.py
Provides an interactive Python REPL with a clean prompt.
"""

import code
import sys

def main():
    banner = (
        "Python Terminal\n"
        "Type Python code or 'exit()' / Ctrl-D to quit.\n"
    )
    sys.ps1 = ">>> "
    sys.ps2 = "... "
    code.interact(banner=banner, local=dict(globals(), **locals()))

if __name__ == "__main__":
    main()
