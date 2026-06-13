package com.atlas.ragengine.schema;

import static org.assertj.core.api.Assertions.assertThat;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

/**
 * Schema migration IT — runs the production Flyway migration ({@code db/migration/V1__*.sql})
 * against a real pgvector/pg16 container and asserts the P1 schema materialised exactly as
 * specified (tables, indexes, the {@code vector(768)} column, the generated tsvector).
 *
 * <p>Drives Flyway's Java API directly against the container datasource — no Spring context,
 * no Ollama beans — so it tests the migration SQL in isolation. The "Flyway runs on app boot"
 * wiring is exercised later by the ingestion IT (P1 task 3), which needs a live context anyway.
 *
 * <p>Needs Docker but NOT a GPU, so it runs in normal CI. The local dev daemon (Docker >= 28)
 * requires docker-java's {@code api.version} to be pinned; the Failsafe config forwards
 * {@code -Dapi.version=${docker.api.version}} for that (see parent pom / RUNBOOK).
 */
class SchemaMigrationIT {

    // Same major as prod (PG16, ADR-0002). Stock pgvector image; V1 creates the `vector` ext.
    @SuppressWarnings("resource")
    private static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>(
            DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"));

    @BeforeAll
    static void migrate() {
        POSTGRES.start();
        Flyway.configure()
                .dataSource(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword())
                .locations("classpath:db/migration")
                .load()
                .migrate();
    }

    @AfterAll
    static void stop() {
        POSTGRES.stop();
    }

    @Test
    void bothTablesExist() throws SQLException {
        assertThat(tableExists("atlas_document")).isTrue();
        assertThat(tableExists("atlas_chunk")).isTrue();
    }

    @Test
    void allThreeIndexesExist() throws SQLException {
        assertThat(indexExists("atlas_chunk_hnsw")).isTrue();
        assertThat(indexExists("atlas_chunk_tsv")).isTrue();
        assertThat(indexExists("atlas_chunk_clear")).isTrue();
    }

    @Test
    void hnswIndexUsesHnswAccessMethod() throws SQLException {
        String method = queryString(
                """
                SELECT am.amname
                FROM pg_class c
                JOIN pg_index i ON i.indexrelid = c.oid
                JOIN pg_am am ON am.oid = c.relam
                WHERE c.relname = 'atlas_chunk_hnsw'
                """);
        assertThat(method).isEqualTo("hnsw");
    }

    @Test
    void embeddingColumnIsVector768() throws SQLException {
        // pgvector stores the declared dimension in the column's atttypmod.
        String dim = queryString(
                """
                SELECT a.atttypmod::text
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                WHERE c.relname = 'atlas_chunk' AND a.attname = 'embedding'
                """);
        assertThat(dim).isEqualTo("768");
    }

    @Test
    void contentTsvIsGeneratedColumn() throws SQLException {
        String generated = queryString(
                """
                SELECT is_generated
                FROM information_schema.columns
                WHERE table_name = 'atlas_chunk' AND column_name = 'content_tsv'
                """);
        assertThat(generated).isEqualTo("ALWAYS");
    }

    // ---- helpers -----------------------------------------------------------

    private static Connection conn() throws SQLException {
        return java.sql.DriverManager.getConnection(
                POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
    }

    private boolean tableExists(String table) throws SQLException {
        return queryString(
                "SELECT count(*)::text FROM information_schema.tables WHERE table_name = '" + table + "'")
                .equals("1");
    }

    private boolean indexExists(String index) throws SQLException {
        return queryString(
                "SELECT count(*)::text FROM pg_indexes WHERE indexname = '" + index + "'")
                .equals("1");
    }

    private String queryString(String sql) throws SQLException {
        try (Connection c = conn();
                ResultSet rs = c.createStatement().executeQuery(sql)) {
            return rs.next() ? rs.getString(1) : null;
        }
    }
}
