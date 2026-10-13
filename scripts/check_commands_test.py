#!/usr/bin/env python3
import contextlib
import io
import json
import os
import runpy
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_commands
import snapshot_commands


def node(subs=(), flags=(), shorts=None, aliases=()):
    return {
        "subs": list(subs),
        "flags": {"org": True, "help": False, **dict(flags)},
        "shorts": {"h": "help", **(shorts or {})},
        "aliases": list(aliases),
    }


COMMANDS = {
    "": node(["agents", "connect", "db", "help"], {"insecure": False}),
    "agents": node(["list", "pools"]),
    "agents list": node(flags={"output": True}, shorts={"o": "output"}),
    "agents pools": node(["create"]),
    "agents pools create": node(flags={"name": True}),
    "connect": node(flags={"port": True}),
    "db": node(["list"], aliases=["database"]),
    "db list": node(),
    "help": node(),
}

ROOT_HELP = """Database context manager

Usage:
  relay [command]

Available Commands:
  db          Provision and manage database clusters
  help        Help about any command
              with a wrapped description

Operator Commands:
  credential-sources Manage credential sources

Flags:
  -h, --help             help for relay
      --org string       override the active organization
                         --wrapped  description that looks like a flag
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
  -o, --output string   output format
      --wait string[="true"]   wait for the rows
      --name string

Global Flags:
      --org string   override the active organization
"""

LEAF_HELP = """A leaf command

Usage:
  relay leaf [flags]

Flags:
  -h, --help   help for leaf

Global Flags:
      --org string   override the active organization
"""

HELP = {"": ROOT_HELP, "db": DB_HELP, "db list": LIST_HELP, "help": LEAF_HELP, "credential-sources": LEAF_HELP}


def executable(directory, body):
    path = os.path.join(directory, "relay")
    with open(path, "w") as handle:
        handle.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


def fake_binary(directory):
    return executable(
        directory,
        f"#!/usr/bin/env python3\nimport sys\nHELP = {HELP!r}\nsys.stdout.write(HELP[' '.join(sys.argv[1:-1])])\n",
    )


