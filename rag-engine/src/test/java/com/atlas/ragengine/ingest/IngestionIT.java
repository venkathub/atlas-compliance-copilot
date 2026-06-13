package com.atlas.ragengine.ingest;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.ragengine.ingest.IngestionService.IngestionReport;
import javax.sql.DataSource;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

/**
 * Ingestion IT: runs the full pipeline (load → validate → chunk → embed → store) against a real
 * pgvector/pg16 container with a deterministic stub embedder (Docker, no GPU). Asserts document/
 * chunk counts, provenance + integrity columns, the generated tsvector, embedding dimension, and
 * idempotency of the full rebuild.
 */
class IngestionIT {

    private static final int DIM = 768;

    @SuppressWarnings("resource")
    private static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>(
            DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"));

    private static JdbcTemplate jdbc;
    private static IngestionService service;
    private static CorpusLoader loader;

    @BeforeAll
    static void setUp() {
        POSTGRES.start();
        Flyway.configure()
                .dataSource(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword())
                .locations("classpath:db/migration")
                .load()
                .migrate();

        DataSource ds = new DriverManagerDataSource(
                POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
        jdbc = new JdbcTemplate(ds);

        IngestionProperties props = IngestionProperties.defaults();
        loader = new CorpusLoader(props);
        service = new IngestionService(
                loader,
                new IngestionValidator(props.trustedOrigins()),
                new DocumentChunker(props.chunkSize(), props.chunkOverlap()),
                new EmbeddingWriter(jdbc, new DeterministicStubEmbeddingModel(DIM), DIM),
                jdbc);
    }

    @AfterAll
    static void tearDown() {
        POSTGRES.stop();
    }

    @Test
    void ingestsEntireCorpusWithProvenanceAndEmbeddings() {
        IngestionReport report = service.rebuild();

        int expectedDocs = loader.loadAll().size();
        assertThat(report.documents()).isEqualTo(expectedDocs);
        assertThat(report.rejectedUntrusted()).isZero();
        assertThat(report.chunks()).isGreaterThanOrEqualTo(report.documents());

        // rows actually persisted
        assertThat(count("atlas_document")).isEqualTo(report.documents());
        assertThat(count("atlas_chunk")).isEqualTo(report.chunks());

        // provenance + integrity (LLM04): every document row is complete
        assertThat(intQuery("SELECT count(*) FROM atlas_document WHERE content_sha256 IS NULL")).isZero();
        assertThat(intQuery("SELECT count(*) FROM atlas_document "
                + "WHERE length(content_sha256) <> 64 OR source_uri IS NULL OR trusted IS NOT TRUE")).isZero();
        assertThat(intQuery("SELECT count(*) FROM atlas_document WHERE source_layer NOT IN (1,2)")).isZero();
        // both layers ingested
        assertThat(intQuery("SELECT count(*) FROM atlas_document WHERE source_layer = 1")).isEqualTo(12);
        assertThat(intQuery("SELECT count(*) FROM atlas_document WHERE source_layer = 2")).isEqualTo(12);

        // sparse tsvector generated + dense embedding at the configured dimension
        assertThat(intQuery("SELECT count(*) FROM atlas_chunk WHERE length(content_tsv::text) = 0")).isZero();
        assertThat(intQuery("SELECT count(*) FROM atlas_chunk WHERE vector_dims(embedding) <> " + DIM)).isZero();

        // clearance denormalized onto chunks and within the valid set
        assertThat(intQuery("SELECT count(*) FROM atlas_chunk "
                + "WHERE clearance NOT IN ('public','analyst','compliance','restricted')")).isZero();
    }

    @Test
    void rebuildIsIdempotent() {
        IngestionReport first = service.rebuild();
        IngestionReport second = service.rebuild();
        assertThat(second).isEqualTo(first);
        // no row accumulation across rebuilds
        assertThat(count("atlas_document")).isEqualTo(second.documents());
        assertThat(count("atlas_chunk")).isEqualTo(second.chunks());
    }

    private int count(String table) {
        return intQuery("SELECT count(*) FROM " + table);
    }

    private int intQuery(String sql) {
        Integer n = jdbc.queryForObject(sql, Integer.class);
        return n == null ? 0 : n;
    }
}
