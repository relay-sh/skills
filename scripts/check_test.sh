#!/usr/bin/env bash
set -euo pipefail

check="$(cd "$(dirname "$0")" && pwd)/check.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
failures=0

valid_tree() {
  local root="$1" skill="${2:-relay-setup}"
  mkdir -p "$root/plugins/relay/skills/$skill" "$root/plugins/relay/evals/$skill--install-the-cli/graders"
  printf -- '---\nname: %s\ndescription: Install the Relay CLI.\nlicense: MPL-2.0\n---\n\n## Workflow: Install the CLI\n' "$skill" \
    > "$root/plugins/relay/skills/$skill/SKILL.md"
  printf -- '---\nmax_turns: 10\n---\n\nInstall the Relay CLI.\n' \
    > "$root/plugins/relay/evals/$skill--install-the-cli/prompt.md"
  printf -- "---\ntype: tool_used\ntool: Skill\ninput_match: '\"skill\"\\\\s*:\\\\s*\"(?:[\\\\w-]+:)?%s\"'\n---\n" "$skill" \
    > "$root/plugins/relay/evals/$skill--install-the-cli/graders/skill-fired.md"
}

expect() {
  local label="$1" want_status="$2" want_text="$3" root="$4" out status=0
  out="$("$check" "$root" 2>&1)" || status=$?
  if [ "$status" != "$want_status" ] || ! printf '%s' "$out" | grep -qF -- "$want_text"; then
    echo "FAIL $label: status=$status output=$out"
    failures=$((failures + 1))
  else
    echo "ok   $label"
  fi
}

skill_md="plugins/relay/skills/relay-setup/SKILL.md"
case_dir="plugins/relay/evals/relay-setup--install-the-cli"

r="$tmp/valid"; valid_tree "$r"
expect "valid tree passes" 0 "check: ok" "$r"

r="$tmp/no-skills-dir"; mkdir -p "$r"
expect "missing skills directory" 1 "plugins/relay/skills not found" "$r"

r="$tmp/empty"; mkdir -p "$r/plugins/relay/skills"
expect "no skills" 1 "no skills found" "$r"

r="$tmp/no-skill-md"; valid_tree "$r"; rm "$r/$skill_md"
expect "missing SKILL.md" 1 "relay-setup: missing SKILL.md" "$r"

r="$tmp/prefix"; valid_tree "$r" setup
expect "name without relay- prefix" 1 "setup: directory name must start with relay-" "$r"

r="$tmp/no-frontmatter"; valid_tree "$r"; printf '# Relay setup\n\n## Workflow: Install the CLI\n' > "$r/$skill_md"
expect "no frontmatter" 1 "relay-setup: SKILL.md has no frontmatter" "$r"

r="$tmp/bad-key"; valid_tree "$r"
printf -- '---\nname: relay-setup\ndescription: Install.\nmodel: opus\n---\n\n## Workflow: Install the CLI\n' > "$r/$skill_md"
expect "disallowed frontmatter key" 1 "frontmatter key 'model' is not allowed" "$r"

r="$tmp/name"; valid_tree "$r"
printf -- '---\nname: relay-other\ndescription: Install.\n---\n\n## Workflow: Install the CLI\n' > "$r/$skill_md"
expect "name differs from directory" 1 "frontmatter name 'relay-other' differs from the directory name" "$r"

r="$tmp/description"; valid_tree "$r"
printf -- '---\nname: relay-setup\n---\n\n## Workflow: Install the CLI\n' > "$r/$skill_md"
expect "missing description" 1 "relay-setup: description is missing" "$r"

r="$tmp/folded"; valid_tree "$r"
printf -- '---\nname: relay-setup\ndescription: >-\n  Install the Relay CLI.\n  Second line.\n---\n\n## Workflow: Install the CLI\n' > "$r/$skill_md"
expect "folded description passes" 0 "check: ok" "$r"

r="$tmp/no-workflow"; valid_tree "$r"; rm -r "${r:?}/$case_dir"
printf -- '---\nname: relay-setup\ndescription: Install.\n---\n\n## Install\n' > "$r/$skill_md"
expect "no workflow section" 1 "relay-setup: no '## Workflow: ' section" "$r"

r="$tmp/no-case"; valid_tree "$r"; rm -r "${r:?}/$case_dir"
expect "workflow without eval case" 1 "workflow 'Install the CLI' has no eval case at $case_dir" "$r"

r="$tmp/no-grader"; valid_tree "$r"; rm "$r/$case_dir/graders/skill-fired.md"
expect "case without skill grader" 1 "relay-setup--install-the-cli: no grader asserts that relay-setup was invoked" "$r"

r="$tmp/orphan"; valid_tree "$r"; cp -R "$r/$case_dir" "$r/plugins/relay/evals/relay-setup--gone"
expect "eval case without workflow" 1 "relay-setup--gone: eval case matches no '## Workflow: ' heading" "$r"

