package com.atlas.gateway.safety;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class OutputSanitizerTest {

    private final OutputSanitizer sanitizer = new OutputSanitizer();

    @Test
    void stripsScriptBlocks() {
        OutputSanitizer.Sanitized s = sanitizer.sanitize("Answer <script>steal()</script> done.");
        assertThat(s.text()).doesNotContainIgnoringCase("<script>").doesNotContain("steal()");
        assertThat(s.applied()).isTrue();
    }

    @Test
    void neutralizesJavascriptUriAndEventHandlers() {
        OutputSanitizer.Sanitized s = sanitizer.sanitize("<a href=\"javascript:evil()\" onclick=\"x()\">link</a>");
        assertThat(s.text()).doesNotContainIgnoringCase("javascript:");
        assertThat(s.text()).doesNotContain("onclick=");
        assertThat(s.applied()).isTrue();
    }

    @Test
    void escapesResidualMarkup() {
        OutputSanitizer.Sanitized s = sanitizer.sanitize("1 < 2 and 3 > 2");
        assertThat(s.text()).contains("&lt;", "&gt;");
        assertThat(s.text()).doesNotContain("< 2");
    }

    @Test
    void leavesPlainTextUntouched() {
        OutputSanitizer.Sanitized s = sanitizer.sanitize("Open AML exceptions [1].");
        assertThat(s.applied()).isFalse();
        assertThat(s.text()).isEqualTo("Open AML exceptions [1].");
    }
}
