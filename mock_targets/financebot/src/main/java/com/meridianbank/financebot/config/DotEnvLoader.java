package com.meridianbank.financebot.config;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;

/**
 * Loads .env files into Spring Environment before bean initialization.
 * Priority: system env vars > local .env > project root .env > application.yml defaults.
 */
public class DotEnvLoader implements EnvironmentPostProcessor {

    @Override
    public void postProcessEnvironment(ConfigurableEnvironment environment, SpringApplication application) {
        Map<String, Object> merged = new HashMap<>();

        Path rootEnv = findProjectRoot();
        if (rootEnv != null) {
            merged.putAll(parseEnvFile(rootEnv.resolve(".env")));
        }
        merged.putAll(parseEnvFile(Paths.get(".env")));

        if (!merged.isEmpty()) {
            environment.getPropertySources()
                    .addLast(new MapPropertySource("dotenv", merged));
        }
    }

    private Path findProjectRoot() {
        Path dir = Paths.get("").toAbsolutePath();
        while (dir != null) {
            if (Files.isDirectory(dir.resolve("backend"))
                    && Files.isDirectory(dir.resolve("mock_targets"))) {
                return dir;
            }
            dir = dir.getParent();
        }
        return null;
    }

    private Map<String, Object> parseEnvFile(Path path) {
        Map<String, Object> props = new HashMap<>();
        if (!Files.isRegularFile(path)) return props;
        try {
            for (String line : Files.readAllLines(path)) {
                String trimmed = line.trim();
                if (trimmed.isEmpty() || trimmed.startsWith("#")) continue;
                int idx = trimmed.indexOf('=');
                if (idx == -1) continue;
                String key = trimmed.substring(0, idx).trim();
                String value = trimmed.substring(idx + 1).trim()
                        .replaceAll("^[\"']|[\"']$", "");
                if (!key.isEmpty()) {
                    props.put(key, value);
                }
            }
        } catch (IOException ignored) {
        }
        return props;
    }
}
