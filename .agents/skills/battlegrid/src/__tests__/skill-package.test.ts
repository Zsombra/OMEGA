import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * The npm tarball is the skill package: `npx skills add` and tarball consumers read the skills
 * from the published files, so a skill missing from `files`, a frontmatter without its required
 * fields, or a name that no longer matches its directory ships a broken install. These checks
 * run against the repo exactly as `npm pack` would read it.
 *
 * PACKAGING ONLY. Whether an exported skill is the one `battlegrid-app` wrote is
 * `skill-provenance.test.ts`; whether it states the live authoring contract is
 * `skill-contract.test.ts`. The name-matches-directory rule below is why the export namespaces each
 * skill to `battlegrid-<name>` on the way out.
 */

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const packageJson = JSON.parse(readFileSync(join(repoRoot, 'package.json'), 'utf8')) as {
  version: string;
  files: string[];
};

/** Minimal frontmatter read: the `---` fence plus `name:` / `description:` scalars. */
function readFrontmatter(path: string): { name: string | null; description: string | null } {
  const lines = readFileSync(path, 'utf8').split('\n');
  expect(lines[0]?.trim(), `${path} must open with a frontmatter fence`).toBe('---');
  const closing = lines.indexOf('---', 1);
  expect(closing, `${path} must close its frontmatter fence`).toBeGreaterThan(0);
  const block = lines.slice(1, closing);
  const scalar = (key: string): string | null => {
    const line = block.find((entry) => entry.startsWith(`${key}:`));
    if (line === undefined) return null;
    const value = line.slice(key.length + 1).trim();
    return value.length > 0 ? value : null;
  };
  return { name: scalar('name'), description: scalar('description') };
}

describe('skill package', () => {
  it('ships both skill surfaces in the npm tarball file list', () => {
    expect(packageJson.files).toContain('SKILL.md');
    expect(packageJson.files).toContain('skills');
  });

  it('root SKILL.md carries valid frontmatter naming the battlegrid skill', () => {
    const frontmatter = readFrontmatter(join(repoRoot, 'SKILL.md'));
    expect(frontmatter.name).toBe('battlegrid');
    expect(frontmatter.description).not.toBeNull();
  });

  it('every skills/<dir> has a SKILL.md whose name matches its directory', () => {
    const skillsDir = join(repoRoot, 'skills');
    const directories = readdirSync(skillsDir, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name);
    expect(directories.length).toBeGreaterThan(0);

    for (const directory of directories) {
      const skillFile = join(skillsDir, directory, 'SKILL.md');
      expect(existsSync(skillFile), `${directory} must carry a SKILL.md`).toBe(true);
      const frontmatter = readFrontmatter(skillFile);
      expect(frontmatter.name, `${skillFile} name must match its directory`).toBe(directory);
      expect(frontmatter.description, `${skillFile} must describe itself`).not.toBeNull();
    }
  });

  it('every skill ships the references its SKILL.md points at', () => {
    // Generalised from a single named skill when the hand-authored studio fork was retired: the
    // assertion is worth keeping for whichever exported skill next carries a `references/` file,
    // and naming one directory would have quietly stopped checking anything the day it moved.
    const skillsDir = join(repoRoot, 'skills');
    for (const directory of readdirSync(skillsDir, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)) {
      const skillDir = join(skillsDir, directory);
      const body = readFileSync(join(skillDir, 'SKILL.md'), 'utf8');
      for (const reference of new Set(
        [...body.matchAll(/references\/[a-z0-9-]+\.md/g)].map((match) => match[0]),
      )) {
        expect(
          existsSync(join(skillDir, reference)),
          `${directory}/${reference} is named but not shipped`,
        ).toBe(true);
      }
    }
  });

  it('root SKILL.md names every exported skill directory', () => {
    // The root skill is the proxy-authored pointer into the exports (its table is the only place an
    // agent learns which skill to open), so an exported directory it does not name is unreachable.
    const rootSkill = readFileSync(join(repoRoot, 'SKILL.md'), 'utf8');
    const skillsDir = join(repoRoot, 'skills');
    const exported = readdirSync(skillsDir, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && entry.name.startsWith('battlegrid-'))
      .map((entry) => entry.name);

    expect(exported.length).toBeGreaterThan(0);
    for (const directory of exported) {
      expect(rootSkill, `root SKILL.md must name ${directory}`).toContain(`\`${directory}\``);
    }
  });

  it('all four release version values agree (the publish gate fails closed on a mismatch)', () => {
    const lock = JSON.parse(readFileSync(join(repoRoot, 'package-lock.json'), 'utf8')) as {
      version: string;
      packages: Record<string, { version?: string }>;
    };
    const source = readFileSync(join(repoRoot, 'src', 'index.ts'), 'utf8');
    const declared = source.match(/PACKAGE_VERSION = '([^']+)'/)?.[1];

    expect(lock.version).toBe(packageJson.version);
    expect(lock.packages['']?.version).toBe(packageJson.version);
    expect(declared).toBe(packageJson.version);
  });
});
