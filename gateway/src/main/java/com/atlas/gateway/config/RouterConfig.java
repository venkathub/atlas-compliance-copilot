package com.atlas.gateway.config;

import com.atlas.gateway.router.CostProperties;
import com.atlas.gateway.router.CostTable;
import com.atlas.gateway.router.RoutingProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Wires the cost-aware model router (ADR-0035) + cost-units table (ADR-0040). {@code ModelRouter} is a
 * {@code @Component}; this enables its config properties and exposes the {@link CostTable}.
 */
@Configuration
@EnableConfigurationProperties({RoutingProperties.class, CostProperties.class})
public class RouterConfig {

    @Bean
    CostTable costTable(CostProperties props) {
        return new CostTable(props);
    }
}
