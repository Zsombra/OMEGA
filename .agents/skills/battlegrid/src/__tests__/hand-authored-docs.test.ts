import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * The hand-authored docs teach connection, the `account` argument and scopes — never a tool's
 * arguments. A tool's input is the server's published schema, discovered live, and the exported
 * skills carry each workflow's calls (`battlegrid-app`, `mcp-tool-contract` "A breaking change to a
 * published tool ships as one coordinated rollout"). A call shape written here is a second statement
 * of a schema this package does not own, and it drifts the moment the server's contract moves: so
 * none may be written at all.
 *
 * README's contract-history entries describe the release they were written for, so the sweep reads
 * README only above its first `## Contract history` heading. Generated files are not swept: the
 * exported skills are `battlegrid-app`'s, checked there against the live schema.
 */

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

/** A `snake_case(` call, the shape every taught tool call opens with. */
const CALL_SNIPPET = /\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\(/g;

/** The README above its first contract-history entry. */
function currentReadme(text: string): string {
  const history = text.indexOf('\n## Contract history');
  return history === -1 ? text : text.slice(0, history);
}

/** Every call snippet in a text, as `line: snippet`. */
function callSnippets(text: string): string[] {
  return text.split('\n').flatMap((line, index) =>
    [...line.matchAll(CALL_SNIPPET)].map((match) => `${index + 1}: ${match[0]}`));
}

const HAND_AUTHORED: ReadonlyArray<{ readonly file: string; readonly current: (text: string) => string }> = [
  { file: 'SKILL.md', current: (text) => text },
  { file: 'AGENTS.md', current: (text) => text },
  { file: 'CLAUDE.md', current: (text) => text },
  { file: 'README.md', current: currentReadme },
];

describe('hand-authored docs teach no tool call', () => {
  it.each(HAND_AUTHORED)('$file carries no call snippet', ({ file, current }) => {
    expect(callSnippets(current(readFileSync(join(repoRoot, file), 'utf8')))).toEqual([]);
  });

  it('would catch a call snippet — the sweep is not vacuous', () => {
    expect(callSnippets('Stage with `stage_strategy_draft({ strategyId, draftVersion, axes })`.'))
      .toEqual(['1: stage_strategy_draft(']);
  });

  it('reads README only above its contract history', () => {
    expect(currentReadme('# Package\n\nNow.\n\n## Contract history — v1\n\n`get_agent_draft({ agentId })`'))
      .toBe('# Package\n\nNow.\n');
  });
});
