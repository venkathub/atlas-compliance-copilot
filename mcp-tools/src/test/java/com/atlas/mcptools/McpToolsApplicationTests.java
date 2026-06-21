package com.atlas.mcptools;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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

/**
 * P4 task 1 — skeleton smoke tests. Model-free and dependency-free: the mcp-tools skeleton needs no
 * DB / Redis / GPU (datasource + Flyway arrive in task 2), so this runs in plain CI (no Docker).
 *
 * <p>Verifies the application context starts, actuator health/metrics are exposed, and the Spring AI
 * MCP server answers a real <b>Streamable-HTTP</b> handshake ({@code initialize} → session →
 * {@code tools/list}) advertising our configured identity and an <b>empty</b> tool list (the
 * {@code open_draft_sar} tool is added in task 3; the full tool-call round-trip is a task-3 test).
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class McpToolsApplicationTests {

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final String MCP_ENDPOINT = "/mcp";
    private static final String SESSION_HEADER = "Mcp-Session-Id";

    @Autowired
    private TestRestTemplate rest;

    @Test
    void contextLoads() {
        // The application context (Spring AI MCP server WebMVC + actuator) starts cleanly.
    }

    @Test
    void actuatorHealthIsUp() {
        ResponseEntity<String> response = rest.getForEntity("/actuator/health", String.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).contains("\"status\":\"UP\"");
    }

    @Test
    void prometheusEndpointIsExposed() {
        ResponseEntity<String> response = rest.getForEntity("/actuator/prometheus", String.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
    }

    @Test
    void mcpStreamableHttpHandshakeAdvertisesIdentityAndZeroTools() throws Exception {
        // 1) initialize → 200 + a session id; serverInfo carries our env-configured name/version,
        //    and the server advertises the `tools` capability (ready to host tools in later tasks).
        String initBody = "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\","
                + "\"params\":{\"protocolVersion\":\"2025-11-25\",\"capabilities\":{},"
                + "\"clientInfo\":{\"name\":\"atlas-it\",\"version\":\"1\"}}}";
        ResponseEntity<String> init = rest.exchange(
                MCP_ENDPOINT, HttpMethod.POST, new HttpEntity<>(initBody, mcpHeaders(null)), String.class);

        assertThat(init.getStatusCode()).isEqualTo(HttpStatus.OK);
        String sessionId = init.getHeaders().getFirst(SESSION_HEADER);
        assertThat(sessionId).as("MCP Streamable HTTP issues a session id on initialize").isNotBlank();

        JsonNode initResult = parseJsonRpc(init.getBody()).path("result");
        assertThat(initResult.path("serverInfo").path("name").asText()).isEqualTo("atlas-mcp-tools");
        assertThat(initResult.path("capabilities").has("tools")).as("server advertises tools capability").isTrue();

        // 2) tools/list (with the session) → an empty tool array (skeleton registers no tools).
        String listBody = "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/list\",\"params\":{}}";
        ResponseEntity<String> list = rest.exchange(
                MCP_ENDPOINT, HttpMethod.POST, new HttpEntity<>(listBody, mcpHeaders(sessionId)), String.class);

        assertThat(list.getStatusCode()).isEqualTo(HttpStatus.OK);
        JsonNode tools = parseJsonRpc(list.getBody()).path("result").path("tools");
        assertThat(tools.isArray()).as("result.tools is a JSON array").isTrue();
        assertThat(tools).as("no tools are registered in the P4 task-1 skeleton").isEmpty();
    }

    private static HttpHeaders mcpHeaders(String sessionId) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setAccept(java.util.List.of(
                MediaType.APPLICATION_JSON, MediaType.parseMediaType("text/event-stream")));
        if (sessionId != null) {
            headers.set(SESSION_HEADER, sessionId);
        }
        return headers;
    }

    /** Streamable HTTP may answer as plain JSON or as an SSE {@code data:} frame — handle both. */
    private static JsonNode parseJsonRpc(String responseBody) throws Exception {
        assertThat(responseBody).as("MCP response body present").isNotBlank();
        String json = responseBody;
        if (json.contains("data:")) {
            json = json.lines()
                    .filter(l -> l.startsWith("data:"))
                    .map(l -> l.substring("data:".length()).trim())
                    .reduce((a, b) -> b) // last data frame carries the result
                    .orElseThrow();
        }
        return MAPPER.readTree(json);
    }
}
