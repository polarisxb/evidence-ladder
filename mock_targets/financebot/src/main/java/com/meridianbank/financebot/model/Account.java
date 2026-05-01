package com.meridianbank.financebot.model;

import jakarta.persistence.*;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;

@Entity
@Table(name = "account")
public class Account {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Column(name = "customer_id", nullable = false, length = 32)
    private String customerId;

    @NotBlank
    @Column(name = "account_number", nullable = false, unique = true, length = 32)
    private String accountNumber;

    @NotBlank
    @Column(name = "account_type", nullable = false, length = 16)
    private String accountType;

    @NotNull
    @Column(name = "balance", nullable = false, precision = 18, scale = 2)
    private BigDecimal balance;

    @Column(name = "credit_limit", precision = 18, scale = 2)
    private BigDecimal creditLimit;

    @NotBlank
    @Column(name = "status", nullable = false, length = 16)
    private String status;

    public Account() {}

    public Long getId() { return id; }
    public String getCustomerId() { return customerId; }
    public String getAccountNumber() { return accountNumber; }
    public String getAccountType() { return accountType; }
    public BigDecimal getBalance() { return balance; }
    public BigDecimal getCreditLimit() { return creditLimit; }
    public String getStatus() { return status; }

    public void setId(Long id) { this.id = id; }
    public void setCustomerId(String customerId) { this.customerId = customerId; }
    public void setAccountNumber(String accountNumber) { this.accountNumber = accountNumber; }
    public void setAccountType(String accountType) { this.accountType = accountType; }
    public void setBalance(BigDecimal balance) { this.balance = balance; }
    public void setCreditLimit(BigDecimal creditLimit) { this.creditLimit = creditLimit; }
    public void setStatus(String status) { this.status = status; }
}
