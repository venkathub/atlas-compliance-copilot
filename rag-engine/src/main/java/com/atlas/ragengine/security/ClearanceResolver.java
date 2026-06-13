package com.atlas.ragengine.security;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Resolves the caller's {@link ClearanceLevel} from request headers (ADR-0016, D-P1-6).
 *
 * <p><b>P1-only trusted-header shim</b> — wired only under the {@code local}/{@code test} profile
 * (see {@code SecurityConfig}); the simulated IdP in P3 (ADR-0003) supersedes it with a verifiable
 * claim. Resolution order:
 * <ol>
 *   <li>explicit {@code X-Atlas-Clearance} header (trusted in dev) — wins;</li>
 *   <li>{@code X-Atlas-User} header → D3 user→clearance map;</li>
 *   <li>otherwise the configured default (fail-closed: {@code public}).</li>
 * </ol>
 * Any unparseable/unknown value falls back to the default rather than escalating.
 */
public class ClearanceResolver {

    private static final Logger log = LoggerFactory.getLogger(ClearanceResolver.class);

    private final SecurityProperties props;
    private final DevClearanceDirectory directory;
    private final ClearanceLevel defaultLevel;

    public ClearanceResolver(SecurityProperties props, DevClearanceDirectory directory) {
        this.props = props;
        this.directory = directory;
        this.defaultLevel = resolveDefault(props, directory);
    }

    public ClearanceLevel resolve(RequestHeaders headers) {
        // 1) explicit clearance header (dev shim — trusted only under local/test profile)
        var explicit = headers.get(props.headerClearance());
        if (explicit.isPresent()) {
            try {
                return ClearanceLevel.fromLabel(explicit.get());
            } catch (IllegalArgumentException e) {
                log.warn("Unparseable {}='{}' — falling back to {}",
                        props.headerClearance(), explicit.get(), defaultLevel.label());
                return defaultLevel;
            }
        }
        // 2) user id -> D3 map
        var user = headers.get(props.headerUser());
        if (user.isPresent()) {
            return directory.clearanceFor(user.get()).orElseGet(() -> {
                log.warn("Unknown dev user '{}' — falling back to {}", user.get(), defaultLevel.label());
                return defaultLevel;
            });
        }
        // 3) default (fail-closed)
        return defaultLevel;
    }

    public ClearanceLevel defaultLevel() {
        return defaultLevel;
    }

    private static ClearanceLevel resolveDefault(SecurityProperties props, DevClearanceDirectory directory) {
        try {
            return ClearanceLevel.fromLabel(props.defaultClearance());
        } catch (IllegalArgumentException e) {
            return directory.defaultClearance();
        }
    }
}
