package com.atlas.ragengine.config;

import com.atlas.ragengine.security.ClearanceResolver;
import com.atlas.ragengine.security.DevClearanceDirectory;
import com.atlas.ragengine.security.RbacFilterBuilder;
import com.atlas.ragengine.security.ClearanceLevel;
import com.atlas.ragengine.security.SecurityProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;

/**
 * Wires the RBAC core + the P1 clearance-transport shim.
 *
 * <p>The {@link RbacFilterBuilder} is always available (it is the retrieval trust boundary). The
 * trusted-header {@link ClearanceResolver} + {@link DevClearanceDirectory} are <b>profile-gated to
 * {@code local}/{@code test}</b> (ADR-0016): outside those profiles the shim is absent, so the
 * system fails closed (the P3 IdP provides the real resolver). Never enable this shim in a shared
 * or production environment.
 */
@Configuration
@EnableConfigurationProperties(SecurityProperties.class)
public class SecurityConfig {

    @Bean
    RbacFilterBuilder rbacFilterBuilder() {
        return new RbacFilterBuilder();
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
}
