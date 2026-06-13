package com.atlas.ragengine.security;

import static org.assertj.core.api.Assertions.assertThat;

import com.atlas.ragengine.security.RbacFilterBuilder.RbacPredicate;
import org.junit.jupiter.api.Test;

class RbacFilterBuilderTest {

    private final RbacFilterBuilder builder = new RbacFilterBuilder();

    @Test
    void predicateBindsCallerVisibleLabels() {
        RbacPredicate p = builder.predicate("clearance", ClearanceLevel.COMPLIANCE);
        assertThat(p.sqlFragment()).isEqualTo("clearance = ANY(?)");
        assertThat(p.params()).hasSize(1);
        assertThat((String[]) p.params()[0]).containsExactly("public", "analyst", "compliance");
    }

    @Test
    void predicateForPublicOnlySeesPublic() {
        RbacPredicate p = builder.predicate("c.clearance", ClearanceLevel.PUBLIC);
        assertThat(p.sqlFragment()).isEqualTo("c.clearance = ANY(?)");
        assertThat((String[]) p.params()[0]).containsExactly("public");
    }

    @Test
    void predicateForRestrictedSeesEverything() {
        RbacPredicate p = builder.predicate("clearance", ClearanceLevel.RESTRICTED);
        assertThat((String[]) p.params()[0])
                .containsExactly("public", "analyst", "compliance", "restricted");
    }

    @Test
    void isVisibleEnforcesHierarchyDefenseInDepth() {
        assertThat(builder.isVisible(ClearanceLevel.COMPLIANCE, ClearanceLevel.PUBLIC)).isTrue();
        assertThat(builder.isVisible(ClearanceLevel.COMPLIANCE, ClearanceLevel.COMPLIANCE)).isTrue();
        // a restricted item must NOT be visible to a compliance caller (a leak)
        assertThat(builder.isVisible(ClearanceLevel.COMPLIANCE, ClearanceLevel.RESTRICTED)).isFalse();
    }

    @Test
    void isVisibleByLabelFailsClosedOnUnknown() {
        assertThat(builder.isVisible(ClearanceLevel.RESTRICTED, "compliance")).isTrue();
        assertThat(builder.isVisible(ClearanceLevel.RESTRICTED, "bogus")).isFalse();
        assertThat(builder.isVisible(ClearanceLevel.PUBLIC, "restricted")).isFalse();
    }
}