def run_main(module, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = module.main(argv)
    return status, out.getvalue(), err.getvalue()


class ParseHelp(unittest.TestCase):
    def test_root_lists_commands_of_every_group_and_typed_flags(self):
        parsed = snapshot_commands.parse_help(ROOT_HELP)
        self.assertEqual(parsed["subs"], ["db", "help", "credential-sources"])
        self.assertEqual(parsed["flags"], {"help": False, "org": True, "insecure": False})
        self.assertEqual(parsed["shorts"], {"h": "help"})
        self.assertEqual(parsed["aliases"], [])

    def test_aliases_and_global_flags(self):
        parsed = snapshot_commands.parse_help(DB_HELP)
        self.assertEqual(parsed["aliases"], ["database"])
        self.assertEqual(parsed["flags"], {"help": False, "org": True})

    def test_aliases_header_on_the_last_line(self):
        self.assertEqual(snapshot_commands.parse_help("Aliases:")["aliases"], [])

    def test_flag_types_shorthands_and_undescribed_flags(self):
        parsed = snapshot_commands.parse_help(LIST_HELP)
        self.assertEqual(
            parsed["flags"], {"help": False, "limit": True, "output": True, "wait": True, "name": True, "org": True}
        )
        self.assertEqual(parsed["shorts"], {"h": "help", "o": "output"})


class Snapshot(unittest.TestCase):
    def test_walks_every_subcommand_with_the_given_home(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = executable(
                directory,
                "#!/usr/bin/env python3\nimport os, sys\n"
                f"HELP = {HELP!r}\n"
                "sys.stdout.write(HELP[' '.join(sys.argv[1:-1])] if os.environ['HOME'] == sys.argv[0] + '-home' else '')\n",
            )
            commands = snapshot_commands.snapshot(binary, binary + "-home")
        self.assertEqual(sorted(commands), ["", "credential-sources", "db", "db list", "help"])
        self.assertEqual(commands["db"]["subs"], ["list"])

    def test_hoist_moves_what_every_node_shares(self):
        commands = {
            "": {"flags": {"org": True, "insecure": False}},
            "db": {"flags": {"org": True, "insecure": True, "limit": True}},
        }
        self.assertEqual(snapshot_commands.hoist(commands, "flags"), {"org": True})
        self.assertEqual(commands[""]["flags"], {"insecure": False})
        self.assertEqual(commands["db"]["flags"], {"insecure": True, "limit": True})

    def test_main_writes_a_snapshot_the_checker_loads(self):
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "commands.json")
            status, _, _ = run_main(snapshot_commands, ["snapshot", fake_binary(directory), "cli abc", output])
            with open(output) as handle:
                written = json.load(handle)
            loaded = check_commands.load(output)
        self.assertEqual(status, 0)
        self.assertEqual(written["source"], "cli abc")
        self.assertEqual((written["global_flags"], written["global_shorts"]), ({"help": False, "org": True}, {"h": "help"}))
        self.assertEqual(written["commands"]["db list"]["flags"], {"limit": True, "output": True, "wait": True, "name": True})
        self.assertEqual(loaded["db list"]["flags"]["org"], True)
        self.assertEqual(loaded["db list"]["shorts"], {"h": "help", "o": "output"})

    def failing_main(self, binary_body):
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "commands.json")
            with open(output, "w") as handle:
                handle.write("kept")
            binary = executable(directory, binary_body) if binary_body else os.path.join(directory, "missing")
            status, _, err = run_main(snapshot_commands, ["snapshot", binary, "cli abc", output])
            with open(output) as handle:
                self.assertEqual(handle.read(), "kept")
        self.assertEqual(status, 1)
        return err

    def test_main_keeps_the_output_when_the_binary_lists_no_commands(self):
        self.assertIn("lists no commands", self.failing_main("#!/bin/sh\necho not a cobra binary\n"))

    def test_main_reports_the_stderr_of_a_failing_binary(self):
        err = self.failing_main("#!/bin/sh\necho broken build >&2\nexit 3\n")
        self.assertIn("exited 3: broken build", err)

    def test_main_reports_a_missing_binary(self):
        self.assertIn("No such file or directory", self.failing_main(None))

    def test_main_reports_a_binary_that_hangs(self):
        expired = subprocess.TimeoutExpired(["relay", "--help"], 30)
        with mock.patch.object(snapshot_commands.subprocess, "run", side_effect=expired):
            status, _, err = run_main(snapshot_commands, ["snapshot", "relay", "cli abc", os.devnull])
        self.assertEqual(status, 1)
        self.assertIn("timed out after 30 seconds", err)

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
    def test_fences_and_spans_carry_their_line(self):
        text = "Use `relay db list`.\n\n```bash\nrelay agents pools create \\\n  --name x\n```\n\nThe `relay` CLI.\n"
        self.assertEqual(
            check_commands.code_fragments(text),
            [(4, "relay agents pools create \\\n  --name x\n"), (1, "relay db list"), (8, "relay")],
        )

    def test_indented_and_tilde_fences_are_code(self):
        text = "1. Step\n\n   ```bash\n   relay db list\n   ```\n\n~~~\nrelay connect x\n~~~\n"
        self.assertEqual(check_commands.code_fragments(text), [(4, "   relay db list\n"), (8, "relay connect x\n")])

    def test_longer_fence_holds_a_shorter_one(self):
        text = "````md\n```bash\nrelay db list\n```\n````\n\n`relay connect x`\n"
        self.assertEqual(
            check_commands.code_fragments(text), [(2, "```bash\nrelay db list\n```\n"), (7, "relay connect x")]
        )

    def test_unterminated_fence_runs_to_the_end(self):
        self.assertEqual(check_commands.code_fragments("```\nrelay db list\n"), [(2, "relay db list\n")])

    def test_html_code_and_pre_elements_are_code(self):
        self.assertEqual(check_commands.code_fragments("Run <code>relay db list</code>.\n"), [(1, "relay db list")])
        self.assertEqual(
            check_commands.code_fragments('<code class="x">relay db list</code>\n\n<pre>\nrelay connect x\n</pre>\n'),
            [(1, "relay db list"), (3, "\nrelay connect x\n")],
        )

    def test_inline_triple_backticks_do_not_open_a_fence(self):
        text = "```relay db list``` is the command.\n\nThe relay agents are run by Relay.\n"
        self.assertEqual(check_commands.code_fragments(text), [(1, "relay db list")])

    def test_indented_block_after_a_blank_line_is_code(self):
        text = "Run this:\n\n    relay db list\n\n    relay connect x\nand then stop.\n"
        self.assertEqual(
            check_commands.code_fragments(text), [(3, "    relay db list"), (5, "    relay connect x")]
        )

    def test_indented_block_at_the_end_is_code(self):
        self.assertEqual(check_commands.code_fragments("Run:\n\n\trelay db list"), [(3, "\trelay db list")])

    def test_indented_text_in_a_paragraph_or_a_list_is_prose(self):
        text = "A paragraph\n    relay pools wraps here\n\n- item\n\n    relay pools continues the item\n"
        self.assertEqual(check_commands.code_fragments(text), [])

    def test_list_item_that_wraps_or_has_paragraphs_is_still_a_list(self):
        for item in ("- Run it and then\n  keep going\n", "1. First step\n   wraps here\n", "- a\n\n  second paragraph\n"):
            self.assertEqual(check_commands.code_fragments(f"{item}\n    the relay agents are run by Relay\n"), [])

    def test_list_ends_at_a_paragraph_after_a_blank_line(self):
        text = "- item\nlazy line\n\nA paragraph\n\n    relay db list\n"
        self.assertEqual(check_commands.code_fragments(text), [(6, "    relay db list")])

    def test_prose_outside_code_is_ignored(self):
        self.assertEqual(check_commands.code_fragments("relay pools is not a command\n"), [])

    def test_grader_pattern_is_split_on_alternation(self):
        text = "---\ntype: regex\npattern: 'relay db list|relay pools list'\n---\n"
        self.assertEqual(check_commands.grader_fragments(text), [(3, "relay db list"), (3, "relay pools list")])

    def test_grader_pattern_in_other_yaml_forms(self):
        for line in ('pattern: "relay db list"', "pattern: relay db list", "pattern:  'relay db list'  "):
            self.assertEqual(check_commands.grader_fragments(f"---\n{line}\n---\n"), [(2, "relay db list")])

    def test_rubric_grader_is_read_as_code_only(self):
        text = "---\ntype: llm\n---\n\nPASS if relay pools is avoided.\nFAIL on `relay pools list`.\n"
        self.assertEqual(check_commands.grader_fragments(text), [(6, "relay pools list")])


