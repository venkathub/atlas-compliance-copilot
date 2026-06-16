package com.atlas.gateway.resilience;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;

class RequestLimitsTest {

    private final RequestLimits limits = new RequestLimits(100, 256); // 100-token input cap

    @Test
    void acceptsInputWithinCap() {
        limits.validateInputSize("a short question"); // ~4 tokens — no exception
    }

    @Test
    void rejectsOversizedInputWith413() {
        String huge = "x".repeat(1000); // ~250 tokens > 100
        assertThatThrownBy(() -> limits.validateInputSize(huge))
                .isInstanceOf(ResponseStatusException.class)
                .satisfies(e -> assertThat(((ResponseStatusException) e).getStatusCode().value()).isEqualTo(413));
    }

    @Test
    void exposesMaxOutputTokens() {
        assertThat(limits.maxOutputTokens()).isEqualTo(256);
    }

    @Test
    void tokenEstimateIsDeterministic() {
        assertThat(RequestLimits.estimateTokens("12345678")).isEqualTo(2);
        assertThat(RequestLimits.estimateTokens("")).isZero();
        assertThat(RequestLimits.estimateTokens(null)).isZero();
    }
}
