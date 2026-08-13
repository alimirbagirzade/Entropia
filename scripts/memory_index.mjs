#!/usr/bin/env node
/**
 * Derived memory index — docs/PROJECT_HISTORY.md -> agentmemory.
 *
 * Rationale. CLAUDE.md's closing ritual asks for a memory checkpoint per slice.
 * That step failed three sessions in a row (ADIM 47/48/49) because the remote
 * container is ephemeral: whatever an agent writes into a container-local store
 * dies with the container. Writing checkpoints BY HAND into an ephemeral store
 * cannot be made reliable, so this script inverts the dependency — the single
 * source of truth stays the git-tracked history doc, and the memory store is a
 * DERIVED index over it, regenerable at will:
 *
 *     node scripts/memory_index.mjs --write        # rehydrate a fresh store
 *
 * Every emitted record names its own authority (the doc section it came from)
 * so a recall hit can never be mistaken for the canonical text. Records are
 * truncated at a char budget on purpose: this repo's history carries adjudicated
 * wording where a lost clause inverts the meaning (O-30's two key names, the
 * `ADIM 16 (sevk edilen)` / `ADIM 16 (ADR §12)` suffixes, the K-6a/K-6b split).
 * The index points AT that text, it does not replace it.
 *
 * Modes:
 *   --emit    print the derived records as JSON (deterministic, no network)
 *   --check   CI gate: every section indexed, ids unique and stable (no network)
 *   --write   push the records into agentmemory over the MCP stdio shim
 *
 * Flags:
 *   --only <substr>   restrict to records whose id contains <substr>
 *   --budget <n>      per-record char budget (default 6000)
 */

import { readFileSync } from 'node:fs'
import { spawn } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const SOURCE = 'docs/PROJECT_HISTORY.md'
const PROJECT = 'entropia'
const MCP_PACKAGE = '@agentmemory/mcp@0.9.28'

/**
 * `## Current position` inside the history doc is the OLD current-position block,
 * kept verbatim for the record. Indexing it would let a recall hit answer "where
 * are we now?" with a snapshot that was already stale when it was archived —
 * exactly the failure CLAUDE.md §Session START calls STALE-BY-DEFAULT. The live
 * answer lives in CLAUDE.md §Current position and docs/generated/repository_facts.md,
 * both of which are loaded or gated elsewhere.
 */
const EXCLUDED_HEADING_PREFIXES = ['Current position']

const TR_MAP = { ı: 'i', İ: 'i', ş: 's', Ş: 's', ğ: 'g', Ğ: 'g', ü: 'u', Ü: 'u', ö: 'o', Ö: 'o', ç: 'c', Ç: 'c' }

function slugify(text) {
  const folded = [...text].map((ch) => TR_MAP[ch] ?? ch).join('')
  return folded
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 72)
    .replace(/-+$/g, '')
}

const FILE_PATH_RE = /`([a-z0-9_.-]+(?:\/[A-Za-z0-9_.<>-]+)+\.(?:py|ts|tsx|mjs|js|sh|md|json|yml|yaml|css|html))/g

function parseSections(markdown) {
  const lines = markdown.split('\n')
  const sections = []
  let current = null
  lines.forEach((line, index) => {
    const match = /^##\s+(\S.*?)\s*$/.exec(line)
    if (match) {
      if (current) sections.push(current)
      current = { heading: match[1], line: index + 1, body: [] }
      return
    }
    if (current) current.body.push(line)
  })
  if (current) sections.push(current)
  return sections
}

function buildRecord(section, budget) {
  const body = section.body.join('\n').trim()
  const header = `[Entropia · ${SOURCE} §${section.heading}]`
  const pointer = `\n\n--- kanonik tam kayıt: ${SOURCE} §${section.heading} (satır ${section.line}) ---`
  const room = budget - header.length - pointer.length - 1
  const truncated = body.length > room
  const kept = truncated ? `${body.slice(0, room)}…` : body

  const prs = [...new Set([...section.heading.matchAll(/#(\d{2,4})\b/g), ...body.matchAll(/#(\d{2,4})\b/g)].map((m) => m[1]))]
  const files = [...new Set([...body.matchAll(FILE_PATH_RE)].map((m) => m[1]))].sort()
  const concepts = [...new Set(
    section.heading
      .split(/[—·:,()]/)
      .map((part) => part.trim())
      .filter((part) => part.length >= 3 && part.length <= 60),
  )]

  return {
    id: slugify(section.heading),
    heading: section.heading,
    line: section.line,
    prs,
    files: files.slice(0, 24),
    concepts,
    truncated,
    content: `${header}\n${kept}${pointer}`,
  }
}

function deriveRecords({ budget }) {
  const markdown = readFileSync(path.join(REPO_ROOT, SOURCE), 'utf8')
  return parseSections(markdown)
    .filter((section) => !EXCLUDED_HEADING_PREFIXES.some((prefix) => section.heading.startsWith(prefix)))
    .map((section) => buildRecord(section, budget))
}

function check(records) {
  const problems = []
  const seen = new Map()
  for (const record of records) {
    if (!record.id) problems.push(`bosh id türedi: "${record.heading}" (satır ${record.line})`)
    if (seen.has(record.id)) {
      // CLAUDE.md: slice numbers are never reassigned; two records that carry the
      // same number are told apart by a title suffix. A collision here means that
      // suffix is missing, and a recall hit would be ambiguous.
      problems.push(
        `id çakışması "${record.id}": "${seen.get(record.id)}" ↔ "${record.heading}" — ` +
          'başlığa ayırt edici ek koy (CLAUDE.md: numaralar yeniden atanmaz)',
      )
    }
    seen.set(record.id, record.heading)
    if (record.content.trim().length < 80) problems.push(`gövdesi boş kayıt: "${record.heading}" (satır ${record.line})`)
  }
  return problems
}

function rpc(child, id, method, params) {
  child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', id, method, params })}\n`)
}

