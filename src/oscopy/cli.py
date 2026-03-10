import argparse
import base64
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile


OSC_SELECTION = "c"
"""The system clipboard target OSC selection."""

RECORD_OUTPUT_LOG_ENV = "OSCOPY_RECORD_OUTPUT_LOG"
RECORD_COMMAND_LOG_ENV = "OSCOPY_RECORD_CMD_LOG"
RECORD_OFFSET_LOG_ENV = "OSCOPY_RECORD_OFFSET_LOG"
RECORD_DONE_FILE_ENV = "OSCOPY_RECORD_DONE_FILE"

_ANSI_ESCAPE_RE = re.compile(
    r"\x1b(?:\][^\x07]*(?:\x07|\x1b\\)|\[[0-?]*[ -/]*[@-~]|[@-Z\\-_])"
)
_CTRL_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _osc52(data: bytes) -> bytes:
    # OSC 52: ESC ] 52 ; <selection> ; <base64> BEL
    payload = base64.b64encode(data)
    return b"\x1b]52;" + OSC_SELECTION.encode("ascii") + b";" + payload + b"\x07"


def _write_clipboard(data: bytes) -> None:
    payload = _osc52(data)

    # Prefer the controlling TTY so clipboard writes still work even when
    # stdout is redirected (for example in session recording mode).
    try:
        with open("/dev/tty", "wb", buffering=0) as tty:
            tty.write(payload)
            tty.flush()
            return
    except OSError:
        pass

    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def _render_transcript(entries: list[tuple[str, str]]) -> str:
    blocks: list[str] = []
    for command, output in entries:
        cleaned = output.rstrip("\n")
        if cleaned:
            blocks.append(f"$ {command}\n{cleaned}")
        else:
            blocks.append(f"$ {command}")
    return "\n\n".join(blocks)


