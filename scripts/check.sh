#!/usr/bin/env bash
set -euo pipefail

root="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
plugin="$root/plugins/relay"
allowed=" name description license allowed-tools "
failed=0
expected=" "

fail() {
  echo "check: $1" >&2
  failed=1
}

frontmatter() {
  awk 'NR==1 && $0!="---" {exit} NR>1 && $0=="---" {exit} NR>1 {print}' "$1"
}

prompt_body() {
  awk 'NR==1 && $0=="---" {fm=1; next} fm && $0=="---" {fm=0; next} !fm {print}' "$1"
}

has_skill_grader() {
  local g
  for g in "$1"/*; do
    [ -f "$g" ] || continue
    if grep -qE '^type:[[:space:]]*tool_used[[:space:]]*$' "$g" \
      && grep -qE '^tool:[[:space:]]*Skill[[:space:]]*$' "$g" \
      && grep -qE "^input_match:.*$2\"" "$g"; then
      return 0
    fi
  done
  return 1
}

slug() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

check_skill() {
  local dir="$1" skill file fm key name title case_name line found=0
  skill="$(basename "$dir")"
  file="$dir/SKILL.md"

  if [ ! -f "$file" ]; then
    fail "$skill: missing SKILL.md"
    return
  fi
  case "$skill" in
    relay-*) ;;
    *) fail "$skill: directory name must start with relay-" ;;
  esac

  fm="$(frontmatter "$file")"
  if [ -z "$fm" ]; then
    fail "$skill: SKILL.md has no frontmatter"
    return
  fi
  for key in $(printf '%s\n' "$fm" | sed -nE 's/^([A-Za-z][A-Za-z0-9_-]*):.*/\1/p'); do
    case "$allowed" in
      *" $key "*) ;;
      *) fail "$skill: frontmatter key '$key' is not allowed" ;;
    esac
  done
  name="$(printf '%s\n' "$fm" | sed -nE 's/^name:[[:space:]]*//p')"
  if [ "$name" != "$skill" ]; then
    fail "$skill: frontmatter name '$name' differs from the directory name"
  fi
  if ! printf '%s\n' "$fm" | grep -qE '^description:[[:space:]]*[^[:space:]]'; then
    fail "$skill: description is missing"
  fi

  while IFS= read -r line; do
    fail "$skill: heading '$line' must be exactly '## Workflow: <title>'"
  done < <(grep -E '^#+ *[Ww]orkflow' "$file" | grep -vE '^## Workflow: [^ ]' || true)

  while IFS= read -r title; do
    found=1
    case_name="$skill--$(slug "$title")"
    case "$expected" in
      *" $case_name "*) fail "$skill: workflow '$title' repeats the eval case $case_name" ;;
    esac
    expected="$expected$case_name "
    if [ ! -f "$plugin/evals/$case_name/prompt.md" ]; then
      fail "$skill: workflow '$title' has no eval case at plugins/relay/evals/$case_name"
    else
      if ! prompt_body "$plugin/evals/$case_name/prompt.md" | grep -q '[^[:space:]]'; then
        fail "$case_name: prompt.md has no prompt text"
      fi
      if ! has_skill_grader "$plugin/evals/$case_name/graders" "$skill"; then
        fail "$case_name: no grader asserts that $skill was invoked"
      fi
    fi
  done < <(sed -nE 's/^## Workflow: //p' "$file")
  if [ "$found" = 0 ]; then
    fail "$skill: no '## Workflow: ' section"
  fi
}

if [ ! -d "$plugin/skills" ]; then
  echo "check: plugins/relay/skills not found under $root" >&2
  exit 1
fi

skills=0
for dir in "$plugin"/skills/*/; do
  [ -d "$dir" ] || continue
  skills=1
  check_skill "${dir%/}"
done
if [ "$skills" = 0 ]; then
  fail "no skills found under plugins/relay/skills"
fi

for dir in "$plugin"/evals/*/; do
  [ -f "$dir/prompt.md" ] || continue
  case_name="$(basename "$dir")"
  case "$expected" in
    *" $case_name "*) ;;
    *) fail "$case_name: eval case matches no '## Workflow: ' heading" ;;
  esac
done

if ! python3 "$(dirname "$0")/check_commands.py" "$root"; then
  failed=1
fi

if [ "$failed" = 1 ]; then
  exit 1
fi
echo "check: ok"
