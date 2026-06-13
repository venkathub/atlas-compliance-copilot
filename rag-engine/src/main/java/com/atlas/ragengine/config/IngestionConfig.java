package com.atlas.ragengine.config;

import com.atlas.ragengine.ingest.CorpusLoader;
import com.atlas.ragengine.ingest.DocumentChunker;
import com.atlas.ragengine.ingest.EmbeddingWriter;
import com.atlas.ragengine.ingest.IngestionProperties;
import com.atlas.ragengine.ingest.IngestionService;
import com.atlas.ragengine.ingest.IngestionValidator;
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * Wires the ingestion pipeline from {@link IngestionProperties}. The pipeline classes are plain
 * constructor-injected POJOs (so ITs can build them directly against a Testcontainers datasource);
 * this config is the production assembly.
 */
@Configuration
@EnableConfigurationProperties(IngestionProperties.class)
public class IngestionConfig {

    @Bean
    CorpusLoader corpusLoader(IngestionProperties props) {
        return new CorpusLoader(props);
    }

    @Bean
    IngestionValidator ingestionValidator(IngestionProperties props) {
        return new IngestionValidator(props.trustedOrigins());
    }

    @Bean
    DocumentChunker documentChunker(IngestionProperties props) {
        return new DocumentChunker(props.chunkSize(), props.chunkOverlap());
    }

    @Bean
    EmbeddingWriter embeddingWriter(JdbcTemplate jdbcTemplate, EmbeddingModel embeddingModel,
            IngestionProperties props) {
        return new EmbeddingWriter(jdbcTemplate, embeddingModel, props.embeddingDim());
    }

    @Bean
    IngestionService ingestionService(CorpusLoader corpusLoader, IngestionValidator ingestionValidator,
            DocumentChunker documentChunker, EmbeddingWriter embeddingWriter, JdbcTemplate jdbcTemplate) {
        return new IngestionService(corpusLoader, ingestionValidator, documentChunker, embeddingWriter,
                jdbcTemplate);
    }
}
