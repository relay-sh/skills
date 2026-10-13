#!/usr/bin/env python3
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})[^`\n]*\n(.*?)(?:^[ \t]*\1[`~]*[ \t]*$|\Z)", re.M | re.S)
SPAN = re.compile(r"`([^`\n]+)`|<(?:code|pre)\b[^>]*>(.*?)</(?:code|pre)>", re.S)
INDENT = re.compile(r"^(?: {4}|\t)")
LIST = re.compile(r"^ {0,3}(?:[-*+]|\d+[.)])\s")
PATTERN = re.compile(r"^pattern:[ \t]*(['\"]?)(.*?)\1[ \t]*$", re.M)
COMMAND = re.compile(r"(?<![\w/.~-])(?:(?:\.{1,2}|~)?/(?:[\w.-]+/)*)?relay((?:[ \t]+\S+)+)")
SEPARATOR = re.compile(r"&&|\|\||[;|]|[ \t]#|[ \t]--[ \t]")
WORD = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
LONG = re.compile(r"^--([a-z][a-z0-9-]*)")
SHORT = re.compile(r"^-([A-Za-z])$")


def line_of(text, position):
    return text.count("\n", 0, position) + 1


def blank(match):
    return "\n" * match.group(0).count("\n")


def indented_blocks(text):
    blocks, lines, start, code, in_list, after_blank = [], [], 0, False, False, True
    for number, line in enumerate([*text.split("\n"), ""], 1):
        opens = bool(line.strip()) and bool(INDENT.match(line)) and (code or (after_blank and not in_list))
        if opens and not lines:
            start = number
        if opens:
            lines.append(line)
            code = True
        elif lines:
            blocks.append((start, "\n".join(lines)))
            lines = []
        if line.strip() and not INDENT.match(line):
            code = False
            leaves_list = after_blank and not line.startswith(" ")
            in_list = bool(LIST.match(line)) or (in_list and not leaves_list)
        after_blank = not line.strip()
    return blocks


def code_fragments(text):
    fragments = [(line_of(text, match.start(2)), match.group(2)) for match in FENCE.finditer(text)]
    prose = FENCE.sub(blank, text)
    fragments += indented_blocks(prose)
    return fragments + [(line_of(prose, match.start()), match.group(1) or match.group(2)) for match in SPAN.finditer(prose)]


def grader_fragments(text):
    fragments = [
        (line_of(text, match.start()), part) for match in PATTERN.finditer(text) for part in match.group(2).split("|")
    ]
    body = text.split("\n---\n", 1)[-1]
    return fragments + [(line + line_of(text, len(text) - len(body)) - 1, part) for line, part in code_fragments(body)]


def logical_lines(fragment):
    joined, start = "", 0
    for offset, line in enumerate(fragment.split("\n")):
        if not joined:
            start = offset
        joined += line
        if joined.endswith("\\"):
            joined = joined[:-1] + " "
            continue
        yield start, joined
        joined = ""


def flag_of(token, node):
    long, short = LONG.match(token), SHORT.match(token)
    if long:
        return f"--{long.group(1)}", long.group(1) if long.group(1) in node["flags"] else None
    if short:
        return token, node["shorts"].get(short.group(1))
    return None


def subcommand(token, path, commands):
    node = commands[" ".join(path)]
    return next(
        (sub for sub in node["subs"] if token == sub or token in commands[" ".join([*path, sub])]["aliases"]),
        None,
    )


def command_problems(tokens, commands):
    path, flags, stray, value, walking = [], [], "", False, True
    for token in tokens:
        node = commands[" ".join(path)]
        flag = flag_of(token, node)
        if value:
            value = False
        elif flag:
            name = flag[1]
            flags.append((token, name is not None))
            value = node["flags"].get(name, False) and "=" not in token
        elif walking:
            word = token.rstrip(".,:;")
            step = subcommand(word, path, commands)
            if step:
                path.append(step)
            else:
                walking, stray = False, word
    node = commands[" ".join(path)]
    shown = " ".join(["relay", *path])
    if node["subs"] and WORD.match(stray) and not stray.isupper():
        return [f"unknown command '{shown} {stray}'"]
    return [
        f"unknown flag '{flag_of(token, node)[0]}' for '{shown}'"
        for token, known in flags
        if not known and flag_of(token, node)[1] is None
    ]


def problems_in(fragment, commands):
    return [
        (offset, problem)
        for offset, line in logical_lines(fragment)
        for part in SEPARATOR.split(line)
        for match in COMMAND.finditer(part)
        for problem in command_problems(match.group(1).split(), commands)
    ]


def load(path):
    with open(path) as handle:
        document = json.load(handle)
    for node in document["commands"].values():
        node["flags"] = {**document["global_flags"], **node["flags"]}
        node["shorts"] = {**document["global_shorts"], **node["shorts"]}
    return document["commands"]


def scan(root, commands):
    plugin = os.path.join(root, "plugins", "relay")
    targets = [(path, code_fragments) for path in glob.glob(os.path.join(plugin, "skills", "*", "SKILL.md"))]
    targets += [(path, grader_fragments) for path in glob.glob(os.path.join(plugin, "evals", "*", "graders", "*.md"))]
    targets += [(path, code_fragments) for path in glob.glob(os.path.join(plugin, "evals", "*", "prompt.md"))]
    readme = os.path.join(root, "README.md")
    if os.path.exists(readme):
        targets.append((readme, code_fragments))
    found = set()
    for path, fragments in targets:
        with open(path) as handle:
            text = handle.read()
        for line, fragment in fragments(text):
            for offset, problem in problems_in(fragment, commands):
                found.add((os.path.relpath(path, root), line + offset, problem))
    return [f"check: {path}:{line}: {problem}" for path, line, problem in sorted(found)]


def main(argv):
    root = argv[1] if len(argv) > 1 else os.path.dirname(HERE)
    found = scan(root, load(os.path.join(HERE, "relay-commands.json")))
    for line in found:
        print(line, file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
