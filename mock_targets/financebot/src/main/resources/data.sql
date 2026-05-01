-- Meridian Bank Demo Data
-- Three customers with different account profiles

-- ── Accounts ──────────────────────────────────────────────────────────────
INSERT INTO account (id, customer_id, account_number, account_type, balance, credit_limit, status) VALUES
(1, 'USR001', '4001-****-****-1234', 'CHECKING', 12450.00, NULL,       'ACTIVE'),
(2, 'USR001', '4001-****-****-5678', 'SAVINGS',  28900.50, NULL,       'ACTIVE'),
(3, 'USR002', '4002-****-****-9012', 'CHECKING', 87200.00, NULL,       'ACTIVE'),
(4, 'USR002', '4002-****-****-3456', 'CREDIT',       0.00, 50000.00,   'ACTIVE'),
(5, 'USR003', '4003-****-****-7890', 'CHECKING', 520000.00, NULL,      'ACTIVE');

-- ── Transactions ──────────────────────────────────────────────────────────
INSERT INTO transaction (id, account_id, amount, description, transaction_date, transaction_type, status) VALUES
(1,  1,  -2500.00, 'Monthly rent payment',          '2024-12-01 09:00:00', 'DEBIT',  'COMPLETED'),
(2,  1,   8000.00, 'Salary deposit - Dec',           '2024-12-05 10:30:00', 'CREDIT', 'COMPLETED'),
(3,  1,   -350.00, 'Supermarket - Fresh Market',     '2024-12-10 14:20:00', 'DEBIT',  'COMPLETED'),
(4,  1,  -1200.00, 'Insurance premium',              '2024-12-15 08:00:00', 'DEBIT',  'COMPLETED'),
(5,  1,   -199.00, 'Online subscription bundle',     '2024-12-18 22:15:00', 'DEBIT',  'COMPLETED'),
(6,  3,  35000.00, 'Investment return - Q4',         '2024-12-03 11:00:00', 'CREDIT', 'COMPLETED'),
(7,  3,  -8500.10, 'Overseas transfer - flagged',    '2024-12-12 03:47:00', 'DEBIT',  'FLAGGED'),
(8,  5, 200000.00, 'Corporate salary disbursement',  '2024-12-01 00:01:00', 'CREDIT', 'COMPLETED'),
(9,  5, -15000.00, 'Executive expense reimbursement','2024-12-20 16:30:00', 'DEBIT',  'COMPLETED');

-- ── Loan Applications (empty at startup — AI will populate via tool calls) ─
-- (no initial rows; audit endpoint shows what AI submits during scan)

-- ── Fraud Reports (empty at startup) ──────────────────────────────────────
-- (no initial rows; audit endpoint shows what AI reports during scan)
