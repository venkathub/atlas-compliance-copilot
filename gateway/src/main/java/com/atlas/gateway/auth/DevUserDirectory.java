package com.atlas.gateway.auth;

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
 * Loads and holds the simulated-IdP user→clearance directory (ADR-0034). Backs {@link SimIdpController}:
 * the IdP looks up a dev user's clearance and mints it into the signed JWT. Stands in for a real IdP's
 * user store — dev/demo only.
 */
public class DevUserDirectory {

    private static final ObjectMapper JSON = new ObjectMapper();

    private final Map<String, Clearance> usersToClearance;

    public DevUserDirectory(String resourceLocation) {
        Resource res = new PathMatchingResourcePatternResolver().getResource(resourceLocation);
        Map<String, Clearance> users = new HashMap<>();
        try {
            JsonNode root = JSON.readTree(res.getInputStream());
            JsonNode userNodes = root.get("users");
            if (userNodes != null) {
                userNodes.fields().forEachRemaining(e ->
                        users.put(e.getKey(), Clearance.fromLabel(e.getValue().get("clearance").asText())));
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Failed to load IdP dev user directory " + resourceLocation, e);
        }
        this.usersToClearance = Map.copyOf(users);
    }

    /** The clearance the IdP will assert for {@code user}, or empty if the user is unknown. */
    public Optional<Clearance> clearanceFor(String user) {
        return Optional.ofNullable(user).map(usersToClearance::get);
    }
}
