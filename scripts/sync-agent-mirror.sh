#!/usr/bin/env bash
# Mirror the maintenance plugin's agents, skills and commands into `.claude/`.
#
# WHY THIS EXISTS. `.claude/settings.json` lists `entropia-maintenance` under
# `enabledPlugins`, but naming a plugin is not installing it: installation resolves
# through the marketplace and needs an approval prompt. A remote container is
# non-interactive, so `installed_plugins.json` stays empty there and NONE of the
# plugin's agents, skills or commands load. That is not a misconfiguration — it was
# measured in ADIM 58, which is why the two blocking guard hooks were registered
# directly in `.claude/settings.json` instead of being left to the plugin.
#
# The same reasoning applies to the rest of the machinery. `entropia-triage` and
# `entropia-scoped-fix` — the diagnose-then-fix pipeline — were written and then
# never loaded in any remote session, so every one of those sessions did the work by
# hand. `.claude/agents/` and `.claude/skills/` are discovered without installation,
# so mirroring the content there makes it actually reachable.
#
# Slash commands are mirrored for the same reason and by COPY, not by a pointer file.
# A pointer cannot carry them: `session-start.md` injects live git state through the
# `!`-prefixed form, which the harness expands in the command file it loads — a file
# that only says "read the plugin's copy" loses that expansion, and `$ARGUMENTS`
# interpolation with it. Copying is what preserves behaviour; the gate below is what
# keeps the copy honest.
#
# The plugin stays the source of truth; this only copies. `agent-config-gate.mjs`
# fails CI when a mirror diverges, because a silently stale agent definition is worse
# than a missing one: it loads and applies the wrong rule.
#
# Run after editing anything under `plugins/entropia-maintenance/agents`, `.../skills`
# or `.../commands`. Idempotent.
set -euo pipefail

cd "$(dirname "$0")/.."

plugin_agents="plugins/entropia-maintenance/agents"
plugin_skills="plugins/entropia-maintenance/skills"
plugin_commands="plugins/entropia-maintenance/commands"
copied=0

if [ -d "$plugin_agents" ]; then
  mkdir -p .claude/agents
  for source in "$plugin_agents"/*.md; do
    [ -e "$source" ] || continue
    target=".claude/agents/$(basename "$source")"
    if ! cmp -s "$source" "$target"; then
      cp "$source" "$target"
      echo "  agent  $(basename "$source")"
      copied=$((copied + 1))
    fi
  done
fi

if [ -d "$plugin_skills" ]; then
  for source_dir in "$plugin_skills"/*/; do
    [ -e "$source_dir/SKILL.md" ] || continue
    name="$(basename "$source_dir")"
    mkdir -p ".claude/skills/$name"
    target=".claude/skills/$name/SKILL.md"
    if ! cmp -s "$source_dir/SKILL.md" "$target"; then
      cp "$source_dir/SKILL.md" "$target"
      echo "  skill  $name"
      copied=$((copied + 1))
    fi
  done
fi

if [ -d "$plugin_commands" ]; then
  mkdir -p .claude/commands
  for source in "$plugin_commands"/*.md; do
    [ -e "$source" ] || continue
    target=".claude/commands/$(basename "$source")"
    if ! cmp -s "$source" "$target"; then
      cp "$source" "$target"
      echo "  command  $(basename "$source")"
      copied=$((copied + 1))
    fi
  done
fi

if [ "$copied" -eq 0 ]; then
  echo "agent mirror: already in sync"
else
  echo "agent mirror: $copied file(s) refreshed — commit them"
fi
