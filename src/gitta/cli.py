from __future__ import annotations
import argparse
import sys
import textwrap
import re
from pathlib import Path
import tempfile
import subprocess
import os
import shutil
from typing import List, Optional
from . import __version__

SUBJECT_MAX = 50
BODY_WRAP = 72


def read_input(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    editor = os.environ.get("EDITOR") or shutil.which("nano") or shutil.which("vi") or "vi"
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".commit", delete=False, encoding="utf-8") as tf:
        tmpname = tf.name
        tf.write("# Enter bullet points (leading '-' or '*' optional). Lines starting with '#' are ignored.\n")
        tf.write("# Example:\n")
        tf.write("# - module: short subject line\n")
        tf.flush()
    try:
        subprocess.call([editor, tmpname])
        text = Path(tmpname).read_text(encoding="utf-8")
        return text
    finally:
        try:
            os.unlink(tmpname)
        except OSError:
            pass


def extract_bullets(text: str) -> list[str]:
    lines = text.splitlines()
    bullets: list[str] = []
    for ln in lines:
        ln = ln.rstrip()
        if not ln:
            continue
        if ln.lstrip().startswith("#"):
            continue
        m = re.match(r'^\s*[-*]\s*(.+)$', ln)
        if m:
            bullets.append(m.group(1).strip())
        else:
            bullets.append(ln.strip())
    return bullets


def make_subject(first: str, maxlen: int = SUBJECT_MAX) -> str:
    s = re.sub(r'\s+', ' ', first).strip()
    if len(s) <= maxlen:
        return s
    cut = s[:maxlen]
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0]
    return cut + '...'


def make_body(bullets: list[str], skip_first: bool = True, width: int = BODY_WRAP) -> str:
    items = bullets[1:] if skip_first and len(bullets) > 1 else bullets
    if not items:
        return ""
    joined = ' '.join(re.sub(r'\s+', ' ', it).strip() for it in items)
    if width is not None and width > 0:
        return textwrap.fill(joined, width=width)
    return joined


def _has_bullets(text: str) -> bool:
    for ln in text.splitlines():
        if ln.lstrip().startswith("#"):
            continue
        if re.match(r"^\s*[-*]\s+", ln):
            return True
    return False


def _normalize_paragraphs(text: str) -> list[str]:
    # Convert arbitrary multi-line input into paragraphs: collapse soft line breaks within
    # a paragraph to spaces, preserve blank-line paragraph breaks.
    paras: list[str] = []
    buf: list[str] = []
    for raw in text.splitlines():
        ln = raw.rstrip()
        if not ln.strip() or ln.lstrip().startswith("#"):
            if buf:
                paras.append(re.sub(r"\s+", " ", " ".join(buf)).strip())
                buf = []
            continue
        buf.append(ln.strip())
    if buf:
        paras.append(re.sub(r"\s+", " ", " ".join(buf)).strip())
    return [p for p in paras if p]


def build_commit_message(src_text: str, subject_max: int = SUBJECT_MAX, body_wrap: int = BODY_WRAP) -> str:
    text = src_text.strip()
    if not text:
        raise SystemExit("No content found in input.")

    if _has_bullets(text):
        # Bullet mode (existing behaviour)
        bullets = extract_bullets(text)
        if not bullets:
            raise SystemExit("No content found in input.")
        subject = make_subject(bullets[0], maxlen=subject_max)
        body = make_body(bullets, skip_first=True, width=body_wrap)
        return subject + ("\n\n" + body if body else "") + "\n"

    # Free-text mode: collapse soft breaks, keep paragraphs
    paras = _normalize_paragraphs(text)
    if not paras:
        raise SystemExit("No content found in input.")
    subject = make_subject(paras[0], maxlen=subject_max)
    if body_wrap is not None and body_wrap > 0:
        wrapped_body_parts = [textwrap.fill(p, width=body_wrap) for p in paras[1:]]
    else:
        wrapped_body_parts = paras[1:]
    body = "\n\n".join(wrapped_body_parts).rstrip()
    return subject + ("\n\n" + body if body else "") + "\n"


