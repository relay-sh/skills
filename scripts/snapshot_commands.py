#!/usr/bin/env python3
import json
import re
import subprocess
import sys

SECTION = re.compile(r"^([A-Z][A-Za-z ]+):$")
FLAG = re.compile(r"^\s+(?:-\w, )?--([a-z0-9-]+)(?: ([a-zA-Z0-9]+))?\s{2,}")
SKIPPED = {"help", "completion"}


def parse_help(text):
    subs, flags, aliases, section = [], {}, [], None
    lines = text.splitlines()
    for index, line in enumerate(lines):
        header = SECTION.match(line)
        if header:
            section = header.group(1)
            if section == "Aliases":
                aliases = [alias.strip() for alias in lines[index + 1].split(",")][1:]
            continue
        if section in ("Available Commands", "Additional Commands") and line.startswith("  "):
            name = line.split()[0]
            if name not in SKIPPED:
                subs.append(name)
        elif section in ("Flags", "Global Flags"):
            flag = FLAG.match(line)
            if flag:
                flags[flag.group(1)] = flag.group(2) is not None
    return {"subs": subs, "flags": flags, "aliases": aliases}


def run_help(binary, path):
    return subprocess.run([binary, *path, "--help"], capture_output=True, text=True, check=True).stdout


def snapshot(binary, path=()):
    node = parse_help(run_help(binary, path))
    commands = {" ".join(path): node}
    for sub in node["subs"]:
        commands.update(snapshot(binary, (*path, sub)))
    return commands


def main(argv):
    if len(argv) != 3:
        print("usage: snapshot_commands.py <relay-binary> <source-label>", file=sys.stderr)
        return 2
    json.dump({"source": argv[2], "commands": snapshot(argv[1])}, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
