package com.atlas.ragengine.retrieval;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.atlas.ragengine.security.RbacFilterBuilder;
import org.junit.jupiter.api.Test;

class RetrievalPropertiesTest {

    @Test
    void defaultsToP1Behaviour() {
        RetrievalProperties p = RetrievalProperties.defaults();
        assertThat(p.reranker()).isEqualTo("rrf");
        assertThat(p.sparseQuery()).isEqualTo("plainto");
        assertThat(p.tsqueryFunction()).isEqualTo("plainto_tsquery");
        assertThat(p.llmReranker()).isFalse();
    }

    @Test
    void websearchSelectsWebsearchTsquery() {
        RetrievalProperties p = new RetrievalProperties(null, null, null, null, "llm", "websearch");
        assertThat(p.tsqueryFunction()).isEqualTo("websearch_to_tsquery");
        assertThat(p.llmReranker()).isTrue();
    }

    @Test
    void sparseRetrieverRejectsNonAllowlistedFunction() {
        // the tsquery function is interpolated into SQL — only the allow-list is permitted
        assertThatThrownBy(() ->
                new SparseRetriever(null, new RbacFilterBuilder(), "evil(); DROP TABLE atlas_chunk;--"))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
