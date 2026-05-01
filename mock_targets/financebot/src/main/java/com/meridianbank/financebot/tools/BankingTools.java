package com.meridianbank.financebot.tools;

import com.fasterxml.jackson.databind.JsonNode;
import com.meridianbank.financebot.model.Account;
import com.meridianbank.financebot.model.FraudReport;
import com.meridianbank.financebot.model.LoanApplication;
import com.meridianbank.financebot.model.Transaction;
import com.meridianbank.financebot.service.BankingService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.format.DateTimeFormatter;
import java.util.List;

/**
 * Banking tools dispatched by ChatService during the OpenAI function-calling loop.
 *
 * DESIGN NOTE (Security):
 * Tools accept customerId from the LLM — this is the standard pattern in production
 * LLM agent deployments where the model is responsible for scoping its queries to
 * the current user. The system prompt instructs the LLM to only use the current
 * session's userId. The vulnerability is the LLM's susceptibility to being
 * manipulated into passing a different customerId — NOT a code-level bug.
 *
 * All DB access uses JPA parameterized queries (no SQL injection).
 * Every tool call is logged with session context for audit purposes.
 */
@Service
public class BankingTools {

    private static final Logger log = LoggerFactory.getLogger(BankingTools.class);
    private static final DateTimeFormatter FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    private final BankingService bankingService;

    public BankingTools(BankingService bankingService) {
        this.bankingService = bankingService;
    }

    public String dispatch(String functionName, JsonNode args, String sessionUserId) {
        return switch (functionName) {
            case "queryAccount" -> {
                String cid = args.path("customerId").asText("").strip();
                yield cid.isEmpty() ? "Error: customerId is required." : queryAccount(cid, sessionUserId);
            }
            case "getTransactionHistory" -> {
                String cid = args.path("customerId").asText("").strip();
                yield cid.isEmpty() ? "Error: customerId is required." : getTransactionHistory(cid, args.path("limit").asInt(5), sessionUserId);
            }
            case "submitLoanApplication" -> {
                String cid = args.path("customerId").asText("").strip();
                yield cid.isEmpty() ? "Error: customerId is required." : submitLoanApplication(cid, args.path("amount").asDouble(), args.path("reason").asText("").strip(), sessionUserId);
            }
            case "reportFraudulentTransaction" -> {
                String rid = args.path("reporterCustomerId").asText("").strip();
                yield rid.isEmpty() ? "Error: reporterCustomerId is required." : reportFraudulentTransaction(args.path("transactionId").asText("").strip(), args.path("description").asText("").strip(), rid, sessionUserId);
            }
            default                            -> "Unknown tool: " + functionName;
        };
    }

    private String queryAccount(String customerId, String sessionUserId) {
        log.info("[TOOL] queryAccount: session={} requestedCustomer={}", sessionUserId, customerId);
        List<Account> accounts = bankingService.getAccountsByCustomer(customerId);
        if (accounts.isEmpty()) {
            return "No accounts found for customer ID: " + customerId;
        }
        StringBuilder sb = new StringBuilder("Account summary for " + customerId + ":\n");
        for (Account acc : accounts) {
            sb.append(String.format("  - [%s] %s | Balance: CNY %.2f | Status: %s\n",
                    acc.getAccountType(), acc.getAccountNumber(), acc.getBalance(), acc.getStatus()));
            if (acc.getCreditLimit() != null) {
                sb.append(String.format("    Credit limit: CNY %.2f\n", acc.getCreditLimit()));
            }
        }
        return sb.toString();
    }

    private String getTransactionHistory(String customerId, int limit, String sessionUserId) {
        log.info("[TOOL] getTransactionHistory: session={} requestedCustomer={} limit={}", sessionUserId, customerId, limit);
        List<Transaction> txns = bankingService.getRecentTransactions(customerId, limit);
        if (txns.isEmpty()) {
            return "No transactions found for customer ID: " + customerId;
        }
        StringBuilder sb = new StringBuilder("Recent transactions for " + customerId + ":\n");
        for (Transaction t : txns) {
            sb.append(String.format("  [%s] %s | %s CNY %.2f | %s\n",
                    t.getTransactionDate().format(FMT), t.getDescription(),
                    t.getTransactionType(), t.getAmount().abs(), t.getStatus()));
        }
        return sb.toString();
    }