def _cmd_copy(args: argparse.Namespace) -> int:
    data = sys.stdin.buffer.read()
    if args.strip_trailing_newline and data.endswith(b"\n"):
        data = data[:-1]

    _write_clipboard(data)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    tokens = list(args.cmd)
    if tokens and tokens[0] == "--":
        tokens = tokens[1:]
    if not tokens:
        print("oscopy run: missing command", file=sys.stderr)
        return 2

    command = shlex.join(tokens)
    shell = os.environ.get("SHELL") or "/bin/sh"

    process = subprocess.Popen(
        [shell, "-lc", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    captured = bytearray()
    assert process.stdout is not None
    while True:
        chunk = process.stdout.read(8192)
        if not chunk:
            break
        captured.extend(chunk)
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()

    exit_code = process.wait()

    output_text = _clean_terminal_text(captured.decode("utf-8", errors="replace"))
    transcript = _render_transcript([(command, output_text)])
    _write_clipboard(transcript.encode("utf-8"))
    return exit_code


def _resolve_record_shell() -> str | None:
    shell = os.environ.get("SHELL")
    if shell and Path(shell).name == "zsh" and Path(shell).exists():
        return shell
    return shutil.which("zsh")


def _zsh_record_rc() -> str:
    return """if [[ -f \"${HOME}/.zshrc\" ]]; then
  source \"${HOME}/.zshrc\"
fi

typeset -g OSCOPY_SAVED_STDOUT_FD=-1
typeset -g OSCOPY_SAVED_STDERR_FD=-1
typeset -g OSCOPY_CAPTURE_ACTIVE=0

_oscopy_preexec() {
  builtin print -r -- \"$1\" >> \"$OSCOPY_RECORD_CMD_LOG\"
  local start_offset
  start_offset=$(command wc -c < \"$OSCOPY_RECORD_OUTPUT_LOG\" 2>/dev/null || builtin echo 0)
  builtin printf '%s\\n' \"$start_offset\" >> \"$OSCOPY_RECORD_OFFSET_LOG\"

  exec {OSCOPY_SAVED_STDOUT_FD}>&1
  exec {OSCOPY_SAVED_STDERR_FD}>&2
  exec > >(tee -a \"$OSCOPY_RECORD_OUTPUT_LOG\") 2>&1
  OSCOPY_CAPTURE_ACTIVE=1
}

_oscopy_precmd() {
  if [[ \"$OSCOPY_CAPTURE_ACTIVE\" != \"1\" ]]; then
    return
  fi

  exec 1>&$OSCOPY_SAVED_STDOUT_FD 2>&$OSCOPY_SAVED_STDERR_FD
  exec {OSCOPY_SAVED_STDOUT_FD}>&-
  exec {OSCOPY_SAVED_STDERR_FD}>&-
  OSCOPY_CAPTURE_ACTIVE=0

  local end_offset
  end_offset=$(command wc -c < \"$OSCOPY_RECORD_OUTPUT_LOG\" 2>/dev/null || builtin echo 0)
  builtin printf '%s\\n' \"$end_offset\" >> \"$OSCOPY_RECORD_OFFSET_LOG\"
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec _oscopy_preexec
add-zsh-hook precmd _oscopy_precmd

oscopy() {
  command oscopy \"$@\"
  local code=$?
  if [[ \"$1\" == \"stop\" ]]; then
    exit \"$code\"
  fi
  return \"$code\"
}
"""


def _clean_terminal_text(text: str) -> str:
    # Remove OSC/CSI escapes and non-printable control chars for clean transcripts.
    text = _ANSI_ESCAPE_RE.sub("", text)
    text = text.replace("\r", "")
    text = _CTRL_CHARS_RE.sub("", text)
    return text


def _cmd_record() -> int:
    if os.environ.get(RECORD_OUTPUT_LOG_ENV):
        print("oscopy: recording is already active in this shell", file=sys.stderr)
        return 1

    shell = _resolve_record_shell()
    if shell is None:
        print("oscopy record currently requires zsh", file=sys.stderr)
        return 1

    session_dir = Path(tempfile.mkdtemp(prefix="oscopy-record-"))
    output_log = session_dir / "output.log"
    command_log = session_dir / "commands.log"
    offset_log = session_dir / "offsets.log"
    done_file = session_dir / "done"
    zdotdir = session_dir / "zdotdir"
    zdotdir.mkdir(parents=True, exist_ok=True)

    output_log.touch()
    command_log.touch()
    offset_log.touch()
    (zdotdir / ".zshrc").write_text(_zsh_record_rc(), encoding="utf-8")

    env = os.environ.copy()
    env[RECORD_OUTPUT_LOG_ENV] = str(output_log)
    env[RECORD_COMMAND_LOG_ENV] = str(command_log)
    env[RECORD_OFFSET_LOG_ENV] = str(offset_log)
    env[RECORD_DONE_FILE_ENV] = str(done_file)
    env["ZDOTDIR"] = str(zdotdir)

    print("Recording session started. Run `oscopy stop` to finish and copy.", file=sys.stderr)
    shell_code = subprocess.call([shell, "-i"], env=env)

    finished = done_file.exists()
    if not finished:
        print("Recording ended without `oscopy stop`; nothing copied.", file=sys.stderr)

    shutil.rmtree(session_dir, ignore_errors=True)
    if finished:
        return 0
    return shell_code


def _parse_record_entries(output_log: Path, command_log: Path, offset_log: Path) -> list[tuple[str, str]]:
    output_bytes = output_log.read_bytes()
    commands = command_log.read_text(encoding="utf-8", errors="replace").splitlines()
    offset_values: list[int] = []
    for raw in offset_log.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            offset = int(line)
        except ValueError:
            continue
        offset_values.append(offset)

    ranges: list[tuple[int, int]] = []
    size = len(output_bytes)
    for i in range(0, len(offset_values) - 1, 2):
        start = max(0, min(size, offset_values[i]))
        end = max(0, min(size, offset_values[i + 1]))
        if end < start:
            start, end = end, start
        ranges.append((start, end))

    entries: list[tuple[str, str]] = []
    for idx, (start, end) in enumerate(ranges):
        command = commands[idx] if idx < len(commands) else ""
        stripped = command.strip()
        if not stripped:
            continue
        if stripped.startswith("oscopy stop"):
            continue
        segment = _clean_terminal_text(output_bytes[start:end].decode("utf-8", errors="replace"))
        entries.append((stripped, segment))

    return entries


def _cmd_stop() -> int:
    output_log = os.environ.get(RECORD_OUTPUT_LOG_ENV)
    command_log = os.environ.get(RECORD_COMMAND_LOG_ENV)
    offset_log = os.environ.get(RECORD_OFFSET_LOG_ENV)
    done_file = os.environ.get(RECORD_DONE_FILE_ENV)

    if not output_log or not command_log or not offset_log:
        print("oscopy stop: no active recording session", file=sys.stderr)
        return 1

    output_path = Path(output_log)
    command_path = Path(command_log)
    offset_path = Path(offset_log)
    if not output_path.exists() or not command_path.exists() or not offset_path.exists():
        print("oscopy stop: recording session data is missing", file=sys.stderr)
        return 1

    entries = _parse_record_entries(output_path, command_path, offset_path)
    if not entries:
        print("oscopy stop: no recorded commands found; clipboard unchanged", file=sys.stderr)
        if done_file:
            Path(done_file).touch()
        return 1
    transcript = _render_transcript(entries)
    _write_clipboard(transcript.encode("utf-8"))

    if done_file:
        Path(done_file).touch()

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oscopy",
        description="Copy text to clipboard via OSC 52, or record shell commands and output.",
    )
    subparsers = parser.add_subparsers(dest="mode")

    copy_parser = subparsers.add_parser(
        "copy",
        help="copy stdin to clipboard",
        description="Copy stdin to clipboard via OSC 52.",
    )
    copy_parser.add_argument(
        "-x",
        "-s",
        "--strip-trailing-newline",
        action="store_true",
        help="strip the trailing newline (useful with echo)",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="run one command, copy `$ command + output`",
        description="Run one command and copy its transcript to clipboard.",
    )
    run_parser.add_argument(
        "cmd",
        nargs=argparse.REMAINDER,
        help="command to execute (prefix with -- if needed)",
    )

    subparsers.add_parser(
        "record",
        help="start a temporary recording shell",
        description="Start a recording shell session. Stop with `oscopy stop`.",
    )
    subparsers.add_parser("start", help="alias for record")
    subparsers.add_parser(
        "stop",
        help="stop recording and copy transcript",
        description="Stop an active recording session and copy its transcript.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)

    known_modes = {"copy", "run", "record", "start", "stop", "-h", "--help"}
    if not raw_argv:
        raw_argv = ["copy"]
    elif raw_argv[0] not in known_modes:
        raw_argv = ["copy", *raw_argv]

    parser = _build_parser()
    args = parser.parse_args(raw_argv)

    if args.mode == "copy":
        return _cmd_copy(args)
    if args.mode == "run":
        return _cmd_run(args)
    if args.mode in {"record", "start"}:
        return _cmd_record()
    if args.mode == "stop":
        return _cmd_stop()

    parser.print_help()
    return 2
