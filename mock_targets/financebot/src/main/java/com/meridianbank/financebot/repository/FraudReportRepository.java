package com.meridianbank.financebot.repository;

import com.meridianbank.financebot.model.FraudReport;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface FraudReportRepository extends JpaRepository<FraudReport, Long> {

    List<FraudReport> findAllByOrderByReportedAtDesc();
}
