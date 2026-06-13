package com.atlas.ragengine.ingest;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.ragengine.ingest.IngestionValidator.ValidationResult;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/** Unit test for {@link IngestionValidator} — LLM04 trusted-source admission + integrity hash. */
class IngestionValidatorTest {

    private final IngestionValidator validator =
            new IngestionValidator(List.of("classpath:corpus/"));

    @Test
    void acceptsTrustedDocumentAndComputesSha256() {
        SourceDocument doc = doc("classpath:corpus/layer2/x.md", "compliance", "hello atlas");
        ValidationResult result = validator.validate(doc);
        assertThat(result.accepted()).isTrue();
        // SHA-256("hello atlas") is stable + lowercase hex
        assertThat(result.contentSha256())
                .isEqualTo(IngestionValidator.sha256("hello atlas"))
                .hasSize(64)
                .matches("[0-9a-f]+");
    }

    @Test
    void rejectsUntrustedSource() {
        SourceDocument doc = doc("http://evil.example/poison.md", "public", "payload");
        ValidationResult result = validator.validate(doc);
        assertThat(result.accepted()).isFalse();
        assertThat(result.reason()).startsWith("untrusted-source");
        assertThat(result.contentSha256()).isNull();
    }

    @Test
    void rejectsInvalidClearance() {
        SourceDocument doc = doc("classpath:corpus/layer2/x.md", "top-secret", "payload");
        ValidationResult result = validator.validate(doc);
        assertThat(result.accepted()).isFalse();
        assertThat(result.reason()).startsWith("invalid-clearance");
    }

    @Test
    void rejectsEmptyContent() {
        SourceDocument doc = doc("classpath:corpus/layer2/x.md", "public", "   ");
        assertThat(validator.validate(doc).accepted()).isFalse();
    }

    @Test
    void sha256IsDeterministicAndKnown() {
        // echo -n "" | sha256sum  -> e3b0c442...855
        assertThat(IngestionValidator.sha256(""))
                .isEqualTo("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    }

    private static SourceDocument doc(String origin, String clearance, String content) {
        return new SourceDocument("id-1", "Title", clearance, "atlas://x", 2, origin, content, Map.of());
    }
}