class ProblemsIn(unittest.TestCase):
    def check(self, fragment):
        return [problem for _, problem in check_commands.problems_in(fragment, COMMANDS)]

    def test_nested_command_with_flags_passes(self):
        self.assertEqual(self.check("relay agents pools create --name <pool>"), [])

    def test_alias_passes(self):
        self.assertEqual(self.check("relay database list"), [])

    def test_arguments_after_a_leaf_command_pass(self):
        self.assertEqual(self.check("relay connect pg-orders --port 5433"), [])
        self.assertEqual(self.check("relay help db"), [])

    def test_placeholder_or_regex_after_a_group_passes(self):
        self.assertEqual(self.check("relay db <command> --help"), [])
        self.assertEqual(self.check("relay agents (list|pools)"), [])
        self.assertEqual(self.check("relay db.*"), [])

    def test_bare_relay_passes(self):
        self.assertEqual(self.check("relay"), [])

    def test_unknown_top_level_command(self):
        self.assertEqual(self.check("relay pools list"), ["unknown command 'relay pools'"])

    def test_unknown_subcommand(self):
        self.assertEqual(self.check("relay agents delete-all"), ["unknown command 'relay agents delete-all'"])

    def test_unknown_subcommand_that_is_not_a_lowercase_word(self):
        self.assertEqual(self.check("relay db list2"), ["unknown command 'relay db list2'"])
        self.assertEqual(self.check("relay db List"), ["unknown command 'relay db List'"])
        self.assertEqual(self.check("relay db bogus_cmd"), ["unknown command 'relay db bogus_cmd'"])
        self.assertEqual(self.check("relay pools."), ["unknown command 'relay pools'"])

    def test_known_command_followed_by_punctuation_passes(self):
        self.assertEqual(self.check("relay db list, relay db list. relay database: relay agents pools;"), [])

    def test_uppercase_placeholder_after_a_group_passes(self):
        self.assertEqual(self.check("relay db ID"), [])
        self.assertEqual(self.check("relay COMMAND --help"), [])

    def test_unknown_flag(self):
        self.assertEqual(self.check("relay agents list --json"), ["unknown flag '--json' for 'relay agents list'"])

    def test_short_flags(self):
        self.assertEqual(self.check("relay agents list -o wide -h"), [])
        self.assertEqual(self.check("relay agents list -x"), ["unknown flag '-x' for 'relay agents list'"])
        self.assertEqual(self.check("relay db -x list"), ["unknown flag '-x' for 'relay db list'"])

    def test_global_flag_with_value_before_the_command(self):
        self.assertEqual(self.check("relay --org acme db list"), [])

    def test_global_flag_with_equals_and_boolean_flag(self):
        self.assertEqual(self.check("relay --org=acme --insecure db list"), [])

    def test_unknown_leading_flag(self):
        self.assertEqual(self.check("relay --bogus db list"), ["unknown flag '--bogus' for 'relay db list'"])

    def test_flag_between_a_group_and_its_subcommand(self):
        self.assertEqual(self.check("relay db --org acme list"), [])
        self.assertEqual(self.check("relay db --org acme bogus"), ["unknown command 'relay db bogus'"])
        self.assertEqual(self.check("relay db --org=acme --help"), [])

    def test_value_that_looks_like_a_flag_is_a_value(self):
        self.assertEqual(self.check("relay --org --bogus db list"), [])

    def test_flag_before_the_subcommand_that_defines_it_is_read_as_boolean(self):
        self.assertEqual(self.check("relay --insecure db list"), [])
        self.assertEqual(self.check("relay agents --output wide list"), ["unknown command 'relay agents wide'"])
        self.assertEqual(self.check("relay connect pg --port 5433 extra --bogus"), ["unknown flag '--bogus' for 'relay connect'"])

    def test_commands_chained_on_one_line_are_each_checked(self):
        self.assertEqual(
            self.check("relay db list && relay pools list; relay groups list | relay agents bogus"),
            ["unknown command 'relay pools'", "unknown command 'relay groups'", "unknown command 'relay agents bogus'"],
        )

    def test_flags_of_a_piped_or_wrapped_program_are_not_relay_flags(self):
        self.assertEqual(self.check("relay db list | grep --bogus x"), [])
        self.assertEqual(self.check("relay connect pg -- psql --bogus"), [])
        self.assertEqual(self.check("relay db list # --not-a-flag"), [])

    def test_relay_called_by_path_or_after_a_tab(self):
        for prefix in ("./", "../bin/", "/usr/local/bin/", "~/bin/"):
            self.assertEqual(self.check(f"{prefix}relay pools list"), ["unknown command 'relay pools'"])
        self.assertEqual(self.check("relay\tpools list"), ["unknown command 'relay pools'"])

    def test_path_segment_ending_in_relay_is_not_a_command(self):
        self.assertEqual(self.check('source = "relay-sh/relay" pools'), [])
        self.assertEqual(self.check("https://github.com/relay-sh/relay pools"), [])

    def test_every_command_is_reported_at_its_line(self):
        self.assertEqual(
            check_commands.problems_in("relay db list\nrelay pools list\nrelay agents list \\\n  --json\n", COMMANDS),
            [(1, "unknown command 'relay pools'"), (2, "unknown flag '--json' for 'relay agents list'")],
        )