# -------- Git helpers -------- #
def run_git(*args: str, capture: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], text=True, capture_output=capture, check=check)


def color(txt: str, fg: Optional[str] = None, bold: bool = False) -> str:
    colors = {
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "reset": "\033[0m",
    }
    prefix = ""
    if bold:
        prefix += "\033[1m"
    if fg and fg in colors:
        prefix += colors[fg]
    return f"{prefix}{txt}{colors['reset']}"


# -------- Subcommands -------- #
def cmd_status(_: argparse.Namespace) -> int:
    try:
        cp = run_git("status", "--porcelain=v1", "-b")
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr)
        return e.returncode
    lines = cp.stdout.splitlines()
    if not lines:
        print("No git repository here.")
        return 1
    if lines and lines[0].startswith("## "):
        print(color(lines[0], fg="cyan", bold=True))
        lines = lines[1:]
    staged = []
    changed = []
    untracked = []
    for ln in lines:
        if not ln:
            continue
        code = ln[:2]
        path = ln[3:]
        if code == "??":
            untracked.append(path)
        elif code[0] != " ":
            staged.append(path)
        elif code[1] != " ":
            changed.append(path)
    if staged:
        print(color("Staged:", fg="green", bold=True))
        for p in staged:
            print("  ", p)
    if changed:
        print(color("Changes not staged:", fg="yellow", bold=True))
        for p in changed:
            print("  ", p)
    if untracked:
        print(color("Untracked:", fg="red", bold=True))
        for p in untracked:
            print("  ", p)
    return 0


def cmd_graph(_: argparse.Namespace) -> int:
    try:
        cp = run_git("log", "--graph", "--oneline", "--decorate", "--all", "--color=always")
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr)
        return e.returncode
    sys.stdout.write(cp.stdout)
    return 0


def parse_selection(sel: str, max_index: int) -> List[int]:
    result: List[int] = []
    for part in sel.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, b = part.split('-', 1)
            a = int(a)
            b = int(b)
            result.extend([i for i in range(a, b+1) if 1 <= i <= max_index])
        else:
            i = int(part)
            if 1 <= i <= max_index:
                result.append(i)
    # unique preserve order
    seen = set()
    out: List[int] = []
    for i in result:
        if i not in seen:
            out.append(i)
            seen.add(i)
    return out


def cmd_stage(ns: argparse.Namespace) -> int:
    try:
        cp = run_git("status", "--porcelain=v1")
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr)
        return e.returncode
    entries = []
    for ln in cp.stdout.splitlines():
        if not ln:
            continue
        code = ln[:2]
        path = ln[3:]
        entries.append((code, path))
    if not entries:
        print("Nothing to stage.")
        return 0
    for idx, (code, path) in enumerate(entries, 1):
        print(f"{idx:2d}. {code} {path}")
    if ns.files:
        selection = ns.files
    else:
        if not sys.stdin.isatty():
            print("Interactive selection requires a TTY. Use --files.")
            return 2
        try:
            raw = input("Select files to stage (e.g. 1,3-5): ").strip()
        except EOFError:
            return 1
        idxs = parse_selection(raw, len(entries))
        selection = [entries[i-1][1] for i in idxs]
    if not selection:
        print("No selection.")
        return 0
    try:
        run_git("add", *selection, capture=False)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr)
        return e.returncode
    print("Staged:", ", ".join(selection))
    return 0


def cmd_commit(ns: argparse.Namespace) -> int:
    if ns.message:
        msg = ns.message
    else:
        src = read_input(ns.input)
        body_width = 0 if getattr(ns, "no_wrap", False) else ns.wrap
        msg = build_commit_message(src, subject_max=ns.subject_max, body_wrap=body_width)
    try:
        p = subprocess.run(["git", "commit", "-F", "-"], input=msg, text=True)
        return p.returncode
    except Exception as e:
        sys.stderr.write(str(e) + "\n")
        return 1


