package com.atlas.ragengine.config;

import com.atlas.ragengine.guardrail.InjectionGuardrail;
import com.atlas.ragengine.qa.CitationExtractor;
import com.atlas.ragengine.qa.QueryService;
import com.atlas.ragengine.retrieval.HybridRetriever;
import com.atlas.ragengine.security.RbacFilterBuilder;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** Wires the grounded-QA layer (retrieval → guardrail → ChatModel → citations). */
@Configuration
public class QaConfig {

    @Bean
    CitationExtractor citationExtractor(RbacFilterBuilder rbacFilterBuilder) {
        return new CitationExtractor(rbacFilterBuilder);
    }

    @Bean
    QueryService queryService(HybridRetriever hybridRetriever, InjectionGuardrail injectionGuardrail,
            CitationExtractor citationExtractor, ChatModel chatModel) {
        return new QueryService(hybridRetriever, injectionGuardrail, citationExtractor, chatModel);
    }
}
