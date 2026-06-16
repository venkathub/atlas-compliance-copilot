package com.atlas.gateway.cache;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

import org.junit.jupiter.api.Test;

class VectorsTest {

    @Test
    void cosineOfIdenticalVectorsIsOne() {
        float[] v = {1, 2, 3};
        assertThat(Vectors.cosineSimilarity(v, v)).isCloseTo(1.0, within(1e-9));
    }

    @Test
    void cosineOfOrthogonalVectorsIsZero() {
        assertThat(Vectors.cosineSimilarity(new float[] {1, 0}, new float[] {0, 1})).isCloseTo(0.0, within(1e-9));
    }

    @Test
    void zeroOrMismatchedVectorsAreZero() {
        assertThat(Vectors.cosineSimilarity(new float[] {0, 0}, new float[] {0, 0})).isZero();
        assertThat(Vectors.cosineSimilarity(new float[] {1, 2}, new float[] {1, 2, 3})).isZero();
        assertThat(Vectors.cosineSimilarity(null, new float[] {1})).isZero();
    }

    @Test
    void toBytesIsLittleEndianFloat32() {
        byte[] b = Vectors.toBytes(new float[] {1.0f});
        // IEEE-754 1.0f = 0x3F800000; little-endian byte order.
        assertThat(b).containsExactly(0x00, 0x00, (byte) 0x80, 0x3F);
    }
}
