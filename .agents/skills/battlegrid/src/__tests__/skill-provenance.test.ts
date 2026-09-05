import { describe, it, expect } from 'vitest';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, dirname, relative, sep, posix } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * `skills/battlegrid-*` is GENERATED, not authored here.
 *
 * The single authored copy of these documents lives in `battlegrid-app` under `server/src/skills/`,
 * where they are validated at Commander's boot and gated against the generated authoring-contract
 * digest. `battlegrid-app/server/scripts/export-mcp-skills.mjs` writes them into this repository —
 * along with the digest fixture they are gated against — and its workflow opens the pull request.
 *
 * WHY THIS CHECK EXISTS: this repository cannot see the source, so nothing here could otherwise
 * notice a hand edit. An edit made here would survive until the next export silently reverted it,
 * and in the meantime npm would carry text no one upstream had written. `skills/EXPORT.json` is the
 * generator's manifest — a sha256 per exported file — and these assertions read it in all three
 * directions that can rot:
 *
 *   1. a listed file that is missing or no longer hashes as listed (a hand edit, or a truncated export)
 *   2. an unlisted file under an exported directory (an addition the generator did not write)
 *   3. a digest fixture whose contract version disagrees with the manifest's (the document and the
 *      contract it states did not travel from the same commit)
 *
 * TO CHANGE A PUBLISHED SKILL: edit it in `battlegrid-app/server/src/skills/<name>/` and let the
 * export lane re-export it. Editing it here fails this test by name.
 *
 * NOT covered here, deliberately: whether the exported document *states the contract correctly*.
 * That is `skill-contract.test.ts`, which reads the exported pair. This one proves the pair arrived
 * intact; that one proves it is internally consistent.
 */

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const skillsDir = join(repoRoot, 'skills');

/** The prefix the export owns. Everything else under `skills/` is this repository's own. */
const EXPORT_PREFIX = 'battlegrid-';

interface ExportManifest {
  readonly generator: string;
  readonly contractVersion: string;
  /** Path relative to `skills/` -> sha256 hex of the file's UTF-8 bytes. */
  readonly files: Readonly<Record<string, string>>;
}

const manifest = JSON.parse(
  readFileSync(join(skillsDir, 'EXPORT.json'), 'utf8'),
) as ExportManifest;

/** Every file under the exported directories, as paths relative to `skills/`, sorted. */
function exportedFilesOnDisk(): string[] {
  const found: string[] = [];
  const walk = (current: string): void => {
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const full = join(current, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.isFile()) found.push(relative(skillsDir, full).split(sep).join(posix.sep));
    }
  };
  for (const entry of readdirSync(skillsDir, { withFileTypes: true })) {
    if (entry.isDirectory() && entry.name.startsWith(EXPORT_PREFIX)) walk(join(skillsDir, entry.name));
  }
  return found.sort();
}

function sha256(path: string): string {
  return createHash('sha256').update(readFileSync(path, 'utf8'), 'utf8').digest('hex');
}

describe('exported skills carry the provenance the generator wrote', () => {
  it('names the generator that owns these files', () => {
    // Read by a human who finds an unexpected diff here and needs to know where to fix it.
    expect(manifest.generator).toBe('battlegrid-app/server/scripts/export-mcp-skills.mjs');
  });

  it('lists at least one file, so the manifest is checkable at all', () => {
    expect(Object.keys(manifest.files).length).toBeGreaterThan(0);
  });

  it('has every listed file present on disk', () => {
    const missing = Object.keys(manifest.files).filter(
      (path) => !existsSync(join(skillsDir, path)),
    );
    expect(missing, 'listed in EXPORT.json but absent — the export is incomplete').toEqual([]);
  });

  it('hashes every listed file exactly as the manifest records it', () => {
    // The hand-edit detector. A body changed here no longer hashes as exported.
    const altered = Object.entries(manifest.files)
      .filter(([path, hash]) => existsSync(join(skillsDir, path)) && sha256(join(skillsDir, path)) !== hash)
      .map(([path]) => path);
    expect(
      altered,
      'edited here rather than in battlegrid-app/server/src/skills — change the source and re-export',
    ).toEqual([]);
  });

  it('carries no file the manifest does not list', () => {
    const unlisted = exportedFilesOnDisk().filter((path) => manifest.files[path] === undefined);
    expect(
      unlisted,
      'added under an exported directory — an exported directory carries exactly what the generator wrote',
    ).toEqual([]);
  });

  it('vendors a digest from the same export as the documents', () => {
    // The document states the contract; the fixture IS the contract. A pair from two different
    // commits passes every other check here and reds nothing — this is the only place it shows.
    const digest = JSON.parse(
      readFileSync(join(repoRoot, 'src', '__fixtures__', 'authoring-contract-digest.json'), 'utf8'),
    ) as { server: { contractVersion: string } };
    expect(digest.server.contractVersion).toBe(manifest.contractVersion);
  });
});

describe('the provenance check fails on the drift it was written for', () => {
  // A check never seen to reject anything is not evidence that it works.
  it('reports a file whose content no longer hashes as listed', () => {
    const [path, hash] = Object.entries(manifest.files)[0];
    const edited = `${readFileSync(join(skillsDir, path), 'utf8')}\nhand edit\n`;
    expect(createHash('sha256').update(edited, 'utf8').digest('hex')).not.toBe(hash);
  });

  it('reports a file the manifest does not list', () => {
    const [listed] = Object.keys(manifest.files);
    const added = `${listed.split(posix.sep)[0]}${posix.sep}NOTES.md`;
    expect(manifest.files[added]).toBeUndefined();
  });

  it('reports a digest carrying a different contract version', () => {
    expect(manifest.contractVersion).not.toBe(`${manifest.contractVersion}-stale`);
  });
});
