package com.atlas.ragengine.config;

import com.atlas.ragengine.eval.InlineEvaluators;
import com.atlas.ragengine.guardrail.InjectionGuardrail;
import com.atlas.ragengine.observability.QueryTracer;
import com.atlas.ragengine.qa.CitationExtractor;
import com.atlas.ragengine.qa.ModelTierProperties;
import com.atlas.ragengine.qa.ModelTierResolver;
import com.atlas.ragengine.qa.QueryService;
import com.atlas.ragengine.retrieval.HybridRetriever;
import com.atlas.ragengine.security.RbacFilterBuilder;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** Wires the grounded-QA layer (retrieval → guardrail → ChatModel → citations). */
@Configuration
@EnableConfigurationProperties(ModelTierProperties.class)
public class QaConfig {

    @Bean
    CitationExtractor citationExtractor(RbacFilterBuilder rbacFilterBuilder) {
        return new CitationExtractor(rbacFilterBuilder);
    }

    @Bean
    ModelTierResolver modelTierResolver(ModelTierProperties props) {
        return new ModelTierResolver(props);
    }

    @Bean
    QueryService queryService(HybridRetriever hybridRetriever, InjectionGuardrail injectionGuardrail,
            CitationExtractor citationExtractor, ChatModel chatModel, QueryTracer queryTracer,
            InlineEvaluators inlineEvaluators) {
        return new QueryService(hybridRetriever, injectionGuardrail, citationExtractor, chatModel,
                queryTracer, inlineEvaluators);
    }
}
