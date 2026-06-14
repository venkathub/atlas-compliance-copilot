package com.atlas.ragengine.observability;

import io.micrometer.common.KeyValues;
import io.micrometer.observation.Observation;
import io.micrometer.observation.ObservationHandler;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;

/**
 * In-memory observation recorder for tracing tests — the offline stand-in for an OTel span exporter
 * (no live Langfuse needed in CI, per D-P2 §4.2). Captures each finished span's name + key-values so
 * tests can assert the span tree, attributes, and (crucially) that no chunk text / PII leaked.
 */
public class RecordingObservationHandler implements ObservationHandler<Observation.Context> {

    public record Recorded(String name, KeyValues low, KeyValues high) {

        public String value(String key) {
            return Stream.concat(low.stream(), high.stream())
                    .filter(kv -> kv.getKey().equals(key))
                    .map(io.micrometer.common.KeyValue::getValue)
                    .findFirst()
                    .orElse(null);
        }

        public boolean anyValueContains(String needle) {
            return Stream.concat(low.stream(), high.stream())
                    .anyMatch(kv -> kv.getValue() != null && kv.getValue().contains(needle));
        }
    }

    public final List<Recorded> recorded = new ArrayList<>();

    @Override
    public boolean supportsContext(Observation.Context context) {
        return true;
    }

    @Override
    public void onStop(Observation.Context context) {
        recorded.add(new Recorded(
                context.getName(),
                context.getLowCardinalityKeyValues(),
                context.getHighCardinalityKeyValues()));
    }

    public Recorded byName(String name) {
        return recorded.stream().filter(r -> r.name().equals(name)).findFirst().orElse(null);
    }
}
