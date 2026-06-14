package com.atlas.ragengine.config;

import com.atlas.ragengine.retrieval.DenseRetriever;
import com.atlas.ragengine.retrieval.HybridDocumentRetriever;
import com.atlas.ragengine.retrieval.LlmReranker;
import com.atlas.ragengine.retrieval.ReciprocalRankFusion;
import com.atlas.ragengine.retrieval.Reranker;
import com.atlas.ragengine.retrieval.RetrievalProperties;
import com.atlas.ragengine.retrieval.RrfPassThroughReranker;
import com.atlas.ragengine.retrieval.SparseRetriever;
import com.atlas.ragengine.security.RbacFilterBuilder;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

/** Wires the permission-aware hybrid retriever (dense + sparse + RBAC + RRF + rerank seam). */
@Configuration
@EnableConfigurationProperties(RetrievalProperties.class)
public class RetrievalConfig {

    @Bean
    DenseRetriever denseRetriever(JdbcTemplate jdbcTemplate, EmbeddingModel embeddingModel,
            RbacFilterBuilder rbacFilterBuilder) {
        return new DenseRetriever(jdbcTemplate, embeddingModel, rbacFilterBuilder);
    }

    @Bean
    SparseRetriever sparseRetriever(JdbcTemplate jdbcTemplate, RbacFilterBuilder rbacFilterBuilder,
            RetrievalProperties props) {
        return new SparseRetriever(jdbcTemplate, rbacFilterBuilder, props.tsqueryFunction());
    }

    @Bean
    ReciprocalRankFusion reciprocalRankFusion(RetrievalProperties props) {
        return new ReciprocalRankFusion(props.rrfK());
    }

    @Bean
    Reranker reranker(RetrievalProperties props, ChatModel chatModel) {
        // Eval-gated (ADR-0027): RRF pass-through by default; LLM-as-reranker when opted in.
        return props.llmReranker() ? new LlmReranker(chatModel) : new RrfPassThroughReranker();
    }

    @Bean
    HybridDocumentRetriever hybridDocumentRetriever(DenseRetriever denseRetriever,
            SparseRetriever sparseRetriever, ReciprocalRankFusion fusion, Reranker reranker,
            RetrievalProperties props) {
        return new HybridDocumentRetriever(denseRetriever, sparseRetriever, fusion, reranker, props);
    }
}
