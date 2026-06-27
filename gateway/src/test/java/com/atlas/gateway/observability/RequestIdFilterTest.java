package com.atlas.gateway.observability;

import static org.assertj.core.api.Assertions.assertThat;

import jakarta.servlet.FilterChain;
import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

class RequestIdFilterTest {

    private final RequestIdFilter filter = new RequestIdFilter();

    @Test
    void mintsRequestIdWhenAbsentAndEchoesOnResponse() throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest();
        MockHttpServletResponse response = new MockHttpServletResponse();
        String[] seenInChain = new String[1];
        FilterChain chain = (req, res) -> seenInChain[0] = MDC.get(RequestIdFilter.MDC_KEY);

        filter.doFilter(request, response, chain);

        String header = response.getHeader(RequestIdFilter.HEADER);
        assertThat(header).isNotBlank();
        assertThat(seenInChain[0]).isEqualTo(header); // available in the MDC during the request
        assertThat(MDC.get(RequestIdFilter.MDC_KEY)).isNull(); // and cleaned up afterwards
    }

    @Test
    void reusesWellFormedInboundRequestId() throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader(RequestIdFilter.HEADER, "abc-123_DEF.456");
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, (req, res) -> {});

        assertThat(response.getHeader(RequestIdFilter.HEADER)).isEqualTo("abc-123_DEF.456");
    }

    @Test
    void rejectsMaliciousInboundIdAndMintsAFreshOne() throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader(RequestIdFilter.HEADER, "evil\nINJECTED log line"); // log-injection attempt
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, (req, res) -> {});

        String header = response.getHeader(RequestIdFilter.HEADER);
        assertThat(header).doesNotContain("\n").doesNotContain("INJECTED");
        assertThat(header).matches("[A-Za-z0-9._-]{1,64}");
    }
}