r="$tmp/results"; valid_tree "$r"; mkdir -p "$r/plugins/relay/evals/results/2026"
expect "results directory is ignored" 0 "check: ok" "$r"

r="$tmp/slug"; valid_tree "$r"
printf -- '---\nname: relay-setup\ndescription: Install.\n---\n\n## Workflow: Sign in (SSO & device)\n' > "$r/$skill_md"
expect "title is slugged" 1 "no eval case at plugins/relay/evals/relay-setup--sign-in-sso-device" "$r"

for bad in '### Workflow: Install the CLI' '##  Workflow: Install the CLI' '## workflow: Install the CLI' '## Workflow - Install the CLI' '## Workflow:  Install the CLI'; do
  r="$tmp/heading"; rm -rf "$r"; valid_tree "$r"
  printf -- '---\nname: relay-setup\ndescription: Install.\n---\n\n## Workflow: Install the CLI\n\n%s\n' "$bad" > "$r/$skill_md"
  expect "malformed heading '$bad'" 1 "relay-setup: heading '$bad' must be exactly '## Workflow: <title>'" "$r"
done

r="$tmp/duplicate"; valid_tree "$r"
printf -- '---\nname: relay-setup\ndescription: Install.\n---\n\n## Workflow: Install the CLI\n\n## Workflow: Install the CLI!\n' > "$r/$skill_md"
expect "duplicate case name" 1 "relay-setup: workflow 'Install the CLI!' repeats the eval case relay-setup--install-the-cli" "$r"

r="$tmp/grader-prefix"; valid_tree "$r"
printf -- "---\ntype: tool_used\ntool: Skill\ninput_match: '\"skill\"\\\\s*:\\\\s*\"relay-setup-extra\"'\n---\n" > "$r/$case_dir/graders/skill-fired.md"
expect "grader for a longer skill name" 1 "relay-setup--install-the-cli: no grader asserts that relay-setup was invoked" "$r"

r="$tmp/grader-type"; valid_tree "$r"
printf -- "---\ntype: output_match\ntool: Skill\ninput_match: 'relay-setup\"'\n---\n" > "$r/$case_dir/graders/skill-fired.md"
expect "grader without tool_used" 1 "relay-setup--install-the-cli: no grader asserts that relay-setup was invoked" "$r"

r="$tmp/grader-tool"; valid_tree "$r"
printf -- "---\ntype: tool_used\ntool: Read\ninput_match: 'relay-setup\"'\n---\n" > "$r/$case_dir/graders/skill-fired.md"
expect "grader for another tool" 1 "relay-setup--install-the-cli: no grader asserts that relay-setup was invoked" "$r"

r="$tmp/grader-split"; valid_tree "$r"
printf -- "---\ntype: tool_used\ntool: Skill\n---\n" > "$r/$case_dir/graders/skill-fired.md"
printf -- "---\ninput_match: 'relay-setup\"'\n---\n" > "$r/$case_dir/graders/other.md"
expect "grader fields split across files" 1 "relay-setup--install-the-cli: no grader asserts that relay-setup was invoked" "$r"

r="$tmp/empty-prompt"; valid_tree "$r"; printf -- '---\nmax_turns: 10\n---\n\n  \n\n' > "$r/$case_dir/prompt.md"
expect "empty prompt body" 1 "relay-setup--install-the-cli: prompt.md has no prompt text" "$r"

r="$tmp/empty-prompt-bare"; valid_tree "$r"; printf -- '\n \n' > "$r/$case_dir/prompt.md"
expect "whitespace-only prompt without frontmatter" 1 "relay-setup--install-the-cli: prompt.md has no prompt text" "$r"

r="$tmp/unknown-command"; valid_tree "$r"
printf -- '---\nname: relay-setup\ndescription: Install.\n---\n\n## Workflow: Install the CLI\n\nRun \140relay pools list\140.\n' > "$r/$skill_md"
expect "command that the CLI does not have" 1 "relay-setup/SKILL.md: unknown command 'relay pools'" "$r"

r="$tmp/known-command"; valid_tree "$r"
printf -- '---\nname: relay-setup\ndescription: Install.\n---\n\n## Workflow: Install the CLI\n\nRun \140relay agents pools list\140.\n' > "$r/$skill_md"
expect "command that the CLI has" 0 "check: ok" "$r"

if out=$(python3 "$(dirname "$check")/check_commands_test.py" 2>&1); then
  echo "ok   command check unit tests"
else
  echo "FAIL command check unit tests"
  echo "$out"
  failures=$((failures + 1))
fi

if [ "$failures" != 0 ]; then
  echo "$failures failed"
  exit 1
fi
echo "all passed"