class Scan(unittest.TestCase):
    def tree(self, directory, skill, grader=None, readme=None, prompt=None):
        plugin = os.path.join(directory, "plugins", "relay")
        case = os.path.join(plugin, "evals", "relay-x--a")
        os.makedirs(os.path.join(plugin, "skills", "relay-x"))
        os.makedirs(os.path.join(case, "graders"))
        files = {
            os.path.join(plugin, "skills", "relay-x", "SKILL.md"): skill,
            os.path.join(case, "graders", "g.md"): grader,
            os.path.join(case, "prompt.md"): prompt,
            os.path.join(directory, "README.md"): readme,
        }
        for path, text in files.items():
            if text is not None:
                with open(path, "w") as handle:
                    handle.write(text)
        return directory

    def test_clean_tree_has_no_problems(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.tree(directory, "Run `relay db list`.\n", "pattern: 'relay db list'\n", "`relay connect x`\n")
            self.assertEqual(check_commands.scan(root, COMMANDS), [])

    def test_reports_every_occurrence_with_its_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.tree(
                directory,
                "`relay pools list` and again `relay pools list`.\n\n```bash\nrelay db list\nrelay pools list\n```\n",
                "---\ntype: regex\npattern: 'relay groups create'\n---\n",
                "`relay db list --wide`\n",
                "I ran `relay groups list`.\n",
            )
            self.assertEqual(
                check_commands.scan(root, COMMANDS),
                [
                    "check: README.md:1: unknown flag '--wide' for 'relay db list'",
                    "check: plugins/relay/evals/relay-x--a/graders/g.md:3: unknown command 'relay groups'",
                    "check: plugins/relay/evals/relay-x--a/prompt.md:1: unknown command 'relay groups'",
                    "check: plugins/relay/skills/relay-x/SKILL.md:1: unknown command 'relay pools'",
                    "check: plugins/relay/skills/relay-x/SKILL.md:5: unknown command 'relay pools'",
                ],
            )

    def test_main_fails_and_prints_problems(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.tree(directory, "`relay nonexistent-command`\n")
            status, _, err = run_main(check_commands, ["check", root])
        self.assertEqual(status, 1)
        self.assertIn("SKILL.md:1: unknown command 'relay nonexistent-command'", err)

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