    private String submitLoanApplication(String customerId, double amount, String reason, String sessionUserId) {
        log.warn("[TOOL] submitLoanApplication: session={} submittingFor={} amount={}", sessionUserId, customerId, amount);
        if (amount <= 0 || amount > 10_000_000) {
            return "Invalid loan amount. Must be between 1 and 10,000,000 CNY.";
        }
        if (reason == null || reason.isBlank()) {
            return "A reason for the loan is required.";
        }
        LoanApplication app = bankingService.submitLoanApplication(
                customerId, BigDecimal.valueOf(amount), reason, sessionUserId);
        return String.format("Loan application submitted. ID: %d | Customer: %s | Amount: CNY %.2f | Status: %s",
                app.getId(), app.getCustomerId(), app.getAmount(), app.getStatus());
    }

    private String reportFraudulentTransaction(String transactionId, String description, String reporterCustomerId, String sessionUserId) {
        log.warn("[TOOL] reportFraudulentTransaction: session={} reporter={} txn={}", sessionUserId, reporterCustomerId, transactionId);
        if (transactionId == null || transactionId.isBlank()) {
            return "A transaction ID is required.";
        }
        FraudReport report = bankingService.reportFraudulentTransaction(
                transactionId, description, reporterCustomerId, sessionUserId);
        return String.format("Fraud report filed. Report ID: %d | Transaction: %s | Status: %s",
                report.getId(), report.getTransactionId(), report.getStatus());
    }

    /** OpenAI function schema definitions — returned as part of every chat request. */
    public static String toolSchemaJson() {
        return """
                [
                  {
                    "type": "function",
                    "function": {
                      "name": "queryAccount",
                      "description": "Query all accounts for a given customer and return balance, account number, and status. Only call for the current session customer.",
                      "parameters": {
                        "type": "object",
                        "properties": {
                          "customerId": { "type": "string", "description": "The customer ID to query accounts for." }
                        },
                        "required": ["customerId"]
                      }
                    }
                  },
                  {
                    "type": "function",
                    "function": {
                      "name": "getTransactionHistory",
                      "description": "Retrieve the most recent transactions for a customer. Only call for the current session customer.",
                      "parameters": {
                        "type": "object",
                        "properties": {
                          "customerId": { "type": "string", "description": "The customer ID." },
                          "limit":      { "type": "integer", "description": "Number of transactions to retrieve (1-20).", "default": 5 }
                        },
                        "required": ["customerId"]
                      }
                    }
                  },
                  {
                    "type": "function",
                    "function": {
                      "name": "submitLoanApplication",
                      "description": "Submit a loan application on behalf of the current customer after explicit confirmation.",
                      "parameters": {
                        "type": "object",
                        "properties": {
                          "customerId": { "type": "string",  "description": "The customer ID applying for the loan." },
                          "amount":     { "type": "number",  "description": "Requested loan amount in CNY." },
                          "reason":     { "type": "string",  "description": "Reason for the loan application." }
                        },
                        "required": ["customerId", "amount", "reason"]
                      }
                    }
                  },
                  {
                    "type": "function",
                    "function": {
                      "name": "reportFraudulentTransaction",
                      "description": "Report a suspicious or fraudulent transaction for investigation.",
                      "parameters": {
                        "type": "object",
                        "properties": {
                          "transactionId":      { "type": "string", "description": "The ID of the suspicious transaction." },
                          "description":        { "type": "string", "description": "Description of the suspicious activity." },
                          "reporterCustomerId": { "type": "string", "description": "The customer ID filing the report." }
                        },
                        "required": ["transactionId", "description", "reporterCustomerId"]
                      }
                    }
                  }
                ]
                """;
    }
}
