package com.atlas.ragengine.security;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

/**
 * Loads and holds the D3 dev user→clearance map (ADR-0016). Backs {@link ClearanceResolver}.
 * <b>P1-only shim</b>; the simulated IdP in P3 replaces this with a verifiable claim.
 */
public class DevClearanceDirectory {

    private static final ObjectMapper JSON = new ObjectMapper();

    private final Map<String, ClearanceLevel> usersToClearance;
    private final ClearanceLevel defaultClearance;

    public DevClearanceDirectory(String resourceLocation, ClearanceLevel fallbackDefault) {
        Resource res = new PathMatchingResourcePatternResolver().getResource(resourceLocation);
        Map<String, ClearanceLevel> users = new HashMap<>();
        ClearanceLevel def = fallbackDefault;
        try {
            JsonNode root = JSON.readTree(res.getInputStream());
            if (root.hasNonNull("default_clearance")) {
                def = ClearanceLevel.fromLabel(root.get("default_clearance").asText());
            }
            JsonNode userNodes = root.get("users");
            if (userNodes != null) {
                userNodes.fields().forEachRemaining(e ->
                        users.put(e.getKey(), ClearanceLevel.fromLabel(e.getValue().get("clearance").asText())));
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Failed to load dev clearance map " + resourceLocation, e);
        }
        this.usersToClearance = Map.copyOf(users);
        this.defaultClearance = def;
    }

    public Optional<ClearanceLevel> clearanceFor(String user) {
        return Optional.ofNullable(user).map(usersToClearance::get);
    }

    public ClearanceLevel defaultClearance() {
        return defaultClearance;
    }
}
