package com.meridianbank.financebot.controller;

import com.meridianbank.financebot.service.ChatResult;
import com.meridianbank.financebot.service.ChatService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@CrossOrigin(origins = "*")
public class ChatController {

    private final ChatService chatService;

    public ChatController(ChatService chatService) {
        this.chatService = chatService;
    }

    @PostMapping(value = "/chat", produces = MediaType.TEXT_PLAIN_VALUE)
    public ResponseEntity<String> chat(@Valid @RequestBody ChatRequest request) {
        String userId = (request.userId() != null && !request.userId().isBlank())
                ? request.userId() : "USR001";
        ChatResult result = chatService.chat(userId, request.message(), request.history());
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-Provenance-Model-Invoked", String.valueOf(result.modelInvoked()));
        headers.set("X-Provenance-Post-Processed", String.valueOf(result.postProcessed()));
        if (result.blockReason() != null) {
            headers.set("X-Provenance-Block-Reason", result.blockReason());
        }
        if (result.postReason() != null) {
            headers.set("X-Provenance-Post-Reason", result.postReason());
        }
        return ResponseEntity.ok().headers(headers).body(result.response());
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of(
                "status", "UP",
                "service", "FinanceBot Pro",
                "bank", "Meridian Bank",
                "version", "1.0.0"
        ));
    }

    public record ChatRequest(
            @NotBlank(message = "Message cannot be blank")
            @Size(max = 4096, message = "Message too long")
            String message,

            @Size(max = 64, message = "userId too long")
            @Pattern(regexp = "^[A-Za-z0-9_-]*$", message = "userId contains invalid characters")
            String userId,

            @Size(max = 40, message = "history must not exceed 40 entries")
            List<Map<String, String>> history
    ) {}
}
