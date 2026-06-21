package com.atlas.mcptools;

import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

/**
 * Shared Testcontainers base for mcp-tools ITs. Now that the module persists to Postgres (P4 task 2),
 * any full-context test needs a database, so this stands up a single postgres:16 container (singleton
 * pattern — started once per JVM, reaped by Ryuk) and wires the two-role model:
 *
 * <ul>
 *   <li><b>Flyway</b> runs as the container superuser (privileged: creates schema, role, grants, trigger);</li>
 *   <li><b>the runtime datasource</b> connects as the least-privilege {@code atlas_mcp_app} role.</li>
 * </ul>
 */
abstract public class AbstractAgentSchemaIT {

    protected static final String APP_ROLE = "atlas_mcp_app";
    protected static final String APP_PASSWORD = "app-secret-pw";

    /** Resource-server token config (task 4) — shared with {@code TestTokens} for minting. */
    protected static final String TOKEN_SIGNING_KEY = "it-mcp-signing-key";
    protected static final String TOKEN_ISSUER = "atlas-sim-idp";
    protected static final String TOKEN_AUDIENCE = "atlas-mcp-tools";

    @SuppressWarnings("resource")
    protected static final PostgreSQLContainer<?> POSTGRES =
            new PostgreSQLContainer<>(DockerImageName.parse("postgres:16"));

    static {
        POSTGRES.start();
    }

    @DynamicPropertySource
    static void datasourceProps(DynamicPropertyRegistry registry) {
        registry.add("ATLAS_MCP_DB_URL", POSTGRES::getJdbcUrl);
        // Privileged migration identity (Flyway).
        registry.add("ATLAS_MCP_DB_USERNAME", POSTGRES::getUsername);
        registry.add("ATLAS_MCP_DB_PASSWORD", POSTGRES::getPassword);
        // Least-privilege runtime identity (the app pool).
        registry.add("ATLAS_MCP_DB_APP_USERNAME", () -> APP_ROLE);
        registry.add("ATLAS_MCP_DB_APP_PASSWORD", () -> APP_PASSWORD);
        // OAuth 2.1 resource-server config (task 4).
        registry.add("ATLAS_MCP_TOKEN_SIGNING_KEY", () -> TOKEN_SIGNING_KEY);
        registry.add("ATLAS_MCP_TOKEN_ISSUER", () -> TOKEN_ISSUER);
        registry.add("ATLAS_MCP_TOKEN_AUDIENCE", () -> TOKEN_AUDIENCE);
    }
}
