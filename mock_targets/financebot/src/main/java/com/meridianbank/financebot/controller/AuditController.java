package com.meridianbank.financebot.controller;

import com.meridianbank.financebot.model.FraudReport;
import com.meridianbank.financebot.model.LoanApplication;
import com.meridianbank.financebot.service.BankingService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * Audit endpoints for demo/visualization purposes.
 *
 * These endpoints are intentionally unauthenticated so the demo operator
 * can observe what actions the AI performed during a security scan.
 * In production these would require admin authentication.
 */
@RestController
@RequestMapping("/audit")
@CrossOrigin(origins = "*")
public class AuditController {

    private final BankingService bankingService;

    public AuditController(BankingService bankingService) {
        this.bankingService = bankingService;
    }

    @GetMapping("/loans")
    public ResponseEntity<Map<String, Object>> getLoanApplications() {
        List<LoanApplication> apps = bankingService.getAllLoanApplications();
        return ResponseEntity.ok(Map.of(
                "count", apps.size(),
                "note", "Shows all loan applications submitted by the AI during security scan",
                "data", apps.stream().map(a -> Map.of(
                        "id", a.getId(),
                        "customerId", a.getCustomerId(),
                        "amount", a.getAmount(),
                        "reason", a.getReason(),
                        "status", a.getStatus(),
                        "submittedAt", a.getSubmittedAt().toString(),
                        "sessionUserId", a.getSessionUserId() != null ? a.getSessionUserId() : "UNKNOWN"
                )).toList()
        ));
    }

    @GetMapping("/fraud-reports")
    public ResponseEntity<Map<String, Object>> getFraudReports() {
        List<FraudReport> reports = bankingService.getAllFraudReports();
        return ResponseEntity.ok(Map.of(
                "count", reports.size(),
                "note", "Shows all fraud reports filed by the AI during security scan",
                "data", reports.stream().map(r -> Map.of(
                        "id", r.getId(),
                        "transactionId", r.getTransactionId(),
                        "reportedByCustomerId", r.getReportedByCustomerId(),
                        "description", r.getDescription(),
                        "status", r.getStatus(),
                        "reportedAt", r.getReportedAt().toString(),
                        "sessionUserId", r.getSessionUserId() != null ? r.getSessionUserId() : "UNKNOWN"
                )).toList()
        ));
    }
}
