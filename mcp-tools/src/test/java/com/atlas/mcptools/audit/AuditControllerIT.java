package com.atlas.mcptools.audit;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.mcptools.AbstractAgentSchemaIT;
import com.atlas.mcptools.auth.TestTokens;
import com.fasterxml.jackson.databind.JsonNode;
import javax.sql.DataSource;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

/**
 * IT for the read-only, compliance-gated {@code GET /v1/audit} endpoint (P5 Task 5) against a real
 * postgres:16 container (shared {@link AbstractAgentSchemaIT}). Proves: token required (401);
 * sub-compliance clearance refused (403); compliance caller gets a newest-first page with a global
 * {@code chainVerified:true}; pagination + filters work; the response carries NO sensitive
 * digest/hash columns (LLM02); and the endpoint is SELECT-only (a GET does not mutate the log).
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class AuditControllerIT extends AbstractAgentSchemaIT {

    @Autowired
    TestRestTemplate rest;

    @Autowired
    AuditService auditService;

    private JdbcTemplate ownerJdbc;

    @BeforeEach
    void setUp() {
        DataSource owner = new DriverManagerDataSource(
                POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
        ownerJdbc = new JdbcTemplate(owner);
        ownerJdbc.execute("TRUNCATE agent.tool_audit RESTART IDENTITY");
    }

    private String token(String subject, String clearance) {
        return TestTokens.valid(TOKEN_SIGNING_KEY, TOKEN_ISSUER, TOKEN_AUDIENCE, subject, clearance);
    }

    private ResponseEntity<JsonNode> get(String path, String bearer) {
        HttpHeaders headers = new HttpHeaders();
        if (bearer != null) {
            headers.setBearerAuth(bearer);
        }
        return rest.exchange(path, HttpMethod.GET, new HttpEntity<>(headers), JsonNode.class);
    }

    private void seedThreeRows() {
        auditService.append("run_1", "open_draft_sar", AuditPhase.ATTEMPT,
                "priya", "compliance", Digests.sha256Hex("a1"), null);
        auditService.append("run_1", "open_draft_sar", AuditPhase.SUCCESS,
                "priya", "compliance", Digests.sha256Hex("a2"), "SAR-2026-000001");
        auditService.append("run_2", "open_draft_sar", AuditPhase.ATTEMPT,
                "bsa-admin", "restricted", Digests.sha256Hex("a3"), null);
    }

    @Test
    void missingTokenIsUnauthorized() {
        assertThat(get("/v1/audit", null).getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void subComplianceClearanceIsForbidden() {
        seedThreeRows();
        ResponseEntity<JsonNode> res = get("/v1/audit", token("analyst-bob", "analyst"));
        assertThat(res.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void complianceCallerGetsNewestFirstPageWithVerifiedChain() {
        seedThreeRows();
        ResponseEntity<JsonNode> res = get("/v1/audit", token("priya", "compliance"));

        assertThat(res.getStatusCode()).isEqualTo(HttpStatus.OK);
        JsonNode body = res.getBody();
        assertThat(body).isNotNull();
        assertThat(body.get("total").asInt()).isEqualTo(3);
        assertThat(body.get("chainVerified").asBoolean()).isTrue();
        assertThat(body.get("rows")).hasSize(3);
        // Newest first (seq DESC): first row is seq 3.
        assertThat(body.get("rows").get(0).get("seq").asLong()).isEqualTo(3L);
        // SUCCESS row carries a resultRef.
        assertThat(body.toString()).contains("SAR-2026-000001");
        // LLM02: no sensitive digest / hash-chain columns are surfaced.
        assertThat(body.toString())
                .doesNotContain("argsDigest")
                .doesNotContain("rowHash")
                .doesNotContain("prevHash");
    }

    @Test
    void paginatesByPageAndSize() {
        seedThreeRows();
        String t = token("priya", "compliance");

        JsonNode page0 = get("/v1/audit?page=0&size=2", t).getBody();
        assertThat(page0.get("total").asInt()).isEqualTo(3);
        assertThat(page0.get("rows")).hasSize(2);
        assertThat(page0.get("size").asInt()).isEqualTo(2);

        JsonNode page1 = get("/v1/audit?page=1&size=2", t).getBody();
        assertThat(page1.get("rows")).hasSize(1);
        assertThat(page1.get("page").asInt()).isEqualTo(1);
    }

    @Test
    void filtersByCallerAndRunId() {
        seedThreeRows();
        String t = token("priya", "compliance");

        JsonNode byCaller = get("/v1/audit?caller=bsa-admin", t).getBody();
        assertThat(byCaller.get("total").asInt()).isEqualTo(1);
        assertThat(byCaller.get("rows").get(0).get("caller").asText()).isEqualTo("bsa-admin");

        JsonNode byRun = get("/v1/audit?runId=run_1", t).getBody();
        assertThat(byRun.get("total").asInt()).isEqualTo(2);
    }

    @Test
    void getIsSelectOnlyAndDoesNotMutateTheLog() {
        seedThreeRows();
        Integer before = ownerJdbc.queryForObject("SELECT count(*) FROM agent.tool_audit", Integer.class);
        get("/v1/audit", token("priya", "compliance"));
        get("/v1/audit", token("priya", "compliance"));
        Integer after = ownerJdbc.queryForObject("SELECT count(*) FROM agent.tool_audit", Integer.class);
        assertThat(after).isEqualTo(before);
    }
}
