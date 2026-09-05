#!/usr/bin/env node
/**
 * The ONE definition of "a git path whose change alters the published tarball".
 *
 * WHY IT IS A SCRIPT AND NOT A REGEX WRITTEN TWICE: two sites ask this question — the pre-PR reach
 * check in CLAUDE.md and the publish workflow's stranded-release gate. One offers the answer, the
 * other refuses on it, and a repo rule says those are one rule at two altitudes. Written out twice
 * they drift in the worst direction: the checklist clears a branch the workflow then rejects, or
 * the workflow stays silent on exactly what the checklist was meant to catch.
 *
 * THE TRANSLATION THIS OWNS: `package.json` `files` is tarball-side, not git-side. Every entry maps
 * to itself EXCEPT `dist`, which is built rather than committed — its git-side source is
 * `src/index.ts`, because the build emits exactly one file. That is an assumption about the build,
 * so `skill-package.test.ts` asserts it rather than trusting this comment: it fails if the build
 * ever emits a second file, and it fails if `files` gains an entry this script does not map.
 *
 * Deliberately NOT `src/`: `src/__tests__/` is excluded by `tsconfig.json` and `src/__fixtures__/`
 * never reaches `dist`, so a test-only or fixture-only change genuinely needs no version bump. A
 * check that flagged those would be ignored within a week, which is the whole reason this is
 * precise rather than conservative.
 *
 * Prints one POSIX ERE on stdout, anchored, for `grep -E` against `git diff --name-only` output.
 */
import { readFileSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..');

/** Tarball-side `files` entry -> the git paths that build it. */
export const DIST_SOURCES = ['src/index.ts'];

/** Escape a literal path for use inside a POSIX ERE. */
function literal(path) {
  return path.replace(/[.[\]{}()*+?^$|\\]/g, '\\$&');
}

export function shippedPathPatterns(files, root = repoRoot) {
  return files.flatMap((entry) => {
    if (entry === 'dist') return DIST_SOURCES.map((source) => `${literal(source)}$`);
    // A directory entry ships everything beneath it; a file entry ships only itself. Asked of the
    // filesystem, never inferred from the name — `LICENSE` is a file and carries no extension.
    const isDirectory = statSync(join(root, entry)).isDirectory();
    return [isDirectory ? `${literal(entry)}/` : `${literal(entry)}$`];
  });
}

export function shippedPathsRegex(files, root = repoRoot) {
  return `^(${shippedPathPatterns(files, root).join('|')})`;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { files } = JSON.parse(readFileSync(join(repoRoot, 'package.json'), 'utf8'));
  process.stdout.write(`${shippedPathsRegex(files)}\n`);
}
