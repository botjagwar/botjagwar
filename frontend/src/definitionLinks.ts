export interface DefinitionLinkSegment {
  text: string;
  target?: string;
}

interface LinkCandidate {
  target: string;
  words: string[];
}

export type DefinitionLinkIndex = ReadonlyMap<string, readonly LinkCandidate[]>;

const EDGE_PUNCTUATION = /^[,.;:]+|[,.;:]+$/g;

function normalise(value: string): string {
  return value.toLocaleLowerCase();
}

function tokenWord(value: string): string {
  return value.replace(EDGE_PUNCTUATION, "");
}

/** Index linkable words by first token with longer phrases first. */
export function createDefinitionLinkIndex(words: ReadonlySet<string>): DefinitionLinkIndex {
  const index = new Map<string, LinkCandidate[]>();
  for (const target of words) {
    const candidateWords = target.split(/\s+/).filter(Boolean).map(normalise);
    if (!candidateWords.length) continue;
    const candidates = index.get(candidateWords[0]) ?? [];
    candidates.push({ target, words: candidateWords });
    index.set(candidateWords[0], candidates);
  }
  for (const candidates of index.values()) {
    candidates.sort((left, right) => right.words.length - left.words.length || left.target.localeCompare(right.target));
  }
  return index;
}

function appendSegment(segments: DefinitionLinkSegment[], text: string, target?: string): void {
  if (!text) return;
  const previous = segments.at(-1);
  if (!target && previous && !previous.target) {
    previous.text += text;
  } else {
    segments.push(target ? { text, target } : { text });
  }
}

/** Split a definition into plain text and deduplicated longest-match links. */
export function linkDefinition(definition: string, currentWord: string, index: DefinitionLinkIndex): DefinitionLinkSegment[] {
  if (definition.includes("[[") || definition.includes("]]")) return [{ text: definition }];

  const parts = definition.split(/(\s+)/);
  const tokenPartIndexes = parts.flatMap((part, partIndex) => part && !/^\s+$/.test(part) ? [partIndex] : []);
  const linkedTargets = new Set<string>();
  const currentTarget = normalise(currentWord);
  const segments: DefinitionLinkSegment[] = [];
  let tokenIndex = 0;
  let partIndex = 0;

  while (partIndex < parts.length) {
    if (tokenPartIndexes[tokenIndex] !== partIndex) {
      appendSegment(segments, parts[partIndex]);
      partIndex += 1;
      continue;
    }

    const firstWord = tokenWord(parts[partIndex]);
    const candidates = index.get(normalise(firstWord)) ?? [];
    const match = candidates.find((candidate) => {
      const target = normalise(candidate.target);
      if (target === currentTarget || linkedTargets.has(target) || tokenIndex + candidate.words.length > tokenPartIndexes.length) return false;
      return candidate.words.every((word, offset) => normalise(tokenWord(parts[tokenPartIndexes[tokenIndex + offset]])) === word);
    });

    if (!match) {
      appendSegment(segments, parts[partIndex]);
      tokenIndex += 1;
      partIndex += 1;
      continue;
    }

    const lastPartIndex = tokenPartIndexes[tokenIndex + match.words.length - 1];
    const firstOffset = parts[partIndex].indexOf(firstWord);
    const lastWord = tokenWord(parts[lastPartIndex]);
    const lastEnd = parts[lastPartIndex].lastIndexOf(lastWord) + lastWord.length;
    appendSegment(segments, parts[partIndex].slice(0, firstOffset));
    const linkedText = parts.slice(partIndex, lastPartIndex + 1).join("").slice(
      firstOffset,
      parts.slice(partIndex, lastPartIndex).join("").length + lastEnd,
    );
    appendSegment(segments, linkedText, match.target);
    appendSegment(segments, parts[lastPartIndex].slice(lastEnd));
    linkedTargets.add(normalise(match.target));
    tokenIndex += match.words.length;
    partIndex = lastPartIndex + 1;
  }
  return segments;
}
