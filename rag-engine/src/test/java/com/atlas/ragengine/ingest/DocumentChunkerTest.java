package com.atlas.ragengine.ingest;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.ragengine.ingest.DocumentChunker.Chunk;
import java.util.List;
import java.util.function.ToIntFunction;
import org.junit.jupiter.api.Test;

/**
 * Unit test for {@link DocumentChunker}. Uses a deterministic word-count tokenizer so chunk
 * boundaries and overlap are exact and don't depend on the char-based production estimate.
 */
class DocumentChunkerTest {

    /** 1 token == 1 whitespace-delimited word. */
    private static final ToIntFunction<String> WORDS = s -> s.isBlank() ? 0 : s.strip().split("\\s+").length;

    @Test
    void shortContentProducesSingleChunk() {
        DocumentChunker chunker = new DocumentChunker(50, 10, WORDS);
        List<Chunk> chunks = chunker.chunk("A short paragraph with only a few words.");
        assertThat(chunks).hasSize(1);
        assertThat(chunks.get(0).index()).isZero();
    }

    @Test
    void longContentSplitsIntoWindowsRespectingChunkSize() {
        String para = words(40);
        String content = para + "\n\n" + para + "\n\n" + para; // three 40-word paragraphs
        DocumentChunker chunker = new DocumentChunker(50, 10, WORDS);

        List<Chunk> chunks = chunker.chunk(content);

        assertThat(chunks).hasSizeGreaterThan(1);
        // every chunk's base content stays within the window plus the carried overlap
        assertThat(chunks).allSatisfy(c -> assertThat(WORDS.applyAsInt(c.text())).isLessThanOrEqualTo(50 + 10));
        // indices are contiguous from 0
        for (int i = 0; i < chunks.size(); i++) {
            assertThat(chunks.get(i).index()).isEqualTo(i);
        }
    }

    @Test
    void consecutiveChunksOverlap() {
        DocumentChunker chunker = new DocumentChunker(20, 5, WORDS);
        // two paragraphs with distinct token namespaces, each within the window -> two chunks
        String first = ns("a", 19);   // a0 .. a18
        String second = ns("b", 19);  // b0 .. b18
        List<Chunk> chunks = chunker.chunk(first + "\n\n" + second);

        assertThat(chunks).hasSize(2);
        assertThat(chunks.get(0).text()).isEqualTo(first);
        // chunk 1 begins with the carried overlap (trailing a-words of chunk 0), then paragraph two
        assertThat(chunks.get(1).text()).startsWith("a");
        assertThat(chunks.get(1).text()).contains("a18"); // last token of chunk 0 carried over
        assertThat(chunks.get(1).text()).contains("b0");
    }

    @Test
    void oversizedParagraphIsRecursivelySplit() {
        DocumentChunker chunker = new DocumentChunker(10, 2, WORDS);
        // a single 30-word sentence-free paragraph exceeds the 10-token window
        List<Chunk> chunks = chunker.chunk(words(30));
        assertThat(chunks).hasSizeGreaterThan(1);
    }

    private static String ns(String prefix, int n) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < n; i++) {
            if (i > 0) {
                sb.append(' ');
            }
            sb.append(prefix).append(i);
        }
        return sb.toString();
    }

    private static String words(int n) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < n; i++) {
            if (i > 0) {
                sb.append(' ');
            }
            sb.append("w").append(i);
        }
        return sb.toString();
    }
}
