package com.meridianbank.financebot.model;

import jakarta.persistence.*;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.time.LocalDateTime;

@Entity
@Table(name = "fraud_report")
public class FraudReport {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Column(name = "transaction_id", nullable = false, length = 64)
    private String transactionId;

    @NotBlank
    @Column(name = "reported_by_customer_id", nullable = false, length = 32)
    private String reportedByCustomerId;

    @NotBlank
    @Column(name = "description", nullable = false, length = 1024)
    private String description;

    @NotNull
    @Column(name = "reported_at", nullable = false)
    private LocalDateTime reportedAt;

    @NotBlank
    @Column(name = "status", nullable = false, length = 16)
    private String status;

    @Column(name = "session_user_id", length = 32)
    private String sessionUserId;

    public FraudReport() {}

    public Long getId() { return id; }
    public String getTransactionId() { return transactionId; }
    public String getReportedByCustomerId() { return reportedByCustomerId; }
    public String getDescription() { return description; }
    public LocalDateTime getReportedAt() { return reportedAt; }
    public String getStatus() { return status; }
    public String getSessionUserId() { return sessionUserId; }

    public void setId(Long id) { this.id = id; }
    public void setTransactionId(String transactionId) { this.transactionId = transactionId; }
    public void setReportedByCustomerId(String reportedByCustomerId) { this.reportedByCustomerId = reportedByCustomerId; }
    public void setDescription(String description) { this.description = description; }
    public void setReportedAt(LocalDateTime reportedAt) { this.reportedAt = reportedAt; }
    public void setStatus(String status) { this.status = status; }
    public void setSessionUserId(String sessionUserId) { this.sessionUserId = sessionUserId; }
}
