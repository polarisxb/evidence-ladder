package com.meridianbank.financebot.repository;

import com.meridianbank.financebot.model.Transaction;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface TransactionRepository extends JpaRepository<Transaction, Long> {

    @Query("SELECT t FROM Transaction t WHERE t.accountId = :accountId ORDER BY t.transactionDate DESC")
    List<Transaction> findRecentByAccountId(@Param("accountId") Long accountId, Pageable pageable);
}
