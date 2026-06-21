package com.atlas.mcptools.auth;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import com.atlas.mcptools.AbstractAgentSchemaIT;

/**
 * OAuth 2.1 resource-server IT (ADR-0046): the {@code /mcp} endpoint rejects missing / expired /
 * forged / wrong-audience (RFC 8707) tokens with 401, and accepts a valid audience-scoped token.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ResourceServerIT extends AbstractAgentSchemaIT {

    private static final String INIT = "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\","
            + "\"params\":{\"protocolVersion\":\"2025-11-25\",\"capabilities\":{},"
            + "\"clientInfo\":{\"name\":\"atlas-it\",\"version\":\"1\"}}}";

    @Autowired
    TestRestTemplate rest;

    private ResponseEntity<String> initWith(String bearer) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setAccept(java.util.List.of(
                MediaType.APPLICATION_JSON, MediaType.parseMediaType("text/event-stream")));
        if (bearer != null) {
            headers.setBearerAuth(bearer);
        }
        return rest.exchange("/mcp", HttpMethod.POST, new HttpEntity<>(INIT, headers), String.class);
    }

    @Test
    void missingTokenIsUnauthorized() {
        assertThat(initWith(null).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void expiredTokenIsUnauthorized() {
        String expired = TestTokens.mint(TOKEN_SIGNING_KEY, "priya", "compliance",
                TOKEN_ISSUER, TOKEN_AUDIENCE, Instant.now().minusSeconds(60));
        assertThat(initWith(expired).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void forgedSignatureIsUnauthorized() {
        String forged = TestTokens.valid("a-different-signing-key", TOKEN_ISSUER, TOKEN_AUDIENCE,
                "priya", "compliance");
        assertThat(initWith(forged).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void wrongAudienceIsUnauthorized() {
        String wrongAud = TestTokens.valid(TOKEN_SIGNING_KEY, TOKEN_ISSUER, "some-other-resource",
                "priya", "compliance");
        assertThat(initWith(wrongAud).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void wrongIssuerIsUnauthorized() {
        String wrongIss = TestTokens.valid(TOKEN_SIGNING_KEY, "evil-idp", TOKEN_AUDIENCE,
                "priya", "compliance");
        assertThat(initWith(wrongIss).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void validAudienceScopedTokenIsAccepted() {
        String token = TestTokens.valid(TOKEN_SIGNING_KEY, TOKEN_ISSUER, TOKEN_AUDIENCE,
                "priya", "compliance");
        ResponseEntity<String> response = initWith(token);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getHeaders().getFirst("Mcp-Session-Id")).isNotBlank();
    }
}
