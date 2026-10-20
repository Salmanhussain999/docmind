const STOPWORDS = new Set(
  "a an and are as at be by can do does for from has have how i in is it its of on or that the this to was what when where which who why will with you your about there their them they".split(
    " ",
  ),
);

export function keywords(text: string): Set<string> {
  return new Set((text.toLowerCase().match(/[a-z0-9]+/g) ?? []).filter((w) => w.length > 2 && !STOPWORDS.has(w)));
}

/**
 * Splits a passage into sentences and marks the ones that best match the question:
 * at most three, so the highlight still points somewhere.
 */
export function highlightSentences(
  passage: string,
  question: string,
): Array<{ text: string; hit: boolean; heading: boolean }> {
  const terms = keywords(question);
  const sentences = passage.split(/(?<=[.!?])\s+|\n/).filter(Boolean);
  const scores = sentences.map((s) => [...keywords(s)].filter((w) => terms.has(w)).length);
  const best = Math.max(0, ...scores);
  const threshold = best >= 3 ? best - 1 : best;
  const winners = new Set(
    scores
      .map((score, i) => ({ score, i }))
      .filter(({ score }) => best > 0 && score >= threshold)
      .sort((a, b) => b.score - a.score)
      .slice(0, 3)
      .map(({ i }) => i),
  );
  // Short lines without closing punctuation are section headings kept apart by the backend.
  const isHeading = (text: string) => text.length <= 60 && !/[.!?:;"')\]]$/.test(text);
  return sentences.map((text, i) => ({ text, hit: winners.has(i) && !isHeading(text), heading: isHeading(text) }));
}

/** Turns "[2]" citations into markdown links the renderer can draw as highlighter chips. */
export function linkCitations(markdown: string): string {
  return markdown.replace(/\[(\d{1,2})\](?!\()/g, "[$1](#cite-$1)");
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