def cmd_diff(ns: argparse.Namespace) -> int:
    args = ["diff", "--color=always"]
    if ns.path:
        args.append(ns.path)
    try:
        cp = run_git(*args)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr)
        return e.returncode
    sys.stdout.write(cp.stdout)
    return 0


def cmd_stash(ns: argparse.Namespace) -> int:
    if ns.action == "list":
        cp = run_git("stash", "list")
        sys.stdout.write(cp.stdout)
        return 0
    elif ns.action == "show":
        ref = f"stash@{{{ns.index}}}"
        cp = run_git("stash", "show", "-p", ref)
        sys.stdout.write(cp.stdout)
        return 0
    elif ns.action == "apply":
        ref = f"stash@{{{ns.index}}}"
        p = subprocess.run(["git", "stash", "apply", ref])
        return p.returncode
    elif ns.action == "drop":
        ref = f"stash@{{{ns.index}}}"
        p = subprocess.run(["git", "stash", "drop", ref])
        return p.returncode
    else:
        print("Unknown stash action")
        return 2


def cmd_undo(ns: argparse.Namespace) -> int:
    mode = "--mixed"
    if ns.soft:
        mode = "--soft"
    if ns.hard:
        mode = "--hard"
        if sys.stdin.isatty():
            ans = input(color("Hard reset will discard changes. Continue? [y/N] ", fg="red", bold=True))
            if ans.lower() not in ("y", "yes"):
                return 1
    target = ns.target or "HEAD~1"
    p = subprocess.run(["git", "reset", mode, target])
    return p.returncode


SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[+-].*)?$")


