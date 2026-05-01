package com.meridianbank.financebot.model;

import jakarta.persistence.*;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "transaction")
public class Transaction {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotNull
    @Column(name = "account_id", nullable = false)
    private Long accountId;

    @NotNull
    @Column(name = "amount", nullable = false, precision = 18, scale = 2)
    private BigDecimal amount;

    @NotBlank
    @Column(name = "description", nullable = false, length = 256)
    private String description;

    @NotNull
    @Column(name = "transaction_date", nullable = false)
    private LocalDateTime transactionDate;

    @NotBlank
    @Column(name = "transaction_type", nullable = false, length = 16)
    private String transactionType;

    @NotBlank
    @Column(name = "status", nullable = false, length = 16)
    private String status;

    public Transaction() {}

    public Long getId() { return id; }
    public Long getAccountId() { return accountId; }
    public BigDecimal getAmount() { return amount; }
    public String getDescription() { return description; }
    public LocalDateTime getTransactionDate() { return transactionDate; }
    public String getTransactionType() { return transactionType; }
    public String getStatus() { return status; }

    public void setId(Long id) { this.id = id; }
    public void setAccountId(Long accountId) { this.accountId = accountId; }
    public void setAmount(BigDecimal amount) { this.amount = amount; }
    public void setDescription(String description) { this.description = description; }
    public void setTransactionDate(LocalDateTime transactionDate) { this.transactionDate = transactionDate; }
    public void setTransactionType(String transactionType) { this.transactionType = transactionType; }
    public void setStatus(String status) { this.status = status; }
}
