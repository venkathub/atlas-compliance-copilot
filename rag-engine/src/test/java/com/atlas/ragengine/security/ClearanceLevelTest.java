package com.atlas.ragengine.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

class ClearanceLevelTest {

    @Test
    void isStrictlyOrdered() {
        assertThat(ClearanceLevel.PUBLIC.rank()).isLessThan(ClearanceLevel.ANALYST.rank());
        assertThat(ClearanceLevel.ANALYST.rank()).isLessThan(ClearanceLevel.COMPLIANCE.rank());
        assertThat(ClearanceLevel.COMPLIANCE.rank()).isLessThan(ClearanceLevel.RESTRICTED.rank());
    }

    @Test
    void dominatesIsHierarchical() {
        assertThat(ClearanceLevel.COMPLIANCE.dominates(ClearanceLevel.PUBLIC)).isTrue();
        assertThat(ClearanceLevel.COMPLIANCE.dominates(ClearanceLevel.COMPLIANCE)).isTrue();
        assertThat(ClearanceLevel.COMPLIANCE.dominates(ClearanceLevel.RESTRICTED)).isFalse();
        assertThat(ClearanceLevel.PUBLIC.dominates(ClearanceLevel.ANALYST)).isFalse();
    }

    @Test
    void atOrBelowReturnsVisibleSetPerLevel() {
        assertThat(ClearanceLevel.PUBLIC.atOrBelow()).containsExactly(ClearanceLevel.PUBLIC);
        assertThat(ClearanceLevel.ANALYST.atOrBelow())
                .containsExactly(ClearanceLevel.PUBLIC, ClearanceLevel.ANALYST);
        assertThat(ClearanceLevel.COMPLIANCE.atOrBelow())
                .containsExactly(ClearanceLevel.PUBLIC, ClearanceLevel.ANALYST, ClearanceLevel.COMPLIANCE);
        assertThat(ClearanceLevel.RESTRICTED.atOrBelow())
                .containsExactly(ClearanceLevel.values());
    }

    @Test
    void visibleLabelsAreLowercaseDbLabels() {
        assertThat(ClearanceLevel.COMPLIANCE.visibleLabels())
                .containsExactly("public", "analyst", "compliance");
    }

    @Test
    void fromLabelIsCaseInsensitive() {
        assertThat(ClearanceLevel.fromLabel("compliance")).isEqualTo(ClearanceLevel.COMPLIANCE);
        assertThat(ClearanceLevel.fromLabel("  RESTRICTED ")).isEqualTo(ClearanceLevel.RESTRICTED);
    }

    @Test
    void fromLabelRejectsUnknown() {
        assertThatThrownBy(() -> ClearanceLevel.fromLabel("top-secret"))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> ClearanceLevel.fromLabel(null))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
