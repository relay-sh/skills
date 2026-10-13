#!/usr/bin/env python3
import contextlib
import io
import json
import os
import runpy
import stat
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_commands
import snapshot_commands

COMMANDS = {
    "": {"subs": ["agents", "connect", "db"], "flags": {"org": True, "insecure": False, "help": False}, "aliases": []},
    "agents": {"subs": ["list", "pools"], "flags": {"org": True}, "aliases": []},
    "agents list": {"subs": [], "flags": {"org": True, "output": True}, "aliases": []},
    "agents pools": {"subs": ["create"], "flags": {"org": True}, "aliases": []},
    "agents pools create": {"subs": [], "flags": {"org": True, "name": True}, "aliases": []},
    "connect": {"subs": [], "flags": {"org": True, "port": True}, "aliases": []},
    "db": {"subs": ["list"], "flags": {"org": True, "help": False}, "aliases": ["database"]},
    "db list": {"subs": [], "flags": {"org": True}, "aliases": []},
}

ROOT_HELP = """Database context manager

Usage:
  relay [command]

Available Commands:
  completion  Generate the autocompletion script
  db          Provision and manage database clusters
  help        Help about any command

Flags:
  -h, --help             help for relay
      --org string       override the active organization
      --insecure         use plaintext gRPC

Use "relay [command] --help" for more information about a command.
"""

DB_HELP = """Provision and manage database clusters

Usage:
  relay db [command]

Aliases:
  db, database

Available Commands:
  list        List database clusters

Flags:
  -h, --help   help for db

Global Flags:
      --org string   override the active organization
"""

LIST_HELP = """List database clusters

Usage:
  relay db list [flags]

Flags:
  -h, --help          help for list
      --limit int32   max number of rows
      --wait string[="true"]   wait for the rows
      --name string

Global Flags:
      --org string   override the active organization
"""


def fake_binary(directory):
    path = os.path.join(directory, "relay")
    with open(path, "w") as handle:
        handle.write("#!/usr/bin/env python3\nimport sys\n")
        handle.write(f"HELP = {{'': {ROOT_HELP!r}, 'db': {DB_HELP!r}, 'db list': {LIST_HELP!r}}}\n")
        handle.write("sys.stdout.write(HELP[' '.join(sys.argv[1:-1])])\n")
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


def run_main(module, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = module.main(argv)
    return status, out.getvalue(), err.getvalue()


class ParseHelp(unittest.TestCase):
    def test_root_lists_commands_and_typed_flags(self):
        node = snapshot_commands.parse_help(ROOT_HELP)
        self.assertEqual(node["subs"], ["db"])
        self.assertEqual(node["flags"], {"help": False, "org": True, "insecure": False})
        self.assertEqual(node["aliases"], [])

    def test_aliases_and_global_flags(self):
        node = snapshot_commands.parse_help(DB_HELP)
        self.assertEqual(node["aliases"], ["database"])
        self.assertEqual(node["flags"], {"help": False, "org": True})

    def test_numeric_flag_type_takes_a_value(self):
        self.assertTrue(snapshot_commands.parse_help(LIST_HELP)["flags"]["limit"])

    def test_optional_value_and_undescribed_flags_are_kept(self):
        flags = snapshot_commands.parse_help(LIST_HELP)["flags"]
        self.assertEqual((flags["wait"], flags["name"]), (True, True))


class Snapshot(unittest.TestCase):
    def test_walks_every_subcommand(self):
        with tempfile.TemporaryDirectory() as directory:
            commands = snapshot_commands.snapshot(fake_binary(directory))
        self.assertEqual(sorted(commands), ["", "db", "db list"])
        self.assertEqual(commands["db"]["subs"], ["list"])

    def test_main_writes_json(self):
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "commands.json")
            status, _, _ = run_main(snapshot_commands, ["snapshot", fake_binary(directory), "cli abc", output])
            with open(output) as handle:
                written = json.load(handle)
        self.assertEqual(status, 0)
        self.assertEqual(written["source"], "cli abc")
        self.assertIn("db list", written["commands"])

    def test_main_keeps_the_output_when_the_binary_lists_no_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "commands.json")
            with open(output, "w") as handle:
                handle.write("kept")
            binary = os.path.join(directory, "relay")
            with open(binary, "w") as handle:
                handle.write("#!/bin/sh\necho not a cobra binary\n")
            os.chmod(binary, os.stat(binary).st_mode | stat.S_IXUSR)
            status, _, err = run_main(snapshot_commands, ["snapshot", binary, "cli abc", output])
            with open(output) as handle:
                kept = handle.read()
        self.assertEqual((status, kept), (1, "kept"))
        self.assertIn("lists no commands", err)

    def test_main_rejects_wrong_arguments(self):
        status, _, err = run_main(snapshot_commands, ["snapshot"])
        self.assertEqual(status, 2)
        self.assertIn("usage:", err)

    def test_runs_as_a_script(self):
        argv = sys.argv
        sys.argv = ["snapshot_commands.py"]
        try:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                runpy.run_path(os.path.join(HERE, "snapshot_commands.py"), run_name="__main__")
        finally:
            sys.argv = argv
        self.assertEqual(raised.exception.code, 2)


