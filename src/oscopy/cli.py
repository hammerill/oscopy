import argparse
import base64
import sys


OSC_SELECTION = "c"
"""The system clipboard target OSC selection."""


def _osc52(data: bytes) -> bytes:
    # OSC 52: ESC ] 52 ; <selection> ; <base64> BEL
    payload = base64.b64encode(data)
    return b"\x1b]52;" + OSC_SELECTION.encode("ascii") + b";" + payload + b"\x07"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="oscopy",
        description="Copy stdin (or args) to clipboard via OSC 52 escape sequence.",
    )
    p.add_argument(
        "text",
        nargs="*",
        help="if provided, copy this text instead of reading stdin",
    )
    p.add_argument(
        "-x", "-s", "--strip-trailing-newline",
        action="store_true",
        help="strip the trailing newline (useful with echo)",
    )
    args = p.parse_args(argv)

    if args.text:
        data = (" ".join(args.text)).encode("utf-8")
    else:
        data = sys.stdin.buffer.read()

    if args.strip_trailing_newline and data.endswith(b"\n"):
        data = data[:-1]

    sys.stdout.buffer.write(_osc52(data))
    sys.stdout.buffer.flush()
    return 0
