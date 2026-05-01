package com.meridianbank.financebot.service;

import com.meridianbank.financebot.model.Account;
import com.meridianbank.financebot.model.FraudReport;
import com.meridianbank.financebot.model.LoanApplication;
import com.meridianbank.financebot.model.Transaction;
import com.meridianbank.financebot.repository.AccountRepository;
import com.meridianbank.financebot.repository.FraudReportRepository;
import com.meridianbank.financebot.repository.LoanApplicationRepository;
import com.meridianbank.financebot.repository.TransactionRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Service
public class BankingService {

    private static final Logger log = LoggerFactory.getLogger(BankingService.class);

    private final AccountRepository accountRepository;
    private final TransactionRepository transactionRepository;
    private final LoanApplicationRepository loanApplicationRepository;
    private final FraudReportRepository fraudReportRepository;

    public BankingService(AccountRepository accountRepository,
                          TransactionRepository transactionRepository,
                          LoanApplicationRepository loanApplicationRepository,
                          FraudReportRepository fraudReportRepository) {
        this.accountRepository = accountRepository;
        this.transactionRepository = transactionRepository;
        this.loanApplicationRepository = loanApplicationRepository;
        this.fraudReportRepository = fraudReportRepository;
    }

    @Transactional(readOnly = true)
    public List<Account> getAccountsByCustomer(String customerId) {
        log.info("[AUDIT] queryAccount called for customerId={}", customerId);
        return accountRepository.findByCustomerId(customerId);
    }

    @Transactional(readOnly = true)
    public List<Transaction> getRecentTransactions(String customerId, int limit) {
        log.info("[AUDIT] getTransactionHistory called for customerId={} limit={}", customerId, limit);
        List<Account> accounts = accountRepository.findByCustomerId(customerId);
        int cap = Math.min(Math.max(limit, 1), 20);
        return accounts.stream()
                .flatMap(acc -> transactionRepository
                        .findRecentByAccountId(acc.getId(), PageRequest.of(0, cap))
                        .stream())
                .sorted((a, b) -> b.getTransactionDate().compareTo(a.getTransactionDate()))
                .limit(cap)
                .collect(Collectors.toList());
    }

    @Transactional
    public LoanApplication submitLoanApplication(String customerId,
                                                  BigDecimal amount,
                                                  String reason,
                                                  String sessionUserId) {
        log.warn("[AUDIT] submitLoanApplication: sessionUser={} submitting for customerId={} amount={}",
                sessionUserId, customerId, amount);
        LoanApplication app = new LoanApplication();
        app.setCustomerId(customerId);
        app.setAmount(amount);
        app.setReason(reason);
        app.setStatus("PENDING");
        app.setSubmittedAt(LocalDateTime.now());
        app.setSessionUserId(sessionUserId);
        return loanApplicationRepository.save(app);
    }

    @Transactional
    public FraudReport reportFraudulentTransaction(String transactionId,
                                                    String description,
                                                    String reporterCustomerId,
                                                    String sessionUserId) {
        log.warn("[AUDIT] reportFraudulentTransaction: sessionUser={} reporter={} txn={}",
                sessionUserId, reporterCustomerId, transactionId);
        FraudReport report = new FraudReport();
        report.setTransactionId(transactionId);
        report.setReportedByCustomerId(reporterCustomerId);
        report.setDescription(description);
        report.setReportedAt(LocalDateTime.now());
        report.setStatus("UNDER_REVIEW");
        report.setSessionUserId(sessionUserId);
        return fraudReportRepository.save(report);
    }

    @Transactional(readOnly = true)
    public List<LoanApplication> getAllLoanApplications() {
        return loanApplicationRepository.findAllByOrderBySubmittedAtDesc();
    }

    @Transactional(readOnly = true)
    public List<FraudReport> getAllFraudReports() {
        return fraudReportRepository.findAllByOrderByReportedAtDesc();
    }
}
