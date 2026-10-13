#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import tempfile

SECTION = re.compile(r"^([A-Z][A-Za-z ]+):$")
COMMAND = re.compile(r"^  ([a-z][\w-]*)(?: |$)")
FLAG = re.compile(r"^  (?:-(\w), | {4})--([a-z0-9-]+)(?: ([a-zA-Z0-9]+(?:\[[^\]]*\])?))?(?:\s{2,}|$)")
HOISTED = {"flags": "global_flags", "shorts": "global_shorts"}


def parse_help(text):
    subs, flags, shorts, aliases, section = [], {}, {}, [], ""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        header = SECTION.match(line)
        if header:
            section = header.group(1)
            if section == "Aliases":
                aliases = [alias.strip() for alias in lines[index + 1].split(",")][1:]
            continue
        command = COMMAND.match(line)
        flag = FLAG.match(line)
        if section.endswith("Commands") and command:
            subs.append(command.group(1))
        elif section.endswith("Flags") and flag:
            flags[flag.group(2)] = flag.group(3) is not None
            if flag.group(1):
                shorts[flag.group(1)] = flag.group(2)
    return {"subs": subs, "flags": flags, "shorts": shorts, "aliases": aliases}


def run_help(binary, path, home):
    return subprocess.run(
        [binary, *path, "--help"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
        env={**os.environ, "HOME": home},
    ).stdout


def snapshot(binary, home, path=()):
    node = parse_help(run_help(binary, path, home))
    commands = {" ".join(path): node}
    for sub in node["subs"]:
        commands.update(snapshot(binary, home, (*path, sub)))
    return commands


def hoist(commands, key):
    nodes = list(commands.values())
    shared = {name: value for name, value in nodes[0][key].items() if all(node[key].get(name) == value for node in nodes)}
    for node in nodes:
        node[key] = {name: value for name, value in node[key].items() if name not in shared}
    return shared


def main(argv):
    if len(argv) != 4:
        print("usage: snapshot_commands.py <relay-binary> <source-label> <output-file>", file=sys.stderr)
        return 2
    try:
        with tempfile.TemporaryDirectory() as home:
            commands = snapshot(argv[1], home)
    except subprocess.CalledProcessError as error:
        print(f"snapshot: {' '.join(error.cmd)} exited {error.returncode}: {error.stderr.strip()}", file=sys.stderr)
        return 1
    except (subprocess.TimeoutExpired, OSError) as error:
        print(f"snapshot: {error}", file=sys.stderr)
        return 1
    if not commands[""]["subs"]:
        print(f"snapshot: {argv[1]} --help lists no commands", file=sys.stderr)
        return 1
    document = {"source": argv[2], **{name: hoist(commands, key) for key, name in HOISTED.items()}, "commands": commands}
    with open(argv[3], "w") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
