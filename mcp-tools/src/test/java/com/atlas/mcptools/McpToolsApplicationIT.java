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
 * P4 task 1 + 2 — full-context smoke tests. With the audit datasource added in task 2 the context
 * needs a database, so this extends {@link AbstractAgentSchemaIT} (Testcontainers postgres). It verifies
 * the context starts, actuator health/metrics are exposed, and the Spring AI MCP server answers a real
 * <b>Streamable-HTTP</b> handshake ({@code initialize} → session → {@code tools/list}) advertising our
 * configured identity and an <b>empty</b> tool list (the {@code open_draft_sar} tool is added in task 3;
 * the full tool-call round-trip is a task-3 test).
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class McpToolsApplicationIT extends AbstractAgentSchemaIT {

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final String MCP_ENDPOINT = "/mcp";
    private static final String SESSION_HEADER = "Mcp-Session-Id";

    @Autowired
    private TestRestTemplate rest;

    @Autowired
    private org.springframework.jdbc.core.JdbcTemplate appJdbc;

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
    void mcpStreamableHttpHandshakeAdvertisesIdentityAndTheDraftSarTool() throws Exception {
        // 1) initialize → 200 + a session id; serverInfo carries our env-configured name/version,
        //    and the server advertises the `tools` capability.
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

        // 2) tools/list (with the session) → exactly the governed open_draft_sar tool, with a schema
        //    declaring the business args. (Added in P4 task 3.)
        String listBody = "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/list\",\"params\":{}}";
        ResponseEntity<String> list = rest.exchange(
                MCP_ENDPOINT, HttpMethod.POST, new HttpEntity<>(listBody, mcpHeaders(sessionId)), String.class);

        assertThat(list.getStatusCode()).isEqualTo(HttpStatus.OK);
        JsonNode tools = parseJsonRpc(list.getBody()).path("result").path("tools");
        assertThat(tools.isArray()).isTrue();
        assertThat(tools).hasSize(1);
        JsonNode tool = tools.get(0);
        assertThat(tool.path("name").asText()).isEqualTo("open_draft_sar");
        JsonNode schemaProps = tool.path("inputSchema").path("properties");
        assertThat(schemaProps.has("account")).isTrue();
        assertThat(schemaProps.has("period")).isTrue();
        assertThat(schemaProps.has("citations")).isTrue();
    }

    @Test
    void openDraftSarToolCallOverStreamableHttpCreatesDraft() throws Exception {
        String sessionId = initializeSession();

        String callBody = "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\","
                + "\"params\":{\"name\":\"open_draft_sar\",\"arguments\":{"
                + "\"account\":\"Northwind\",\"period\":\"2026-Q2\","
                + "\"rationale\":\"Exception #2 exceeds threshold\","
                + "\"citations\":[1,2],\"runId\":\"run_http_1\"}}}";
        ResponseEntity<String> call = rest.exchange(
                MCP_ENDPOINT, HttpMethod.POST, new HttpEntity<>(callBody, mcpHeaders(sessionId)), String.class);

        assertThat(call.getStatusCode()).isEqualTo(HttpStatus.OK);
        JsonNode result = parseJsonRpc(call.getBody()).path("result");
        assertThat(result.path("isError").asBoolean(false)).as("tool call succeeded").isFalse();

        // The draft was actually persisted (queryable by the originating run).
        Integer drafts = appJdbc.queryForObject(
                "SELECT count(*) FROM agent.sar_draft WHERE run_id = 'run_http_1'", Integer.class);
        assertThat(drafts).isEqualTo(1);
    }

    private String initializeSession() throws Exception {
        String initBody = "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\","
                + "\"params\":{\"protocolVersion\":\"2025-11-25\",\"capabilities\":{},"
                + "\"clientInfo\":{\"name\":\"atlas-it\",\"version\":\"1\"}}}";
        ResponseEntity<String> init = rest.exchange(
                MCP_ENDPOINT, HttpMethod.POST, new HttpEntity<>(initBody, mcpHeaders(null)), String.class);
        return init.getHeaders().getFirst(SESSION_HEADER);
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
