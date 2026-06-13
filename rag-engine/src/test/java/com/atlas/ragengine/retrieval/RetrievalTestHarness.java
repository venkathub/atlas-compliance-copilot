package com.atlas.ragengine.retrieval;

import com.atlas.ragengine.ingest.CorpusLoader;
import com.atlas.ragengine.ingest.DeterministicStubEmbeddingModel;
import com.atlas.ragengine.ingest.DocumentChunker;
import com.atlas.ragengine.ingest.EmbeddingWriter;
import com.atlas.ragengine.ingest.IngestionProperties;
import com.atlas.ragengine.ingest.IngestionService;
import com.atlas.ragengine.ingest.IngestionValidator;
import com.atlas.ragengine.security.RbacFilterBuilder;
import javax.sql.DataSource;
import org.flywaydb.core.Flyway;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

/**
 * Shared retrieval-IT harness: a pgvector/pg16 container with the full corpus ingested (deterministic
 * stub embedder, no GPU) and the dense/sparse/hybrid retrievers wired against it. The dense retriever
 * shares the ingestion embedder so query and chunk vectors are comparable.
 */
final class RetrievalTestHarness implements AutoCloseable {

    static final int DIM = 768;

    final PostgreSQLContainer<?> postgres;
    final JdbcTemplate jdbc;
    final DenseRetriever dense;
    final SparseRetriever sparse;
    final HybridDocumentRetriever hybrid;

    @SuppressWarnings("resource")
    private RetrievalTestHarness() {
        postgres = new PostgreSQLContainer<>(
                DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"));
        postgres.start();

        Flyway.configure()
                .dataSource(postgres.getJdbcUrl(), postgres.getUsername(), postgres.getPassword())
                .locations("classpath:db/migration")
                .load()
                .migrate();

        DataSource ds = new DriverManagerDataSource(
                postgres.getJdbcUrl(), postgres.getUsername(), postgres.getPassword());
        jdbc = new JdbcTemplate(ds);

        IngestionProperties ingestProps = IngestionProperties.defaults();
        DeterministicStubEmbeddingModel embedder = new DeterministicStubEmbeddingModel(DIM);
        new IngestionService(
                new CorpusLoader(ingestProps),
                new IngestionValidator(ingestProps.trustedOrigins()),
                new DocumentChunker(ingestProps.chunkSize(), ingestProps.chunkOverlap()),
                new EmbeddingWriter(jdbc, embedder, DIM),
                jdbc).rebuild();

        RbacFilterBuilder rbac = new RbacFilterBuilder();
        dense = new DenseRetriever(jdbc, embedder, rbac);
        sparse = new SparseRetriever(jdbc, rbac);
        hybrid = new HybridDocumentRetriever(
                dense, sparse, new ReciprocalRankFusion(60), new RrfPassThroughReranker(),
                RetrievalProperties.defaults());
    }

    static RetrievalTestHarness start() {
        return new RetrievalTestHarness();
    }

    @Override
    public void close() {
        postgres.stop();
    }
}
