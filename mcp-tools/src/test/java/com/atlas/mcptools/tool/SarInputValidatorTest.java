package com.atlas.mcptools.tool;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import org.junit.jupiter.api.Test;

/** Unit tests for {@code open_draft_sar} input validation (P4_SPEC §2.3). No Spring/DB. */
class SarInputValidatorTest {

    private static final List<Integer> CITES = List.of(1, 2);

    @Test
    void acceptsWellFormedInput() {
        assertThatCode(() -> SarInputValidator.validate("Northwind", "2026-Q2", "exceeds threshold", CITES))
                .doesNotThrowAnyException();
    }

    @Test
    void rejectsBadPeriod() {
        assertThatThrownBy(() -> SarInputValidator.validate("acct", "2026Q2", "r", CITES))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("period");
        assertThatThrownBy(() -> SarInputValidator.validate("acct", "2026-Q5", "r", CITES))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> SarInputValidator.validate("acct", "26-Q1", "r", CITES))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejectsBlankAccountOrRationale() {
        assertThatThrownBy(() -> SarInputValidator.validate(" ", "2026-Q2", "r", CITES))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("account");
        assertThatThrownBy(() -> SarInputValidator.validate("acct", "2026-Q2", "  ", CITES))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("rationale");
    }

    @Test
    void rejectsOversizedRationale() {
        String big = "x".repeat(SarInputValidator.MAX_RATIONALE_LEN + 1);
        assertThatThrownBy(() -> SarInputValidator.validate("acct", "2026-Q2", big, CITES))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("2000");
    }

    @Test
    void rejectsEmptyOrNullCitations() {
        assertThatThrownBy(() -> SarInputValidator.validate("acct", "2026-Q2", "r", List.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("citations");
        assertThatThrownBy(() -> SarInputValidator.validate("acct", "2026-Q2", "r", null))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
