package com.atlas.ragengine.config;

import com.atlas.ragengine.retrieval.DenseRetriever;
import com.atlas.ragengine.retrieval.HybridDocumentRetriever;
import com.atlas.ragengine.retrieval.ReciprocalRankFusion;
import com.atlas.ragengine.retrieval.Reranker;
import com.atlas.ragengine.retrieval.RetrievalProperties;
import com.atlas.ragengine.retrieval.RrfPassThroughReranker;
import com.atlas.ragengine.retrieval.SparseRetriever;
import com.atlas.ragengine.security.RbacFilterBuilder;
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
    SparseRetriever sparseRetriever(JdbcTemplate jdbcTemplate, RbacFilterBuilder rbacFilterBuilder) {
        return new SparseRetriever(jdbcTemplate, rbacFilterBuilder);
    }

    @Bean
    ReciprocalRankFusion reciprocalRankFusion(RetrievalProperties props) {
        return new ReciprocalRankFusion(props.rrfK());
    }

    @Bean
    Reranker reranker() {
        return new RrfPassThroughReranker();
    }

    @Bean
    HybridDocumentRetriever hybridDocumentRetriever(DenseRetriever denseRetriever,
            SparseRetriever sparseRetriever, ReciprocalRankFusion fusion, Reranker reranker,
            RetrievalProperties props) {
        return new HybridDocumentRetriever(denseRetriever, sparseRetriever, fusion, reranker, props);
    }
}
