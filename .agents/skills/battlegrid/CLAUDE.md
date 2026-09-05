# CLAUDE.md

Maintainer instructions for `@battlegrid/mcp-server` — a **thin stdio proxy** to BattleGrid's remote
MCP server.

Not to be confused with `AGENTS.md`, which is the machine-readable discovery file telling *external*
agents how to connect. This file is for whoever is changing the code in this repo.

## What this package is, and is not

`src/index.ts` is the whole proxy. It **embeds no schemas**, hardcodes no tool catalog, and pins no
contract version — it authenticates, connects upstream, and forwards `{ request }` verbatim. Almost
every "the server changed" question therefore needs **nothing here**.

Before adding anything to this package, check whether it belongs in `battlegrid-app` instead. Tool
schemas, contract semantics, and error vocabularies all live there.

## `skills/battlegrid-*` is generated — never edit it here

The nine `skills/battlegrid-*` directories, `skills/EXPORT.json`, and
`src/__fixtures__/authoring-contract-digest.json` are **written by
`battlegrid-app/server/scripts/export-mcp-skills.mjs`** and arrive by pull request from its
`.github/workflows/mcp-skills-export.yml`. They are the same instructions BattleGrid's in-app
Commander runs on, which is what makes them true about the tools this proxy forwards.

**To change a published skill, change it upstream** in `battlegrid-app/server/src/skills/<name>/` and
let the export lane bring it here. An edit made in this repository fails
`src/__tests__/skill-provenance.test.ts` by filename, and would in any case be silently reverted by
the next export.

