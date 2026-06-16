package com.atlas.gateway.auth;

import static org.assertj.core.api.Assertions.assertThat;

import jakarta.servlet.FilterChain;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

/** Unit tests for the trust-boundary filter (ADR-0034). */
class JwtClearanceFilterTest {

    private final IdpProperties props = new IdpProperties("test-signing-key", "atlas-sim-idp", 3600, null);
    private final ClearanceTokenService tokens = new ClearanceTokenService(props);
    private final JwtClearanceFilter filter = new JwtClearanceFilter(tokens);

    private MockHttpServletResponse response;
    private MockFilterChain chain;

    @BeforeEach
    void setUp() {
        response = new MockHttpServletResponse();
        chain = new MockFilterChain();
    }

    @Test
    void validTokenPassesAndSetsCallerAttribute() throws Exception {
        String token = tokens.mint("priya", Clearance.COMPLIANCE);
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/v1/query");
        request.addHeader("Authorization", "Bearer " + token);

        filter.doFilter(request, response, chain);

        assertThat(response.getStatus()).isEqualTo(200);
        assertThat(chain.getRequest()).isNotNull(); // chain proceeded
        CallerClearance caller = (CallerClearance) request.getAttribute(CallerClearance.ATTRIBUTE);
        assertThat(caller).isNotNull();
        assertThat(caller.subject()).isEqualTo("priya");
        assertThat(caller.clearance()).isEqualTo(Clearance.COMPLIANCE);
    }

    @Test
    void missingTokenIsUnauthorized() throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/v1/query");

        filter.doFilter(request, response, chain);

        assertThat(response.getStatus()).isEqualTo(401);
        assertThat(chain.getRequest()).isNull(); // chain not invoked
    }

    @Test
    void forgedTokenIsUnauthorized() throws Exception {
        ClearanceTokenService attacker =
                new ClearanceTokenService(new IdpProperties("attacker-key", "atlas-sim-idp", 3600, null));
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/v1/query");
        request.addHeader("Authorization", "Bearer " + attacker.mint("priya", Clearance.RESTRICTED));

        filter.doFilter(request, response, chain);

        assertThat(response.getStatus()).isEqualTo(401);
        assertThat(chain.getRequest()).isNull();
    }

    @Test
    void authEndpointIsNotFiltered() throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/v1/auth/token");

        filter.doFilter(request, response, chain);

        // No token, but the auth endpoint is skipped → chain proceeds, not 401.
        assertThat(response.getStatus()).isEqualTo(200);
        assertThat(chain.getRequest()).isNotNull();
    }

    @Test
    void actuatorIsNotFiltered() throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/actuator/health");

        filter.doFilter(request, response, chain);

        assertThat(response.getStatus()).isEqualTo(200);
        assertThat(chain.getRequest()).isNotNull();
    }
}
