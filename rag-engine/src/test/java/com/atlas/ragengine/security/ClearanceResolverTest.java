package com.atlas.ragengine.security;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;
import org.junit.jupiter.api.Test;

/**
 * Unit test for the P1 clearance-transport shim ({@link ClearanceResolver} + the real D3 map on the
 * classpath). No servlet/Spring context — uses {@link RequestHeaders}.
 */
class ClearanceResolverTest {

    private final ClearanceResolver resolver = new ClearanceResolver(
            SecurityProperties.defaults(),
            new DevClearanceDirectory("classpath:dev/clearance-users.json", ClearanceLevel.PUBLIC));

    private ClearanceLevel resolve(Map<String, String> headers) {
        return resolver.resolve(RequestHeaders.of(headers));
    }

    @Test
    void explicitClearanceHeaderWins() {
        // even for a user mapped to public, an explicit header is honored (dev shim)
        ClearanceLevel level = resolve(Map.of(
                "X-Atlas-User", "guest-public",
                "X-Atlas-Clearance", "restricted"));
        assertThat(level).isEqualTo(ClearanceLevel.RESTRICTED);
    }

    @Test
    void userMapsToClearanceViaD3() {
        assertThat(resolve(Map.of("X-Atlas-User", "priya"))).isEqualTo(ClearanceLevel.COMPLIANCE);
        assertThat(resolve(Map.of("X-Atlas-User", "bsa-admin"))).isEqualTo(ClearanceLevel.RESTRICTED);
        assertThat(resolve(Map.of("X-Atlas-User", "analyst-bob"))).isEqualTo(ClearanceLevel.ANALYST);
    }

    @Test
    void headerLookupIsCaseInsensitive() {
        assertThat(resolve(Map.of("x-atlas-user", "priya"))).isEqualTo(ClearanceLevel.COMPLIANCE);
    }

    @Test
    void unknownUserFallsBackToDefault() {
        assertThat(resolve(Map.of("X-Atlas-User", "mallory"))).isEqualTo(ClearanceLevel.PUBLIC);
    }

    @Test
    void missingHeadersFallBackToDefaultPublic() {
        assertThat(resolve(Map.of())).isEqualTo(ClearanceLevel.PUBLIC);
    }

    @Test
    void unparseableClearanceHeaderFallsBackToDefault() {
        assertThat(resolve(Map.of("X-Atlas-Clearance", "god-mode"))).isEqualTo(ClearanceLevel.PUBLIC);
    }

    @Test
    void failClosedResolverIgnoresHeadersAndReturnsPublic() {
        ClearanceResolver failClosed = ClearanceResolver.failClosed();
        assertThat(failClosed.resolve(RequestHeaders.of(Map.of("X-Atlas-Clearance", "restricted"))))
                .isEqualTo(ClearanceLevel.PUBLIC);
        assertThat(failClosed.resolve(RequestHeaders.of(Map.of("X-Atlas-User", "bsa-admin"))))
                .isEqualTo(ClearanceLevel.PUBLIC);
    }
}
