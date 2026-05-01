package com.meridianbank.financebot.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.meridianbank.financebot.tools.BankingTools;
import okhttp3.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/**
 * Orchestrates the OpenAI-compatible chat + function-calling loop.
 *
 * Flow:
 *   1. Build messages array (system + history + user message)
 *   2. POST to /chat/completions with tool schemas
 *   3. If the LLM requests tool calls → execute via BankingTools → append results → repeat
 *   4. When LLM returns a text response → return it as plain text
 *
 * The function-calling loop runs up to MAX_TOOL_ROUNDS iterations to prevent infinite loops.
 */
@Service
public class ChatService {

    private static final Logger log = LoggerFactory.getLogger(ChatService.class);
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");
    private static final int MAX_TOOL_ROUNDS = 6;

    private final OkHttpClient httpClient;
    private final BankingTools bankingTools;
    private final ObjectMapper mapper;

    @Value("${spring.ai.openai.api-key}")
    private String apiKey;

    @Value("${spring.ai.openai.base-url:https://api.openai.com/v1}")
    private String baseUrl;

    @Value("${spring.ai.openai.chat.options.model:gpt-4o}")
    private String model;

    @Value("classpath:prompts/system.txt")
    private Resource systemPromptResource;

    public ChatService(OkHttpClient httpClient, BankingTools bankingTools, ObjectMapper mapper) {
        this.httpClient = httpClient;
        this.bankingTools = bankingTools;
        this.mapper = mapper;
    }

    public ChatResult chat(String userId, String userMessage, List<Map<String, String>> history) {
        try {
            String systemPrompt = buildSystemPrompt(userId);
            ArrayNode messages = mapper.createArrayNode();

            ObjectNode sysMsg = mapper.createObjectNode();
            sysMsg.put("role", "system");
            sysMsg.put("content", systemPrompt);
            messages.add(sysMsg);

            if (history != null) {
                int start = Math.max(0, history.size() - 20);
                for (int i = start; i < history.size(); i++) {
                    Map<String, String> turn = history.get(i);
                    String role = turn.getOrDefault("role", "");
                    String content = turn.getOrDefault("content", "");
                    if ("user".equalsIgnoreCase(role) || "assistant".equalsIgnoreCase(role)) {
                        ObjectNode msg = mapper.createObjectNode();
                        msg.put("role", role.toLowerCase());
                        msg.put("content", content);
                        messages.add(msg);
                    }
                }
            }

            ObjectNode userMsg = mapper.createObjectNode();
            userMsg.put("role", "user");
            userMsg.put("content", userMessage);
            messages.add(userMsg);

            JsonNode tools = mapper.readTree(BankingTools.toolSchemaJson());

            for (int round = 0; round < MAX_TOOL_ROUNDS; round++) {
                ObjectNode requestBody = mapper.createObjectNode();
                requestBody.put("model", model);
                requestBody.set("messages", messages);
                requestBody.set("tools", tools);
                requestBody.put("temperature", 0.3);
                requestBody.put("max_tokens", 1024);

                String responseJson = post(requestBody.toString());
                JsonNode root = mapper.readTree(responseJson);
                JsonNode choice = root.path("choices").path(0);
                JsonNode assistantMsg = choice.path("message");
                String finishReason = choice.path("finish_reason").asText("");

                if ("tool_calls".equals(finishReason)) {
                    messages.add(assistantMsg);

                    JsonNode toolCalls = assistantMsg.path("tool_calls");
                    for (JsonNode tc : toolCalls) {
                        String callId = tc.path("id").asText();
                        String funcName = tc.path("function").path("name").asText();
                        JsonNode funcArgs = mapper.readTree(tc.path("function").path("arguments").asText("{}"));

                        log.info("[FC] round={} function={} args={}", round, funcName, funcArgs);
                        String toolResult = bankingTools.dispatch(funcName, funcArgs, userId);

                        ObjectNode toolMsg = mapper.createObjectNode();
                        toolMsg.put("role", "tool");
                        toolMsg.put("tool_call_id", callId);
                        toolMsg.put("content", toolResult);
                        messages.add(toolMsg);
                    }
                } else {
                    JsonNode contentNode = assistantMsg.path("content");
                    String content = (contentNode.isNull() || contentNode.isMissingNode())
                            ? "" : contentNode.asText("").strip();
                    log.info("[CHAT] userId={} rounds={} response_length={} finishReason={}", userId, round, content.length(), finishReason);
                    if (content.isEmpty()) {
                        log.warn("[CHAT] LLM returned empty/null content for userId={} finishReason={}", userId, finishReason);
                        return ChatResult.postProcessed(
                                "I'm sorry, I couldn't generate a response. Please rephrase your question.",
                                "format_enforcement");
                    }
                    return ChatResult.model(content);
                }
            }

            return ChatResult.postProcessed(
                    "Request processed. Please contact support if you need further assistance.",
                    "tool_rewrite");

        } catch (Exception e) {
            log.error("[CHAT] Error for userId={}: {}", userId, e.getMessage(), e);
            return new ChatResult(
                    "I'm experiencing technical difficulties. Please contact our support line.",
                    false, true, null, "error_fallback");
        }
    }

    private String post(String json) throws IOException {
        String url = baseUrl.replaceAll("/+$", "") + "/chat/completions";
        Request request = new Request.Builder()
                .url(url)
                .addHeader("Authorization", "Bearer " + apiKey)
                .addHeader("Content-Type", "application/json")
                .post(RequestBody.create(json, JSON))
                .build();
        try (Response response = httpClient.newCall(request).execute()) {
            ResponseBody body = response.body();
            String bodyText = body != null ? body.string() : "";
            if (!response.isSuccessful()) {
                throw new IOException("LLM API error " + response.code() + ": " + bodyText);
            }
            return bodyText;
        }
    }

    private String buildSystemPrompt(String userId) {
        try {
            String template = systemPromptResource.getContentAsString(StandardCharsets.UTF_8);
            return template
                    .replace("{userId}", userId)
                    .replace("{date}", LocalDate.now().toString());
        } catch (IOException e) {
            log.error("Failed to load system prompt: {}", e.getMessage());
            return "You are FinanceBot Pro, Meridian Bank's AI customer service assistant. "
                    + "Current customer: " + userId + ". Only service requests for this customer.";
        }
    }
}
