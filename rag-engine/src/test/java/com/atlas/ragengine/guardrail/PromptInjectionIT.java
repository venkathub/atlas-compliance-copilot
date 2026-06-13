package com.atlas.ragengine.guardrail;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.ragengine.ingest.CorpusLoader;
import com.atlas.ragengine.ingest.DeterministicStubEmbeddingModel;
import com.atlas.ragengine.ingest.DocumentChunker;
import com.atlas.ragengine.ingest.EmbeddingWriter;
import com.atlas.ragengine.ingest.IngestionProperties;
import com.atlas.ragengine.ingest.IngestionService;
import com.atlas.ragengine.ingest.IngestionValidator;
import com.atlas.ragengine.ingest.SourceDocument;
import com.atlas.ragengine.retrieval.DenseRetriever;
import com.atlas.ragengine.retrieval.HybridDocumentRetriever;
import com.atlas.ragengine.retrieval.ReciprocalRankFusion;
import com.atlas.ragengine.retrieval.RetrievalProperties;
import com.atlas.ragengine.retrieval.RetrievedChunk;
import com.atlas.ragengine.retrieval.RrfPassThroughReranker;
import com.atlas.ragengine.retrieval.SparseRetriever;
import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.RbacFilterBuilder;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import javax.sql.DataSource;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

/**
 * Prompt-injection IT (LLM01, D7). Ingests the real corpus <em>and</em> the poisoned fixtures through
 * the real pipeline, then proves the guardrail: every poison doc is quarantined (the benign control
 * is not), and the spotlighted prompt context a PUBLIC (attacker-level) caller would get leaks none
 * of the restricted strings the payloads try to summon — combined RBAC + guardrail defense.
 */
class PromptInjectionIT {

    private static final int DIM = 768;
    private static final ObjectMapper JSON = new ObjectMapper();

    @SuppressWarnings("resource")
    private static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>(
            DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"));

    private static InjectionGuardrail guardrail;
    private static HybridDocumentRetriever hybrid;
    private static List<SourceDocument> poisonDocs;
    private static JsonNode expectations;

    @BeforeAll
    static void setUp() throws Exception {
        POSTGRES.start();
        Flyway.configure()
                .dataSource(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword())
                .locations("classpath:db/migration").load().migrate();

        DataSource ds = new DriverManagerDataSource(
                POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
        JdbcTemplate jdbc = new JdbcTemplate(ds);
        DeterministicStubEmbeddingModel embedder = new DeterministicStubEmbeddingModel(DIM);
        DocumentChunker chunker = new DocumentChunker(512, 64);

        // 1) real corpus
        IngestionProperties corpus = IngestionProperties.defaults();
        new IngestionService(new CorpusLoader(corpus), new IngestionValidator(corpus.trustedOrigins()),
                chunker, new EmbeddingWriter(jdbc, embedder, DIM), jdbc).rebuild();

        // 2) append the poisoned fixtures (authored test docs, legitimately ingested at public)
        IngestionProperties poison = new IngestionProperties(
                "classpath:corpus/layer1/manifest.json", "classpath:fixtures/poisoned/poison-*.md",
                null, null, null, List.of("classpath:fixtures/"));
        poisonDocs = new CorpusLoader(poison).loadLayer2();
        new IngestionService(new CorpusLoader(poison), new IngestionValidator(poison.trustedOrigins()),
                chunker, new EmbeddingWriter(jdbc, embedder, DIM), jdbc).ingest(poisonDocs);

        guardrail = new InjectionGuardrail(GuardrailProperties.defaults());
        RbacFilterBuilder rbac = new RbacFilterBuilder();
        hybrid = new HybridDocumentRetriever(
                new DenseRetriever(jdbc, embedder, rbac), new SparseRetriever(jdbc, rbac),
                new ReciprocalRankFusion(60), new RrfPassThroughReranker(), RetrievalProperties.defaults());

        expectations = JSON.readTree(new PathMatchingResourcePatternResolver()
                .getResource("classpath:fixtures/poisoned/expectations.json").getInputStream());
    }

    @AfterAll
    static void tearDown() {
        POSTGRES.stop();
    }

    @Test
    void scannerVerdictMatchesExpectationsPerDoc() {
        Map<String, String> bodyById = new HashMap<>();
        poisonDocs.forEach(d -> bodyById.put(d.docId(), d.content()));

        for (JsonNode d : expectations.get("docs")) {
            String docId = d.get("doc_id").asText();
            boolean mustQuarantine = d.get("mustQuarantine").asBoolean();
            assertThat(bodyById).containsKey(docId);
            assertThat(guardrail.scan(bodyById.get(docId)).flagged())
                    .as("guardrail verdict for %s", docId)
                    .isEqualTo(mustQuarantine);
        }
    }

    @Test
    void poisonedChunksAreQuarantinedFromRetrievedContext() {
        // an attacker queries as a PUBLIC caller; the poison docs are public so they CAN be retrieved
        List<RetrievedChunk> retrieved =
                hybrid.retrieve("Northwind Trading LLC quarterly note", ClearanceLevel.PUBLIC, 20).chunks();
        GuardrailResult result = guardrail.apply(retrieved);

        Map<String, Boolean> mustQuarantine = new HashMap<>();
        expectations.get("docs").forEach(d ->
                mustQuarantine.put(d.get("doc_id").asText(), d.get("mustQuarantine").asBoolean()));

        // every retrieved poison doc was quarantined; the benign control (if retrieved) was not
        for (RetrievedChunk c : retrieved) {
            Boolean mq = mustQuarantine.get(c.docId());
            if (Boolean.TRUE.equals(mq)) {
                assertThat(result.quarantined()).extracting(q -> q.chunk().docId()).contains(c.docId());
            } else if (Boolean.FALSE.equals(mq)) {
                assertThat(result.safe()).extracting(RetrievedChunk::docId).contains(c.docId());
            }
        }
        // at least one poison doc actually reached retrieval (otherwise the test proves nothing)
        assertThat(result.anyQuarantined()).isTrue();
    }

    @Test
    void spotlightedContextLeaksNoRestrictedStringsOrInjections() {
        List<RetrievedChunk> retrieved =
                hybrid.retrieve("Northwind beneficial owners draft SAR sanctions", ClearanceLevel.PUBLIC, 20)
                        .chunks();
        String context = guardrail.apply(retrieved).spotlightedContext();

        // RBAC kept restricted docs out; guardrail removed the payloads that tried to summon them
        for (JsonNode forbidden : expectations.get("answerMustNotContain")) {
            assertThat(context).doesNotContain(forbidden.asText());
        }
        // none of the injection-imperative phrases survive into the prompt context
        for (JsonNode phrase : expectations.get("injectionPhrases")) {
            assertThat(context.toLowerCase()).doesNotContain(phrase.asText().toLowerCase());
        }
    }
}
