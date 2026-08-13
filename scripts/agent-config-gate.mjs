#!/usr/bin/env node
/**
 * Agent-tooling config gate.
 *
 * `.claude/settings.json` was invalid JSON from PR #651 (2026-08-10) until it was
 * repaired: the added PreToolUse block was never closed. Claude Code parses that
 * file silently, so BOTH hooks it declares — the docs-history guard written to
 * stop the #590/#604 docs regressions, and the ultrareview advisor — were dead
 * for every session in between, and nothing said so. No CI job reads `.claude/`.
 * This is that missing reader.
 *
 * Three checks, each pinned to a failure that actually happened or is one typo away:
 *   1. every agent-tooling JSON config parses;
 *   2. every hook `command` points at a file that exists and is executable
 *      (a renamed script leaves the config valid and the hook silently dead);
 *   3. every `npx`-spawned MCP server in `.mcp.json` pins an exact version
 *      (an unpinned `npx -y pkg` executes whatever was published last).
 */

import { readFileSync, existsSync, accessSync, constants } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

const CONFIG_FILES = [
  '.mcp.json',
  '.claude/settings.json',
  '.claude-plugin/marketplace.json',
  'plugins/entropia-maintenance/.claude-plugin/plugin.json',
  'plugins/entropia-maintenance/hooks/hooks.json',
]

const PINNED_NPX = /^(@[a-z0-9-]+\/)?[a-z0-9._-]+@\d+\.\d+\.\d+/

const problems = []

function collectCommands(node, out) {
  if (Array.isArray(node)) {
    for (const item of node) collectCommands(item, out)
    return
  }
  if (node && typeof node === 'object') {
    for (const [key, value] of Object.entries(node)) {
      if (key === 'command' && typeof value === 'string') out.push(value)
      else collectCommands(value, out)
    }
  }
}

/** Resolve the hook-runtime variables Claude Code substitutes at call time. */
function resolveHookPath(raw, configFile) {
  const pluginRoot = configFile.startsWith('plugins/')
    ? path.join(REPO_ROOT, configFile.split('/').slice(0, 2).join('/'))
    : REPO_ROOT
  return raw
    .replace(/\$\{CLAUDE_PROJECT_DIR:-\.\}/g, REPO_ROOT)
    .replace(/\$\{CLAUDE_PROJECT_DIR\}/g, REPO_ROOT)
    .replace(/\$\{CLAUDE_PLUGIN_ROOT\}/g, pluginRoot)
}

/**
 * Every script path a hook command names. Variables are resolved first so that a
 * `bash -c '...'` wrapper (which hides the script behind a flag) is still covered.
 */
const SCRIPT_TOKEN = /[^\s"';|&$()]+\.(?:sh|py|mjs|js)\b/g

function hookScriptPaths(command, configFile) {
  const resolved = resolveHookPath(command, configFile)
  return [...new Set(resolved.match(SCRIPT_TOKEN) ?? [])].map((token) =>
    path.isAbsolute(token) ? token : path.join(REPO_ROOT, token),
  )
}

for (const configFile of CONFIG_FILES) {
  const absolute = path.join(REPO_ROOT, configFile)
  if (!existsSync(absolute)) {
    problems.push(`${configFile}: yok — CONFIG_FILES listesi bayat`)
    continue
  }

  let parsed
  try {
    parsed = JSON.parse(readFileSync(absolute, 'utf8'))
  } catch (error) {
    problems.push(`${configFile}: geçersiz JSON — ${error.message}`)
    continue
  }

  const commands = []
  collectCommands(parsed, commands)
  for (const command of commands) {
    for (const script of hookScriptPaths(command, configFile)) {
      if (!existsSync(script)) {
        problems.push(`${configFile}: hook betiği yok — ${path.relative(REPO_ROOT, script)}`)
        continue
      }
      try {
        accessSync(script, constants.X_OK)
      } catch {
        problems.push(`${configFile}: hook betiği çalıştırılabilir değil — ${path.relative(REPO_ROOT, script)}`)
      }
    }
  }

  if (configFile === '.mcp.json') {
    for (const [name, server] of Object.entries(parsed.mcpServers ?? {})) {
      if (server.command !== 'npx') continue
      const spec = (server.args ?? []).find((arg) => !arg.startsWith('-'))
      if (!spec || !PINNED_NPX.test(spec)) {
        problems.push(`.mcp.json: "${name}" sürüm pinlemiyor ("${spec ?? '?'}") — npx -y <pkg>@<x.y.z> yaz`)
      }
    }
  }

  // `enabledPlugins` names a plugin that Claude Code resolves through the
  // marketplace at session start, long after any typo would still be visible.
  // A name that does not exist here is silently ignored — the plugin's guard
  // hooks then never run and nothing says so.
  if (configFile === '.claude/settings.json') {
    const marketplace = JSON.parse(readFileSync(path.join(REPO_ROOT, '.claude-plugin/marketplace.json'), 'utf8'))
    const known = new Set((marketplace.plugins ?? []).map((plugin) => `${plugin.name}@${marketplace.name}`))
    for (const key of Object.keys(parsed.enabledPlugins ?? {})) {
      if (!key.endsWith(`@${marketplace.name}`)) continue
      if (!known.has(key)) {
        problems.push(
          `.claude/settings.json: enabledPlugins "${key}" bu deponun marketplace'inde yok — ` +
            `bilinen: ${[...known].join(', ') || '(hiç)'}`,
        )
      }
    }
  }
}

if (problems.length > 0) {
  process.stderr.write('agent config gate: ajan araç yapılandırması bozuk —\n')
  for (const problem of problems) process.stderr.write(`  - ${problem}\n`)
  process.exit(1)
}

process.stdout.write(
  `agent config gate: ${CONFIG_FILES.length} yapılandırma geçerli, hook betikleri yerinde, ` +
    'MCP sürümleri pinli, enabledPlugins çözülüyor ✓\n',
)
