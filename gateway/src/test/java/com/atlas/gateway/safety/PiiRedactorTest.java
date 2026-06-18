package com.atlas.gateway.safety;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;

class PiiRedactorTest {

    private final PiiRedactor redactor = new PiiRedactor(List.of("Marcus T. Vale", "Caspian Freight FZE"));

    @Test
    void redactsStructuredFinancePii() {
        PiiRedactor.Redaction r = redactor.redact(
                "SSN 900-12-3456, passport X1234567, account 12345678, DOB 1980-04-12.");
        assertThat(r.text()).doesNotContain("900-12-3456", "X1234567", "12345678", "1980-04-12");
        assertThat(r.counts()).containsKeys("SSN_TIN", "PASSPORT", "ACCOUNT_NUMBER", "DOB");
        assertThat(r.applied()).isTrue();
    }

    @Test
    void redactsDenylistEntitiesCaseInsensitively() {
        PiiRedactor.Redaction r = redactor.redact("Owner marcus t. vale of CASPIAN FREIGHT FZE.");
        assertThat(r.text()).doesNotContainIgnoringCase("marcus t. vale").doesNotContainIgnoringCase("caspian freight fze");
        assertThat(r.counts().get("DENYLIST_TERM")).isEqualTo(2);
    }

    @Test
    void leavesCleanTextUntouched() {
        PiiRedactor.Redaction r = redactor.redact("Summarize the open AML exceptions this quarter.");
        assertThat(r.applied()).isFalse();
        assertThat(r.text()).isEqualTo("Summarize the open AML exceptions this quarter.");
    }
}