def parse_semver(ver: str) -> tuple[int, int, int]:
    m = SEMVER_RE.match(ver)
    if not m:
        raise ValueError(f"Not a semver: {ver}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def bump_version(base: str, level: str) -> str:
    major, minor, patch = parse_semver(base)
    if level == "major":
        return f"{major+1}.0.0"
    if level == "minor":
        return f"{major}.{minor+1}.0"
    return f"{major}.{minor}.{patch+1}"


def detect_bump_level() -> str:
    try:
        base_tag = run_git("describe", "--tags", "--abbrev=0").stdout.strip()
    except subprocess.CalledProcessError:
        base_tag = "v0.1.0"
    range_expr = f"{base_tag}..HEAD" if base_tag else "HEAD"
    try:
        cp = run_git("log", "--pretty=%s%n%b", range_expr)
        text = cp.stdout
    except subprocess.CalledProcessError:
        text = ""
    level = "patch"
    for line in text.splitlines():
        l = line.strip().lower()
        if "breaking change" in l or re.match(r"^(feat|fix|chore|refactor|perf|docs|test)!", l):
            return "major"
        if l.startswith("feat"):
            level = "minor"
    return level


def cmd_tag(ns: argparse.Namespace) -> int:
    # Determine last tag
    try:
        last = run_git("describe", "--tags", "--abbrev=0").stdout.strip()
        if last.startswith('v'):
            base = last[1:]
        else:
            base = last
    except subprocess.CalledProcessError:
        base = "0.1.0"
        last = ""
    level = detect_bump_level()
    next_ver = bump_version(base, level)
    tag_name = f"v{next_ver}"
    print(f"Last tag: {last or '(none)'}")
    print(f"Suggested bump: {level} -> {tag_name}")
    if ns.apply:
        msg = ns.message or f"Release {tag_name}"
        p = subprocess.run(["git", "tag", "-a", tag_name, "-m", msg])
        if p.returncode == 0:
            print(f"Created tag {tag_name}")
        return p.returncode
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gitta", description="Gitta — Git assistent")
    p.add_argument("-V", "--version", action="version", version=f"gitta {__version__}")

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("status", help="Show status with colored sections")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("graph", help="Show branch graph")
    sp.set_defaults(func=cmd_graph)

    sp = sub.add_parser("stage", help="Interactive staging")
    sp.add_argument("--files", nargs="*", help="Files to stage (skips interactive mode)")
    sp.set_defaults(func=cmd_stage)

    sp = sub.add_parser("commit", help="Skapa commit-meddelande från bullets och committa")
    sp.add_argument("-i", "--input", default=None, help="Inputfil (default: stdin eller $EDITOR)")
    sp.add_argument("-m", "--message", default=None, help="Använd given text som commit-subject/body (hoppa över editor)")
    sp.add_argument("--subject-max", type=int, default=SUBJECT_MAX, help="Max längd på subject")
    sp.add_argument("--wrap", type=int, default=BODY_WRAP, help="Bredd för body-wrap")
    sp.add_argument("--no-wrap", action="store_true", help="Inget auto-wrap i body (behåll radlängd)")
    sp.set_defaults(func=cmd_commit)

    sp = sub.add_parser("diff", help="Show diff")
    sp.add_argument("path", nargs="?", default=None, help="Optional path")
    sp.set_defaults(func=cmd_diff)

    sp = sub.add_parser("stash", help="Stash tools")
    sp_sub = sp.add_subparsers(dest="action", required=True)
    sp2 = sp_sub.add_parser("list", help="Lista stashes")
    sp2.set_defaults(func=cmd_stash)
    sp2 = sp_sub.add_parser("show", help="Visa stash patch")
    sp2.add_argument("index", type=int)
    sp2.set_defaults(func=cmd_stash)
    sp2 = sp_sub.add_parser("apply", help="Applicera stash")
    sp2.add_argument("index", type=int)
    sp2.set_defaults(func=cmd_stash)
    sp2 = sp_sub.add_parser("drop", help="Ta bort stash")
    sp2.add_argument("index", type=int)
    sp2.set_defaults(func=cmd_stash)

    sp = sub.add_parser("undo", help="Guided resets")
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--soft", action="store_true", help="Keep index and working directory (soft)")
    g.add_argument("--mixed", action="store_true", help="Keep working directory, reset index (mixed)")
    g.add_argument("--hard", action="store_true", help="Reset both index and working directory (hard)")
    sp.add_argument("target", nargs="?", default=None, help="Target ref, default HEAD~1")
    sp.set_defaults(func=cmd_undo)

    sp = sub.add_parser("tag", help="Versioning and tagging")
    sp_sub = sp.add_subparsers(dest="tcmd", required=True)
    sp2 = sp_sub.add_parser("bump", help="Suggest next semver from commits")
    sp2.add_argument("--apply", action="store_true", help="Create the tag")
    sp2.add_argument("-m", "--message", default=None, help="Tag message")
    sp2.set_defaults(func=cmd_tag)

    sp = sub.add_parser("tui", help="Starta TUI-gränssnittet (kräver 'textual')")
    sp.add_argument("--theme", choices=["dark", "light", "dracula"], default=None, help="Välj inbyggt tema")
    sp.add_argument("--css", default=None, help="Sökväg till egen CSS för TUI")
    sp.set_defaults(func=cmd_tui)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # legacy globals are only relevant for commit subcommand
    if hasattr(args, "subject_max"):
        global SUBJECT_MAX
        SUBJECT_MAX = args.subject_max
    if hasattr(args, "wrap"):
        global BODY_WRAP
        BODY_WRAP = args.wrap
    func = getattr(args, "func", None)
    if not func:
        parser.print_help()
        return 2
    return int(func(args))


def cmd_tui(ns: argparse.Namespace) -> int:
    try:
        from .tui.app import run as run_tui
    except Exception as e:
        sys.stderr.write(
            "TUI kräver paketet 'textual'. Installera t.ex. med:\n"
            "  pip install 'textual>=0.47,<0.60'\n"
            f"Detalj: {e}\n"
        )
        return 1
    return run_tui(theme=ns.theme, css_path=ns.css)