class Fragments(unittest.TestCase):
    def test_fence_joins_continuations_and_spans_exclude_fences(self):
        text = "Use `relay db list`.\n\n```bash\nrelay agents pools create \\\n  --name x\n```\n\nThe `relay` CLI.\n"
        self.assertEqual(
            check_commands.code_fragments(text),
            ["relay agents pools create    --name x\n", "relay db list", "relay"],
        )

    def test_indented_and_tilde_fences_are_code(self):
        text = "1. Step\n\n   ```bash\n   relay db list\n   ```\n\n~~~\nrelay connect x\n~~~\n"
        self.assertEqual(check_commands.code_fragments(text), ["   relay db list\n", "relay connect x\n"])

    def test_prose_outside_code_is_ignored(self):
        self.assertEqual(check_commands.code_fragments("relay pools is not a command\n"), [])

    def test_grader_pattern_is_split_on_alternation(self):
        text = "---\ntype: regex\npattern: 'relay db list|relay pools list'\n---\n"
        self.assertEqual(check_commands.grader_fragments(text), ["relay db list", "relay pools list"])

    def test_grader_without_pattern_has_no_fragments(self):
        self.assertEqual(check_commands.grader_fragments("---\ntype: llm\n---\n\nPASS if relay pools.\n"), [])


