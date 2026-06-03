-- ─────────────────────────────────────────
-- schema.sql
-- Run this in Supabase SQL editor to create all tables
-- ─────────────────────────────────────────


-- 1. Portfolio Table
-- Tracks current cash and holdings
CREATE TABLE IF NOT EXISTS portfolio (
    id              SERIAL PRIMARY KEY,
    cash            DECIMAL(12, 2)  NOT NULL DEFAULT 10000.00,
    total_value     DECIMAL(12, 2),
    last_updated    TIMESTAMP       DEFAULT NOW()
);

-- Insert starting portfolio (run once)
INSERT INTO portfolio (cash, total_value) VALUES (10000.00, 10000.00);


-- 2. Holdings Table
-- Tracks which stocks are currently owned
CREATE TABLE IF NOT EXISTS holdings (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10)     NOT NULL UNIQUE,
    shares          DECIMAL(10, 4)  NOT NULL,
    avg_buy_price   DECIMAL(10, 2)  NOT NULL,
    current_price   DECIMAL(10, 2),
    total_value     DECIMAL(12, 2),
    profit_loss     DECIMAL(12, 2),
    last_updated    TIMESTAMP       DEFAULT NOW()
);


-- 3. Stock Prices Table
-- Price snapshot saved 4x daily
CREATE TABLE IF NOT EXISTS stock_prices (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10)     NOT NULL,
    price           DECIMAL(10, 2)  NOT NULL,
    change_pct      DECIMAL(6, 2),
    volume          BIGINT,
    recorded_at     TIMESTAMP       DEFAULT NOW()
);


-- 4. Trades History Table
-- Every BUY and SELL logged here
CREATE TABLE IF NOT EXISTS trades_history (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10)     NOT NULL,
    action          VARCHAR(4)      NOT NULL CHECK (action IN ('BUY', 'SELL')),
    shares          DECIMAL(10, 4)  NOT NULL,
    price           DECIMAL(10, 2)  NOT NULL,
    total_value     DECIMAL(12, 2)  NOT NULL,
    profit_loss     DECIMAL(12, 2),
    reasoning       TEXT,
    executed_at     TIMESTAMP       DEFAULT NOW()
);


-- 5. Portfolio Added Table
-- Logs when a stock is added to portfolio
CREATE TABLE IF NOT EXISTS portfolio_added (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10)     NOT NULL,
    shares          DECIMAL(10, 4)  NOT NULL,
    buy_price       DECIMAL(10, 2)  NOT NULL,
    total_cost      DECIMAL(12, 2)  NOT NULL,
    reason          TEXT,
    added_at        TIMESTAMP       DEFAULT NOW()
);


-- 6. Portfolio Removed Table
-- Logs when a stock is removed from portfolio
CREATE TABLE IF NOT EXISTS portfolio_removed (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10)     NOT NULL,
    shares          DECIMAL(10, 4)  NOT NULL,
    sell_price      DECIMAL(10, 2)  NOT NULL,
    total_value     DECIMAL(12, 2)  NOT NULL,
    profit_loss     DECIMAL(12, 2),
    reason          TEXT,
    removed_at      TIMESTAMP       DEFAULT NOW()
);


-- 7. Watchlist Table
-- Good and bad stocks flagged by agent
CREATE TABLE IF NOT EXISTS watchlist (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10)     NOT NULL UNIQUE,
    status          VARCHAR(4)      NOT NULL CHECK (status IN ('GOOD', 'BAD')),
    reason          TEXT,
    confidence      INTEGER,
    last_updated    TIMESTAMP       DEFAULT NOW()
);


-- 8. Agent Decisions Log Table
-- Full reasoning trace for every agent decision
CREATE TABLE IF NOT EXISTS agent_decisions_log (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10)     NOT NULL,
    action          VARCHAR(4)      NOT NULL CHECK (action IN ('BUY', 'SELL', 'HOLD')),
    confidence      INTEGER,
    reasoning       TEXT,
    risk_level      VARCHAR(6)      CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
    decided_at      TIMESTAMP       DEFAULT NOW()
);
