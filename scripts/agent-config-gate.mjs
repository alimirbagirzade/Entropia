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

import { readFileSync, readdirSync, existsSync, accessSync, constants } from 'node:fs'
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
/** `npx [-y|--yes] <spec>` inside a launcher script; the spec may be a variable. */
const NPX_INVOCATION = /\bnpx\s+(?:-y\s+|--yes\s+)?(\S+)/g
const SHELL_ASSIGNMENT = /^\s*([A-Za-z_][A-Za-z0-9_]*)=["']?([^"'\n]+?)["']?\s*$/gm

/** Resolve `"$PKG"` / `${PKG}` against the script's own literal assignments. */
function resolveSpec(token, scriptText) {
  const bare = token.replace(/^["']|["']$/g, '')
  const variable = /^\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?$/.exec(bare)
  if (!variable) return bare
  for (const [, name, value] of scriptText.matchAll(SHELL_ASSIGNMENT)) {
    if (name === variable[1]) return value.replace(/^["']|["']$/g, '')
  }
  return bare
}

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

/**
 * Repo-relative script references inside a launcher's own text.
 *
 * SCRIPT_TOKEN cannot be reused here: it stops at `$`, so `"$ROOT/scripts/x.sh"`
 * comes back as the non-existent `ROOT/scripts/x.sh` and the chain is silently
 * dropped — which is exactly how the first version of this gate passed its own
 * negative control. Anchoring on the repo's directory names instead survives any
 * variable prefix.
 */
const REPO_SCRIPT_REF = /((?:scripts|\.claude\/hooks)\/[A-Za-z0-9._-]+\.(?:sh|mjs|js|py))\b/g

/** `npx` in command position — not the word "npx" inside a comment or a message. */
function npxSpecs(text) {
  const specs = []
  for (const line of text.split('\n')) {
    const trimmed = line.trim()
    if (trimmed.startsWith('#') || trimmed.includes('echo ') || trimmed.includes('command -v')) continue
    for (const [, token] of line.matchAll(NPX_INVOCATION)) specs.push(resolveSpec(token, text))
  }
  return specs
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
      if (server.command === 'npx') {
        const spec = (server.args ?? []).find((arg) => !arg.startsWith('-'))
        if (!spec || !PINNED_NPX.test(spec)) {
          problems.push(`.mcp.json: "${name}" sürüm pinlemiyor ("${spec ?? '?'}") — npx -y <pkg>@<x.y.z> yaz`)
        }
        continue
      }

      // A server launched through a repo script would otherwise escape the pin
      // rule entirely: the `npx` call moves inside the script, where the check
      // above cannot see it. Follow it in.
      // A launcher may delegate to another launcher (memory_mcp.sh -> memory_server.sh),
      // so follow every script path the command mentions and every script those name.
      const queue = hookScriptPaths(server.command, configFile)
      const visited = new Set()
      while (queue.length > 0) {
        const script = queue.shift()
        if (visited.has(script)) continue
        visited.add(script)
        if (!existsSync(script)) {
          problems.push(`${path.relative(REPO_ROOT, script)}: "${name}" sunucusunun çağırdığı betik yok`)
          continue
        }
        const text = readFileSync(script, 'utf8')
        for (const [, reference] of text.matchAll(REPO_SCRIPT_REF)) queue.push(path.join(REPO_ROOT, reference))
        for (const spec of npxSpecs(text)) {
          if (!PINNED_NPX.test(spec)) {
            problems.push(
              `${path.relative(REPO_ROOT, script)}: "${name}" sunucusu pinsiz npx çağırıyor ("${spec}") — <pkg>@<x.y.z> yaz`,
            )
          }
        }
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

// 5. Plugin ajan/skill'lerinin `.claude/` aynası taze mi.
//
// `enabledPlugins` bir plugin'i ADLANDIRIR ama KURMAZ: kurulum bir onay istemi
// ister ve remote container etkileşimsizdir, o yüzden `installed_plugins.json`
// orada boş kalır (ADIM 58'de ölçüldü). Sonucu şuydu: `entropia-triage` ve
// `entropia-scoped-fix` remote'ta HİÇ yüklenmedi — teşhis/düzeltme makinesi
// yazılmıştı ve her oturum onsuz, elle yürüdü. `.claude/agents/` ve
// `.claude/skills/` ise kurulum istemeden yüklenir, o yüzden plugin içeriği
// oraya AYNALANIR (ADIM 58'in hook'lar için yaptığının aynısı: kaynak plugin'de
// kalır, erişilebilirlik ikinci bir kayıtla sağlanır).
//
// Ayna bir KOPYA olduğu için sapabilir — ve sessizce sapan bir ajan tanımı,
// hiç yüklenmemiş olandan daha kötüdür: yüklenir ve YANLIŞ kuralı uygular.
// Bu yüzden eşitlik bir kapıdır. Plugin'i düzenlediysen aynayı da güncelle
// (`scripts/sync-agent-mirror.sh`), tersi de geçerli.
const MIRRORED = [
  ['plugins/entropia-maintenance/agents', '.claude/agents', (name) => name],
  ['plugins/entropia-maintenance/skills', '.claude/skills', (name) => path.join(name, 'SKILL.md')],
]

for (const [sourceDir, mirrorDir, toRelative] of MIRRORED) {
  const sourceRoot = path.join(REPO_ROOT, sourceDir)
  if (!existsSync(sourceRoot)) continue
  const isSkillTree = mirrorDir.endsWith('skills')
  const entries = readdirSync(sourceRoot, { withFileTypes: true })
    .filter((entry) => (isSkillTree ? entry.isDirectory() : entry.name.endsWith('.md')))
    .map((entry) => entry.name)

  for (const name of entries) {
    const relative = toRelative(name)
    const sourcePath = path.join(sourceDir, isSkillTree ? path.join(name, 'SKILL.md') : name)
    const mirrorPath = path.join(mirrorDir, relative)
    if (!existsSync(path.join(REPO_ROOT, sourcePath))) continue
    if (!existsSync(path.join(REPO_ROOT, mirrorPath))) {
      problems.push(
        `${mirrorPath}: yok — ${sourcePath} plugin'de tanımlı ama aynalanmamış, ` +
          'yani plugin kurulmayan bir oturumda (remote container: her zaman) hiç yüklenmez',
      )
      continue
    }
    const sourceText = readFileSync(path.join(REPO_ROOT, sourcePath), 'utf8')
    const mirrorText = readFileSync(path.join(REPO_ROOT, mirrorPath), 'utf8')
    if (sourceText !== mirrorText) {
      problems.push(
        `${mirrorPath}: ${sourcePath} ile AYRIŞMIŞ — ayna sessizce eski kuralı uygular; ` +
          'scripts/sync-agent-mirror.sh ile eşitle',
      )
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
    'MCP sürümleri pinli, enabledPlugins çözülüyor, plugin ajan/skill aynası taze ✓\n',
)
