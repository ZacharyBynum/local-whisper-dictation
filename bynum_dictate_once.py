#!/usr/bin/env python3
from __future__ import annotations

import sys

import bynum_dictate


def build_args(args: list[str]) -> list[str]:
    return ["record", "--paste", "--notify", *args]


def main() -> None:
    sys.argv = [sys.argv[0], *build_args(sys.argv[1:])]
    bynum_dictate.main()


if __name__ == "__main__":
    main()