class ProblemsIn(unittest.TestCase):
    def check(self, fragment):
        return check_commands.problems_in(fragment, COMMANDS)

    def test_nested_command_with_flags_passes(self):
        self.assertEqual(self.check("relay agents pools create --name <pool>"), [])

    def test_alias_passes(self):
        self.assertEqual(self.check("relay database list"), [])

    def test_arguments_after_a_leaf_command_pass(self):
        self.assertEqual(self.check("relay connect pg-orders --port 5433"), [])

    def test_placeholder_after_a_group_passes(self):
        self.assertEqual(self.check("relay db <command> --help"), [])

    def test_bare_relay_passes(self):
        self.assertEqual(self.check("relay"), [])

    def test_unknown_top_level_command(self):
        self.assertEqual(self.check("relay pools list"), ["unknown command 'relay pools'"])

    def test_unknown_subcommand(self):
        self.assertEqual(self.check("relay agents delete-all"), ["unknown command 'relay agents delete-all'"])

    def test_unknown_flag(self):
        self.assertEqual(self.check("relay agents list --json"), ["unknown flag '--json' for 'relay agents list'"])

    def test_global_flag_with_value_before_the_command(self):
        self.assertEqual(self.check("relay --org acme db list"), [])

    def test_global_flag_with_equals_and_boolean_flag(self):
        self.assertEqual(self.check("relay --org=acme --insecure db list"), [])

    def test_unknown_leading_flag(self):
        self.assertEqual(self.check("relay --bogus db list"), ["unknown flag '--bogus' for 'relay'"])

    def test_flag_between_a_group_and_its_subcommand(self):
        self.assertEqual(self.check("relay db --org acme list"), [])
        self.assertEqual(self.check("relay db --org acme bogus"), ["unknown command 'relay db bogus'"])
        self.assertEqual(self.check("relay db --org=acme --help"), [])

    def test_commands_chained_on_one_line_are_each_checked(self):
        self.assertEqual(
            self.check("relay db list && relay pools list; relay groups list | relay agents bogus"),
            ["unknown command 'relay pools'", "unknown command 'relay groups'", "unknown command 'relay agents bogus'"],
        )

    def test_flags_of_a_piped_or_wrapped_program_are_not_relay_flags(self):
        self.assertEqual(self.check("relay db list | grep --bogus x"), [])
        self.assertEqual(self.check("relay connect pg -- psql --bogus"), [])
        self.assertEqual(self.check("relay db list # --not-a-flag"), [])

    def test_path_segment_ending_in_relay_is_not_a_command(self):
        self.assertEqual(self.check('source = "relay-sh/relay" pools'), [])

    def test_every_command_in_a_fragment_is_checked(self):
        self.assertEqual(
            self.check("relay db list\nrelay pools list\nrelay groups list"),
            ["unknown command 'relay pools'", "unknown command 'relay groups'"],
        )


class Scan(unittest.TestCase):
    def tree(self, directory, skill, grader=None, readme=None):
        plugin = os.path.join(directory, "plugins", "relay")
        os.makedirs(os.path.join(plugin, "skills", "relay-x"))
        with open(os.path.join(plugin, "skills", "relay-x", "SKILL.md"), "w") as handle:
            handle.write(skill)
        if grader is not None:
            os.makedirs(os.path.join(plugin, "evals", "relay-x--a", "graders"))
            with open(os.path.join(plugin, "evals", "relay-x--a", "graders", "g.md"), "w") as handle:
                handle.write(grader)
        if readme is not None:
            with open(os.path.join(directory, "README.md"), "w") as handle:
                handle.write(readme)
        return directory

    def test_clean_tree_has_no_problems(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.tree(directory, "Run `relay db list`.\n", "pattern: 'relay db list'\n", "`relay connect x`\n")
            self.assertEqual(check_commands.scan(root, COMMANDS), [])

    def test_reports_each_file_once_per_problem(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.tree(
                directory,
                "`relay pools list` and again `relay pools list`.\n",
                "pattern: 'relay groups create'\n",
                "`relay db list --wide`\n",
            )
            self.assertEqual(
                check_commands.scan(root, COMMANDS),
                [
                    "check: README.md: unknown flag '--wide' for 'relay db list'",
                    "check: plugins/relay/evals/relay-x--a/graders/g.md: unknown command 'relay groups'",
                    "check: plugins/relay/skills/relay-x/SKILL.md: unknown command 'relay pools'",
                ],
            )

    def test_main_fails_and_prints_problems(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.tree(directory, "`relay nonexistent-command`\n")
            status, _, err = run_main(check_commands, ["check", root])
        self.assertEqual(status, 1)
        self.assertIn("unknown command 'relay nonexistent-command'", err)

    def test_main_passes_on_this_repository(self):
        status, _, err = run_main(check_commands, ["check"])
        self.assertEqual((status, err), (0, ""))

    def test_runs_as_a_script(self):
        argv = sys.argv
        sys.argv = ["check_commands.py"]
        try:
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(os.path.join(HERE, "check_commands.py"), run_name="__main__")
        finally:
            sys.argv = argv
        self.assertEqual(raised.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
