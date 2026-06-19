package com.atlas.ragengine.config;

import com.atlas.ragengine.api.DownstreamClearanceFilter;
import com.atlas.ragengine.security.ClearanceResolver;
import com.atlas.ragengine.security.DevClearanceDirectory;
import com.atlas.ragengine.security.DownstreamClearanceVerifier;
import com.atlas.ragengine.security.InternalClearanceProperties;
import com.atlas.ragengine.security.RbacFilterBuilder;
import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.SecurityProperties;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.core.Ordered;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;

/**
 * Wires the RBAC core + the P1 clearance-transport shim + the P3 Gateway trust boundary.
 *
 * <p>The {@link RbacFilterBuilder} is always available (it is the retrieval trust boundary). The
 * trusted-header {@link ClearanceResolver} + {@link DevClearanceDirectory} are <b>profile-gated to
 * {@code local}/{@code test}</b> (ADR-0016): outside those profiles the shim is absent, so the
 * system fails closed (the P3 IdP provides the real resolver). Never enable this shim in a shared
 * or production environment.
 *
 * <p>The {@link DownstreamClearanceVerifier} + {@link DownstreamClearanceFilter} (ADR-0034) are always
 * available: when the Gateway forwards a valid signed internal clearance assertion, it is verified here
 * and used in preference to the shim header. Absent an assertion, the filter is a no-op.
 */
@Configuration
@EnableConfigurationProperties({SecurityProperties.class, InternalClearanceProperties.class})
public class SecurityConfig {

    @Bean
    RbacFilterBuilder rbacFilterBuilder() {
        return new RbacFilterBuilder();
    }

    @Bean
    DownstreamClearanceVerifier downstreamClearanceVerifier(InternalClearanceProperties props) {
        return new DownstreamClearanceVerifier(props);
    }

    @Bean
    FilterRegistrationBean<DownstreamClearanceFilter> downstreamClearanceFilter(DownstreamClearanceVerifier verifier) {
        FilterRegistrationBean<DownstreamClearanceFilter> reg =
                new FilterRegistrationBean<>(new DownstreamClearanceFilter(verifier));
        reg.addUrlPatterns("/v1/*");
        reg.setOrder(Ordered.HIGHEST_PRECEDENCE + 10);
        return reg;
    }

    @Bean
    @Profile({"local", "test"})
    DevClearanceDirectory devClearanceDirectory(SecurityProperties props) {
        return new DevClearanceDirectory(props.clearanceUsers(), ClearanceLevel.PUBLIC);
    }

    @Bean
    @Profile({"local", "test"})
    ClearanceResolver clearanceResolver(SecurityProperties props, DevClearanceDirectory directory) {
        return new ClearanceResolver(props, directory);
    }

    /**
     * Fail-closed fallback used outside {@code local}/{@code test}: no trusted-header shim, so the
     * context still loads but every caller resolves to {@code PUBLIC} (the P3 IdP provides the real
     * resolver). Ensures the app boots in any profile without trusting client headers.
     */
    @Bean
    @ConditionalOnMissingBean(ClearanceResolver.class)
    ClearanceResolver failClosedClearanceResolver() {
        return ClearanceResolver.failClosed();
    }
}