This is not a style rule. It replaces a real arrangement that cost three pull requests (#47, #48,
#52) and shipped a fork: `skills/battlegrid-strategy-studio/` was hand-authored here, drifted from
the server's own document, and needed a gate of its own to notice. One author, one gate.

| Path | Owner |
|---|---|
| `SKILL.md` (repo root) | **this repository** — connection, the `{ account, request }` envelope, scopes, and pointers into the exported skills. There is no upstream source for it. |
| `skills/battlegrid-*/` | the export lane |
| `skills/EXPORT.json` | the export lane (sha256 per exported file) |
| `src/__fixtures__/authoring-contract-digest.json` | the export lane (vendored beside the documents it gates) |
| everything else | this repository |

Three tests divide the work and should not be merged:

- `skill-package.test.ts` — **packaging.** Frontmatter fence, `name` equals directory, `files`
  coverage, the four version values. (The name rule is why the export namespaces each skill to
  `battlegrid-<name>` on the way out.)
- `skill-provenance.test.ts` — **arrival.** Every file hashes as `EXPORT.json` records it, nothing
  unlisted sits under an exported directory, and the digest fixture's contract version matches the
  manifest's.
- `skill-contract.test.ts` — **consistency.** The exported `battlegrid-strategy-examples/SKILL.md`
  states the axes and domains the vendored digest carries. Its upstream twin
  (`authoring-recipe-contract.test.ts`) gates the same bytes; this one is the arrival check on the
  exported pair, not a second opinion about it.

**The export lane bumps the version itself** when it commits, but only if the version on `main` is
already on the registry — an unpublished version means a pending release is carrying it, and a
second bump would strand that number. So an export pull request usually arrives already bumped; do
not bump it again.

## Releasing — read this before touching a version

### A version change on `main` IS the release

`.github/workflows/publish.yml` runs on **every push to `main`** (plus `workflow_dispatch`), reads
`package.json`, and asks the registry whether that version exists. Three outcomes:

| Gate decision | When |
|---|---|
| `release=true` | the version is not on the registry → publish, then tag |
| `reconcile_tag=true` | already published, tag missing → create the tag only |
| neither | already published and tagged → nothing to do |

No tag authorizes a release; the tag is an **output** of a successful publish. There is nothing to
run by hand — merging is the trigger.

The workflow is deliberately **not** path-filtered on `package.json`: GitHub skips a path-filtered
workflow when a push diff exceeds 3,000 files and the matching file is not in the first 3,000
returned, so a version bump inside a large merge would silently fail to release. Releases are also
serialized (`concurrency: publish-mcp-server`, `cancel-in-progress: false`) because `npm publish`
moves `dist-tags.latest` unconditionally — a slower older run finishing last would drag `latest`
backward.

### Move all four values together — the check fails closed

`package.json` is not the only place the version lives. The workflow compares **four** values and
aborts the release if any disagree:

| Where | What to change |
|---|---|
| `package.json` | `"version"` |
| `package-lock.json` | root `"version"` |
| `package-lock.json` | `packages[""].version` (the self-referencing entry) |
| `src/index.ts` | `export const PACKAGE_VERSION = '…'` |

Run the workflow's own check locally before committing:

```bash
PKG=$(node -p "require('./package.json').version")
LOCK=$(node -p "require('./package-lock.json').version")
SELF=$(node -p "require('./package-lock.json').packages[''].version")
SRC=$(node -p "require('fs').readFileSync('src/index.ts','utf8').match(/PACKAGE_VERSION = '([^']+)'/)[1]")
[ "$PKG" = "$LOCK" ] && [ "$PKG" = "$SELF" ] && [ "$PKG" = "$SRC" ] \
  && echo "Version integrity OK: $PKG" || echo "MISMATCH — the release would fail closed"
```

The lockfile's self-referencing entry is the one that gets forgotten, which is why the check exists
rather than trusting `npm version`.

### What the number means — and what it must not track

**Version this package's own code, and nothing else.** Since v31 the number is the proxy's build
identity: a fix here, a dependency bump, a documentation correction. Ordinary semver against the
proxy's own surface — MAJOR for a break in how the proxy behaves or what its number means, MINOR for
proxy features, **PATCH for fixes and docs**.

**Do not bump because the server's contract moved.** That used to be the entire job and is now a
category error. A contract move needs *nothing* from this package: connected proxies read the
contract out of the upstream handshake and announce it verbatim on their next connection. The
publish-time deploy gate and the MAJOR.MINOR pairing rule were retired with v31 — there is no
ordering between a release here and a deploy there, in either direction.

So `npm view` and the announced contract legitimately differ, and code keyed to them being equal is
wrong.

### A docs-only change still needs a version bump to reach npm

`package.json`'s `files` is `["dist", "README.md", "LICENSE", "SKILL.md", "skills"]` — **README.md,
SKILL.md and the whole published skill ship inside the tarball**, so npmjs.com renders the README of
the last *published* version and every `npx` install gets that version's skill text.

That makes a README-only merge a silent no-op as far as the registry is concerned: the change lands
on `main`, the gate sees the current version already published, nothing publishes, and the npm page
keeps showing the old text. If the point of the change is that people read it on npm, it needs a
**PATCH bump** — which is exactly what "PATCH for fixes and docs" is for.

This is the one case where documenting a contract move *does* touch this package's version, and the
distinction matters: the bump is for publishing **the documentation**, never for the contract.

### Before opening the PR, confirm the release will actually happen

The integrity check above proves the four values agree with **each other**. It cannot tell you the
number is still *available*, and that is the failure this repository keeps repeating: branch off a
base whose version is already on the registry, change something that ships, merge — and the gate
sees the version published, does nothing, and reports **success**. CI is green end to end and
nothing reaches npm. It has cost #45 and #48 a release, and would have cost #50 a third.

What ships is narrower than `files` suggests, because `dist` is built rather than committed. The
build emits exactly one file, so the shipped set from source is **`src/index.ts` alone** —
`src/__tests__/` is excluded by `tsconfig.json` and `src/__fixtures__/` never reaches `dist`. A
fixture-only re-vendor genuinely needs no bump, which is why this tests the DIFF and not just the
version; a check that cried wolf on those would be ignored within a week.

`scripts/shipped-paths.mjs` owns that set. **Do not re-type it here or in the workflow** — this
check and the publish gate are one rule asked at two altitudes, and written out twice they drift
into the worst shape, where the checklist clears a branch the workflow then rejects. It derives
what it can from `files`; `skill-package.test.ts` and `shipped-paths.test.ts` assert the one
mapping it cannot (`dist` ← `src/index.ts`).

```bash
SHIPPED=$(git diff --name-only origin/main...HEAD | grep -E "$(node scripts/shipped-paths.mjs)" || true)
PKG=$(node -p "require('./package.json').version")

if [ -z "$SHIPPED" ]; then
  echo "Nothing that ships changed — $PKG may stay published; no bump needed."
elif npm view "@battlegrid/mcp-server@$PKG" version >/dev/null 2>&1; then
  echo "STRANDED — $PKG is already published and this branch changes shipped files:"
  echo "$SHIPPED" | sed 's/^/  /'
  echo "Merging would publish NOTHING. Bump before opening the PR."
else
  echo "OK — $PKG is unpublished and will carry:"
  echo "$SHIPPED" | sed 's/^/  /'
fi
```

Run it **before opening the PR**, not after merging. Once the release lands, the version is
published and the check reads STRANDED for every branch — true, and useless.

### Release checklist

1. Change the code or docs.
2. Move all four version values together; run the integrity snippet above.
3. Run the reach check above. **STRANDED means bump now** — merging would publish nothing.
4. `npm run build && npm test`.
5. Open a PR; merge it.
6. The workflow publishes with OIDC provenance and tags `mcp-server@<version>` after success.

If a run fails for a reason outside the diff — an unreachable endpoint, a registry error — re-run it
with `workflow_dispatch`. Never hand-publish: `npm` versions cannot be republished, and a
hand-publish with no tag is the exact silence this workflow was built to remove.

## Layout

```
src/index.ts           the entire proxy
src/__tests__/         announced-version, identity, shipped-paths, skill-contract,
                       skill-package, skill-provenance, startup-ordering,
                       strategy-authoring-proxy, validate-env
src/__fixtures__/      the vendored authoring-contract digest (generated — see above)
AGENTS.md              discovery file for external agents — how to CONNECT
README.md              user docs + contract history; SHIPS in the tarball
SKILL.md               the published connection skill, authored here
skills/battlegrid-*/   the nine exported skills (generated — see above)
skills/EXPORT.json     the export's hash manifest (generated)
scripts/               shipped-paths.mjs — the one definition of "changes the tarball"
site/                  the GitHub Pages site (CNAME + index.html)
.github/workflows/     ci.yml, publish.yml, static.yml
```

```bash
npm run build     # tsc
npm test          # vitest run
npm run dev       # tsc --watch
```

## Contract history lives in the README

When the server's contract breaks, the entry goes in README.md's contract-history section, grouped
by **what a client observes** — rejected input, reshaped output, widened enum — not by internal
cause. Entries are keyed to the CONTRACT version, not to a release of this package.
