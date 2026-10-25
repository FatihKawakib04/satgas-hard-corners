#!/usr/bin/env python3
"""Titik masuk. Ganti dengan logika proyek."""
import argparse


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=False, help="berkas masukan")
    a = p.parse_args()
    print(f"masukan: {a.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