async function write(records) {
  const child = spawn('npx', ['-y', MCP_PACKAGE], { stdio: ['pipe', 'pipe', 'inherit'] })
  const pending = new Map()
  let buffer = ''

  child.stdout.on('data', (chunk) => {
    buffer += chunk
    let newline
    while ((newline = buffer.indexOf('\n')) !== -1) {
      const line = buffer.slice(0, newline).trim()
      buffer = buffer.slice(newline + 1)
      if (!line) continue
      let message
      try {
        message = JSON.parse(line)
      } catch {
        continue
      }
      const resolve = pending.get(message.id)
      if (resolve) {
        pending.delete(message.id)
        resolve(message)
      }
    }
  })

  let nextId = 0
  const call = (method, params) =>
    new Promise((resolve, reject) => {
      const id = ++nextId
      pending.set(id, resolve)
      setTimeout(() => pending.has(id) && (pending.delete(id), reject(new Error(`${method} zaman aşımı`))), 120_000)
      rpc(child, id, method, params)
    })

  const init = await call('initialize', {
    protocolVersion: '2024-11-05',
    capabilities: {},
    clientInfo: { name: 'entropia-memory-index', version: '1' },
  })
  if (init.error) throw new Error(`initialize başarısız: ${JSON.stringify(init.error)}`)
  child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' })}\n`)

  let written = 0
  for (const record of records) {
    const response = await call('tools/call', {
      name: 'memory_save',
      arguments: {
        content: record.content,
        type: 'architecture',
        project: PROJECT,
        concepts: record.concepts.join(','),
        files: record.files.join(','),
      },
    })
    if (response.error || response.result?.isError) {
      throw new Error(`memory_save başarısız (${record.id}): ${JSON.stringify(response.error ?? response.result)}`)
    }
    written += 1
    process.stderr.write(`  saved ${record.id}\n`)
  }

  child.stdin.end()
  child.kill()
  return written
}

async function main() {
  const argv = process.argv.slice(2)
  const mode = argv.find((arg) => ['--emit', '--check', '--write'].includes(arg))
  if (!mode) {
    process.stderr.write('kullanım: node scripts/memory_index.mjs <--emit|--check|--write> [--only <substr>] [--budget <n>]\n')
    return 2
  }
  const only = argv.includes('--only') ? argv[argv.indexOf('--only') + 1] : null
  const budget = argv.includes('--budget') ? Number(argv[argv.indexOf('--budget') + 1]) : 6000

  const all = deriveRecords({ budget })
  const problems = check(all)
  if (problems.length > 0) {
    process.stderr.write(`memory index gate: ${SOURCE} indekslenemiyor —\n`)
    for (const problem of problems) process.stderr.write(`  - ${problem}\n`)
    return 1
  }

  const records = only ? all.filter((record) => record.id.includes(only)) : all
  if (only && records.length === 0) {
    process.stderr.write(`--only "${only}" hiçbir kayıtla eşleşmedi\n`)
    return 1
  }

  if (mode === '--check') {
    process.stdout.write(`memory index gate: ${all.length} kayıt, id'ler tekil, gövdeler dolu ✓\n`)
    return 0
  }
  if (mode === '--emit') {
    process.stdout.write(`${JSON.stringify(records, null, 2)}\n`)
    return 0
  }

  const written = await write(records)
  process.stdout.write(`agentmemory: ${written} kayıt yazıldı (kaynak ${SOURCE})\n`)
  return 0
}

main().then(
  (code) => process.exit(code),
  (error) => {
    process.stderr.write(`${error.message}\n`)
    process.exit(1)
  },
)
