package com.atlas.ragengine.ingest;

import java.util.ArrayList;
import java.util.List;
import java.util.function.ToIntFunction;

/**
 * Structural/recursive chunker (ADR-0011): splits on paragraph boundaries, greedily packs
 * paragraphs into windows of about {@code chunkSize} tokens, and carries ~{@code overlap} tokens
 * of context from the end of one chunk into the start of the next. Paragraphs larger than the
 * window are recursively split on sentence, then word, boundaries.
 *
 * <p>Token counting is injectable so tests get deterministic boundaries; the production default is
 * a cheap character-based estimator (≈ 4 chars/token) — good enough for chunk sizing without
 * pinning a tokenizer dependency.
 */
public class DocumentChunker {

    private final int chunkSize;
    private final int overlap;
    private final ToIntFunction<String> tokenCounter;

    public DocumentChunker(int chunkSize, int overlap, ToIntFunction<String> tokenCounter) {
        if (overlap >= chunkSize) {
            throw new IllegalArgumentException("overlap must be < chunkSize");
        }
        this.chunkSize = chunkSize;
        this.overlap = overlap;
        this.tokenCounter = tokenCounter;
    }

    /** Production default: char-based token estimate (~4 chars/token). */
    public DocumentChunker(int chunkSize, int overlap) {
        this(chunkSize, overlap, DocumentChunker::estimateTokens);
    }

    /** A single chunk of a document. */
    public record Chunk(int index, String text) {
    }

    public List<Chunk> chunk(String content) {
        List<String> units = splitParagraphs(content);
        List<String> packed = pack(units);
        List<String> withOverlap = applyOverlap(packed);
        List<Chunk> chunks = new ArrayList<>(withOverlap.size());
        for (int i = 0; i < withOverlap.size(); i++) {
            chunks.add(new Chunk(i, withOverlap.get(i)));
        }
        return chunks;
    }

    // ---- packing -----------------------------------------------------------

    private List<String> pack(List<String> units) {
        List<String> out = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        for (String unit : units) {
            if (tokenCounter.applyAsInt(unit) > chunkSize) {
                // flush current, then recursively split the oversized unit
                flush(out, current);
                out.addAll(pack(splitSmaller(unit)));
                continue;
            }
            String candidate = current.isEmpty() ? unit : current + "\n\n" + unit;
            if (tokenCounter.applyAsInt(candidate) > chunkSize && !current.isEmpty()) {
                flush(out, current);
                current.append(unit);
            } else {
                current.setLength(0);
                current.append(candidate);
            }
        }
        flush(out, current);
        return out;
    }

    private void flush(List<String> out, StringBuilder current) {
        if (!current.isEmpty()) {
            out.add(current.toString());
            current.setLength(0);
        }
    }

    /** Recursive fallback: sentences, then words, for a paragraph bigger than one window. */
    private List<String> splitSmaller(String text) {
        String[] sentences = text.split("(?<=[.!?])\\s+");
        if (sentences.length > 1) {
            return List.of(sentences);
        }
        return List.of(text.split("\\s+"));
    }

    private List<String> splitParagraphs(String content) {
        List<String> out = new ArrayList<>();
        for (String para : content.strip().split("\\n\\s*\\n")) {
            String trimmed = para.strip();
            if (!trimmed.isEmpty()) {
                out.add(trimmed);
            }
        }
        return out.isEmpty() ? List.of(content.strip()) : out;
    }

    // ---- overlap -----------------------------------------------------------

    private List<String> applyOverlap(List<String> chunks) {
        if (overlap <= 0 || chunks.size() <= 1) {
            return chunks;
        }
        List<String> out = new ArrayList<>(chunks.size());
        out.add(chunks.get(0));
        for (int i = 1; i < chunks.size(); i++) {
            String tail = trailingTokens(chunks.get(i - 1), overlap);
            out.add(tail.isEmpty() ? chunks.get(i) : tail + "\n\n" + chunks.get(i));
        }
        return out;
    }

    /** The trailing words of {@code text} whose estimated token count is ~{@code tokens}. */
    private String trailingTokens(String text, int tokens) {
        String[] words = text.split("\\s+");
        String acc = "";
        for (int i = words.length - 1; i >= 0; i--) {
            String candidate = acc.isEmpty() ? words[i] : words[i] + " " + acc;
            if (tokenCounter.applyAsInt(candidate) > tokens && !acc.isEmpty()) {
                break;
            }
            acc = candidate;
        }
        return acc;
    }

    static int estimateTokens(String text) {
        return Math.max(1, (int) Math.ceil(text.length() / 4.0));
    }
}
