-- =====================================================================
-- Payment / finance module
--   wallets              current balance per member (balance, frozen)
--   wallet_transactions  append-only ledger: every money movement is one row
--   payment_channels     where members send money (KBZPay, Wave, bank ...)
--   deposit_requests     money in  -> needs approval
--   withdraw_requests    money out -> amount frozen until approved/rejected
--   commission_rules     % paid to inviters (1 = direct inviter, 2 = next ...)
-- =====================================================================

CREATE TYPE request_status AS ENUM ('pending', 'approved', 'rejected');
CREATE TYPE txn_type       AS ENUM ('deposit', 'withdraw', 'commission', 'adjust');

CREATE TABLE wallets (
    member_id   BIGINT PRIMARY KEY REFERENCES members(id) ON DELETE CASCADE,
    balance     NUMERIC(18,2) NOT NULL DEFAULT 0,
    frozen      NUMERIC(18,2) NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CHECK (frozen >= 0),
    CHECK (balance >= frozen)              -- can never spend frozen money
);

CREATE TABLE wallet_transactions (
    id             BIGSERIAL PRIMARY KEY,
    member_id      BIGINT        NOT NULL REFERENCES members(id),
    brand_id       INT           NOT NULL REFERENCES brands(id),
    type           txn_type      NOT NULL,
    amount         NUMERIC(18,2) NOT NULL,          -- + in, - out
    balance_after  NUMERIC(18,2) NOT NULL,
    ref_type       TEXT          NOT NULL,          -- deposit / withdraw / adjust
    ref_id         TEXT          NOT NULL,
    admin_id       INT           REFERENCES admin_users(id),
    note           TEXT,
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    -- idempotency: the same event can never be posted twice to the same wallet
    UNIQUE (ref_type, ref_id, type, member_id)
);
CREATE INDEX idx_txn_member  ON wallet_transactions (member_id, created_at DESC);
CREATE INDEX idx_txn_brand   ON wallet_transactions (brand_id, created_at DESC);

-- Ledger rows are never edited or deleted. Mistakes are fixed with a new 'adjust' row.
CREATE FUNCTION forbid_ledger_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'wallet_transactions is append-only';
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ledger_no_update BEFORE UPDATE OR DELETE ON wallet_transactions
FOR EACH ROW EXECUTE FUNCTION forbid_ledger_change();

CREATE TABLE payment_channels (
    id            SERIAL PRIMARY KEY,
    brand_id      INT           NOT NULL REFERENCES brands(id),
    name          TEXT          NOT NULL,
    type          TEXT          NOT NULL,           -- kbzpay / wavepay / bank / promptpay
    account_name  TEXT          NOT NULL,
    account_no    TEXT          NOT NULL,
    min_amount    NUMERIC(18,2) NOT NULL DEFAULT 0,
    max_amount    NUMERIC(18,2) NOT NULL DEFAULT 10000000,
    is_active     BOOLEAN       NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE deposit_requests (
    id            BIGSERIAL PRIMARY KEY,
    member_id     BIGINT         NOT NULL REFERENCES members(id),
    brand_id      INT            NOT NULL REFERENCES brands(id),
    channel_id    INT            REFERENCES payment_channels(id),
    amount        NUMERIC(18,2)  NOT NULL CHECK (amount > 0),
    reference_no  TEXT,                              -- transfer ID from KBZPay / bank slip
    proof_url     TEXT,
    status        request_status NOT NULL DEFAULT 'pending',
    request_key   TEXT           NOT NULL UNIQUE,    -- idempotency key
    note          TEXT,
    created_by    INT            REFERENCES admin_users(id),
    reviewed_by   INT            REFERENCES admin_users(id),
    reviewed_at   TIMESTAMPTZ,
    created_at    TIMESTAMPTZ    NOT NULL DEFAULT now()
);
CREATE INDEX idx_dep_brand_status ON deposit_requests (brand_id, status, created_at DESC);
CREATE INDEX idx_dep_member       ON deposit_requests (member_id);

CREATE TABLE withdraw_requests (
    id               BIGSERIAL PRIMARY KEY,
    member_id        BIGINT         NOT NULL REFERENCES members(id),
    brand_id         INT            NOT NULL REFERENCES brands(id),
    amount           NUMERIC(18,2)  NOT NULL CHECK (amount > 0),
    receive_method   TEXT           NOT NULL,        -- kbzpay / wavepay / bank
    receive_account  TEXT           NOT NULL,
    receive_name     TEXT           NOT NULL,
    payout_ref       TEXT,                           -- transfer ID after paying out
    status           request_status NOT NULL DEFAULT 'pending',
    request_key      TEXT           NOT NULL UNIQUE,
    note             TEXT,
    created_by       INT            REFERENCES admin_users(id),
    reviewed_by      INT            REFERENCES admin_users(id),
    reviewed_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT now()
);
CREATE INDEX idx_wd_brand_status ON withdraw_requests (brand_id, status, created_at DESC);
CREATE INDEX idx_wd_member       ON withdraw_requests (member_id);

CREATE TABLE commission_rules (
    brand_id   INT          NOT NULL REFERENCES brands(id),
    depth_up   INT          NOT NULL CHECK (depth_up >= 1),  -- 1 = direct inviter
    percent    NUMERIC(5,2) NOT NULL CHECK (percent >= 0 AND percent <= 100),
    PRIMARY KEY (brand_id, depth_up)
);

-- ---------- Fake channels + commission rules ----------
INSERT INTO payment_channels (brand_id, name, type, account_name, account_no, min_amount, max_amount)
SELECT b.id, c.name, c.type, 'DEMO ACCOUNT', c.no, c.min_amt, c.max_amt
FROM brands b
CROSS JOIN (VALUES
    ('KBZPay Main', 'kbzpay',  '09000000001', 1000::numeric,  5000000::numeric),
    ('WavePay',     'wavepay', '09000000002', 1000,           3000000),
    ('Bank Transfer','bank',   '000-0-00000-0', 10000,        50000000)
) AS c(name, type, no, min_amt, max_amt);

INSERT INTO commission_rules (brand_id, depth_up, percent)
SELECT b.id, r.depth_up, r.pct
FROM brands b
CROSS JOIN (VALUES (1, 2.00), (2, 1.00), (3, 0.50)) AS r(depth_up, pct);

-- Every member starts with an empty wallet
INSERT INTO wallets (member_id) SELECT id FROM members;
