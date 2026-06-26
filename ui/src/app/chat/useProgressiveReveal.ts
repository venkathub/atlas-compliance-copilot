import { useEffect, useMemo, useState } from "react";

/**
 * useProgressiveReveal — the client-side "live assistant" effect (D-P5-1a / ADR-0051).
 *
 * The backends are synchronous, so rather than fake streaming we reveal the already-
 * complete answer incrementally (word-by-word) for a typewriter feel. Accessibility:
 * if the user prefers reduced motion, the full text is shown immediately. The reveal
 * always converges on the FULL, byte-identical answer, preserving the P3 grounding.
 */

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function useProgressiveReveal(
  full: string,
  opts: { wordsPerTick?: number; tickMs?: number } = {},
): { text: string; done: boolean } {
  const { wordsPerTick = 3, tickMs = 30 } = opts;
  const reduced = prefersReducedMotion();

  // Tokenize on whitespace, keeping separators so the re-join is byte-exact.
  const tokens = useMemo(() => (full.length ? full.split(/(\s+)/) : []), [full]);
  const total = tokens.length;

  const [count, setCount] = useState(reduced ? total : 0);

  // Reset the reveal when a NEW answer arrives — React's sanctioned "adjust state
  // during render" pattern, so the reset is not a setState-in-effect.
  const [prevFull, setPrevFull] = useState(full);
  if (full !== prevFull) {
    setPrevFull(full);
    setCount(reduced ? total : 0);
  }

  useEffect(() => {
    if (reduced || !total) return;
    const id = setInterval(() => {
      setCount((c) => {
        const next = c + wordsPerTick * 2; // a word + its trailing separator
        if (next >= total) {
          clearInterval(id);
          return total;
        }
        return next;
      });
    }, tickMs);
    return () => clearInterval(id);
  }, [full, total, reduced, wordsPerTick, tickMs]);

  const shown = Math.min(count, total);
  return { text: tokens.slice(0, shown).join(""), done: shown >= total };
}
