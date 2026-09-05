import { describe, it, expect } from 'vitest';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
// eslint-disable-next-line import/extensions -- release tooling lives outside tsconfig's include
import { DIST_SOURCES } from '../../scripts/shipped-paths.mjs';

/**
 * `scripts/shipped-paths.mjs` answers one question — does a git path's change alter the published
 * tarball — for two callers that must not disagree: the pre-PR reach check in CLAUDE.md and the
 * publish workflow's stranded-release gate.
 *
 * WHAT THESE GUARD: the script maps `files` entries to git paths, and the ONE mapping it cannot
 * read off `package.json` is `dist`, which is built rather than committed. That mapping is an
 * assumption about the build, so it is asserted here rather than trusted — a second emitted file,
 * or a new `files` entry the script does not handle, breaks a release check silently otherwise.
 */

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const scriptPath = join(repoRoot, 'scripts', 'shipped-paths.mjs');
const packageJson = JSON.parse(readFileSync(join(repoRoot, 'package.json'), 'utf8')) as {
  files: string[];
};

const regex = new RegExp(
  execFileSync('node', [scriptPath], { cwd: repoRoot, encoding: 'utf8' }).trim(),
);

describe('shipped-paths', () => {
  it('maps every built files[] entry, since only those need a hand-written source', () => {
    // Everything else in `files` is a committed path the script derives from `package.json`
    // directly, so asserting those would test the derivation against itself. `dist` is the one
    // entry with no git path of its own, and the only place the mapping can rot.
    //
    // Tracked-by-git, not present-on-disk: `dist` exists the moment anything runs a build, so
    // presence would classify it as committed and quietly empty this assertion.
    const built = packageJson.files.filter(
      (entry) =>
        execFileSync('git', ['ls-files', '--', entry], { cwd: repoRoot, encoding: 'utf8' }).trim()
          .length === 0,
    );
    expect(built, 'a files[] entry is neither committed nor a known build output').toEqual(['dist']);
    for (const source of DIST_SOURCES) {
      expect(existsSync(join(repoRoot, source)), `${source} must exist to build dist`).toBe(true);
    }
  });

  it('emits exactly one build output, which is what makes src/index.ts the whole dist source', () => {
    execFileSync('npm', ['run', 'build'], { cwd: repoRoot, stdio: 'pipe' });
    const emitted = execFileSync('find', ['dist', '-name', '*.js'], {
      cwd: repoRoot,
      encoding: 'utf8',
    })
      .trim()
      .split('\n')
      .filter(Boolean);
    expect(emitted).toEqual(['dist/index.js']);
  });

  it('matches the paths that ship', () => {
    for (const path of [
      'src/index.ts',
      'README.md',
      'LICENSE',
      'SKILL.md',
      'skills/EXPORT.json',
      'skills/battlegrid-strategy-examples/SKILL.md',
      'skills/battlegrid-arena-play/SKILL.md',
    ]) {
      expect(regex.test(path), `${path} ships and must match`).toBe(true);
    }
  });

  it('does not match paths that cannot change the tarball', () => {
    // Each of these has a real precedent: a fixture-only re-vendor (#48), a test-only change (#50),
    // maintainer docs (#51), and the version files, which move but are not themselves shipped.
    for (const path of [
      'src/__fixtures__/authoring-contract-digest.json',
      'src/__tests__/skill-contract.test.ts',
      'CLAUDE.md',
      'AGENTS.md',
      'package.json',
      'package-lock.json',
      '.github/workflows/publish.yml',
      'site/index.html',
    ]) {
      expect(regex.test(path), `${path} does not ship and must not match`).toBe(false);
    }
  });
});
