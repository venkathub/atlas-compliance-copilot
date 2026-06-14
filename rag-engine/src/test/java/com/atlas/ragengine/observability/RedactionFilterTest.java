package com.atlas.ragengine.observability;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;

class RedactionFilterTest {

    @Test
    void masksStructuredPii() {
        RedactionFilter filter = RedactionFilter.defaults();
        String redacted = filter.redact(
                "SSN 900-12-3456, passport X1234567, acct 1234567890123, mail a.b@x.io");
        assertThat(redacted)
                .doesNotContain("900-12-3456")
                .doesNotContain("X1234567")
                .doesNotContain("1234567890123")
                .doesNotContain("a.b@x.io")
                .contains(RedactionFilter.MASK);
    }

    @Test
    void masksDenylistedLiterals() {
        RedactionFilter filter = new RedactionFilter(List.of("Marcus T. Vale", "Caspian Freight FZE"));
        String redacted = filter.redact("Beneficial owner Marcus T. Vale of Caspian Freight FZE.");
        assertThat(redacted).doesNotContain("Marcus T. Vale").doesNotContain("Caspian Freight FZE");
    }

    @Test
    void leavesCleanTextUntouchedAndIsNullSafe() {
        RedactionFilter filter = RedactionFilter.defaults();
        assertThat(filter.redact("Total revenue rose 12% in 2022.")).isEqualTo("Total revenue rose 12% in 2022.");
        assertThat(filter.redact(null)).isNull();
        assertThat(filter.redact("")).isEmpty();
    }
}
