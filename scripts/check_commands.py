#!/usr/bin/env python3
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FENCE = re.compile(r"^[ \t]*(?:```|~~~)[^\n]*\n(.*?)^[ \t]*(?:```|~~~)", re.M | re.S)
SPAN = re.compile(r"`([^`\n]+)`")
PATTERN = re.compile(r"^pattern: '(.*)'$", re.M)
COMMAND = re.compile(r"(?<![\w/.-])relay((?: +\S+)+)")
SEPARATOR = re.compile(r"&&|\|\||[;|]| #| -- ")
WORD = re.compile(r"^[a-z][a-z-]*$")
FLAG = re.compile(r"^--([a-z][a-z0-9-]*)")


def code_fragments(text):
    fragments = [block.replace("\\\n", " ") for block in FENCE.findall(text)]
    return fragments + SPAN.findall(FENCE.sub("", text))


def grader_fragments(text):
    return [part for pattern in PATTERN.findall(text) for part in pattern.split("|")]


def problems_in(fragment, commands):
    found = []
    for match in (found for part in SEPARATOR.split(fragment) for found in COMMAND.finditer(part)):
        tokens = match.group(1).split()
        root = commands[""]
        while tokens and FLAG.match(tokens[0]):
            name = FLAG.match(tokens[0]).group(1)
            if name not in root["flags"]:
                found.append(f"unknown flag '--{name}' for 'relay'")
            takes_value = root["flags"].get(name, False) and "=" not in tokens[0]
            tokens = tokens[2:] if takes_value else tokens[1:]
        path, rest, value = [], [], False
        for index, token in enumerate(tokens):
            node = commands[" ".join(path)]
            flag = FLAG.match(token)
            if value or flag:
                value = bool(flag) and node["flags"].get(flag.group(1), False) and "=" not in token
                rest.append(token)
                continue
            step = next(
                (sub for sub in node["subs"] if token == sub or token in commands[" ".join([*path, sub])]["aliases"]),
                None,
            )
            if step is None:
                rest += tokens[index:]
                break
            path.append(step)
        node = commands[" ".join(path)]
        stray = tokens[index] if tokens and step is None else ""
        shown = " ".join(["relay", *path])
        if node["subs"] and WORD.match(stray):
            found.append(f"unknown command '{shown} {stray}'")
            continue
        for token in rest:
            flag = FLAG.match(token)
            if flag and flag.group(1) not in node["flags"]:
                found.append(f"unknown flag '--{flag.group(1)}' for '{shown}'")
    return found


def scan(root, commands):
    plugin = os.path.join(root, "plugins", "relay")
    targets = [(path, code_fragments) for path in glob.glob(os.path.join(plugin, "skills", "*", "SKILL.md"))]
    targets += [(path, grader_fragments) for path in glob.glob(os.path.join(plugin, "evals", "*", "graders", "*.md"))]
    readme = os.path.join(root, "README.md")
    if os.path.exists(readme):
        targets.append((readme, code_fragments))
    found = set()
    for path, fragments in targets:
        with open(path) as handle:
            text = handle.read()
        for fragment in fragments(text):
            for problem in problems_in(fragment, commands):
                found.add(f"check: {os.path.relpath(path, root)}: {problem}")
    return sorted(found)


def main(argv):
    root = argv[1] if len(argv) > 1 else os.path.dirname(HERE)
    with open(os.path.join(HERE, "relay-commands.json")) as handle:
        commands = json.load(handle)["commands"]
    found = scan(root, commands)
    for line in found:
        print(line, file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
