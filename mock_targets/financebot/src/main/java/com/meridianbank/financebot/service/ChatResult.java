package com.meridianbank.financebot.service;

/**
 * Structured result from ChatService carrying provenance metadata
 * alongside the response text.
 */
public record ChatResult(
        String response,
        boolean modelInvoked,
        boolean postProcessed,
        String blockReason,
        String postReason
) {
    /** Convenience factory: model was called, response returned as-is. */
    public static ChatResult model(String response) {
        return new ChatResult(response, true, false, null, null);
    }

    /** Convenience factory: model was called but output was rewritten. */
    public static ChatResult postProcessed(String response, String postReason) {
        return new ChatResult(response, true, true, null, postReason);
    }

    /** Convenience factory: model was NOT called, blocked before invocation. */
    public static ChatResult blocked(String response, String blockReason) {
        return new ChatResult(response, false, false, blockReason, null);
    }
}
