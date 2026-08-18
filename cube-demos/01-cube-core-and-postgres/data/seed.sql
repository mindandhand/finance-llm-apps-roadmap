INSERT INTO public.users (id, tenant_id, name, role, created_at) VALUES
    (1, 'alpha', 'Alice', 'manager', '2025-01-01T09:00:00Z'),
    (2, 'alpha', 'Bob', 'analyst', '2025-01-02T09:00:00Z'),
    (3, 'beta', 'Carol', 'manager', '2025-01-03T09:00:00Z');

INSERT INTO public.securities (id, symbol, name, asset_class, currency) VALUES
    (1, '510300.SH', '沪深300ETF', 'equity_etf', 'CNY'),
    (2, '510500.SH', '中证500ETF', 'equity_etf', 'CNY'),
    (3, '511010.SH', '国债ETF', 'bond_etf', 'CNY'),
    (4, '518880.SH', '黄金ETF', 'commodity_etf', 'CNY');

INSERT INTO public.daily_prices (security_id, price_date, close, volume, updated_at) VALUES
    (1, '2025-01-02', 3.9500, 1200000, '2025-01-02T15:30:00Z'),
    (1, '2025-01-03', 4.0000, 1350000, '2025-01-03T15:30:00Z'),
    (2, '2025-01-02', 5.8000, 900000, '2025-01-02T15:30:00Z'),
    (2, '2025-01-03', 5.7500, 880000, '2025-01-03T15:30:00Z'),
    (3, '2025-01-02', 101.2000, 120000, '2025-01-02T15:30:00Z'),
    (3, '2025-01-03', 101.3500, 115000, '2025-01-03T15:30:00Z'),
    (4, '2025-01-02', 5.6200, 480000, '2025-01-02T15:30:00Z'),
    (4, '2025-01-03', 5.7000, 510000, '2025-01-03T15:30:00Z');

INSERT INTO public.portfolios (id, tenant_id, owner_user_id, name, base_currency, created_at) VALUES
    (1, 'alpha', 1, 'Alpha Growth', 'CNY', '2025-01-01T10:00:00Z'),
    (2, 'alpha', 2, 'Alpha Balanced', 'CNY', '2025-01-01T10:00:00Z'),
    (3, 'beta', 3, 'Beta Reserve', 'CNY', '2025-01-01T10:00:00Z');

INSERT INTO public.positions (portfolio_id, security_id, position_date, quantity, market_value) VALUES
    (1, 1, '2025-01-03', 10000, 40000.00),
    (1, 2, '2025-01-03', 5000, 28750.00),
    (2, 1, '2025-01-03', 4000, 16000.00),
    (2, 3, '2025-01-03', 300, 30405.00),
    (3, 3, '2025-01-03', 500, 50675.00),
    (3, 4, '2025-01-03', 6000, 34200.00);

INSERT INTO public.transactions (
    id, tenant_id, portfolio_id, security_id, side, quantity, price, fee, traded_at
) VALUES
    (1, 'alpha', 1, 1, 'buy', 6000, 3.9000, 5.00, '2025-01-02T02:00:00Z'),
    (2, 'alpha', 1, 1, 'buy', 4000, 3.9500, 5.00, '2025-01-03T02:00:00Z'),
    (3, 'alpha', 1, 2, 'buy', 5000, 5.7000, 8.00, '2025-01-03T02:10:00Z'),
    (4, 'alpha', 2, 1, 'buy', 4000, 3.9800, 4.00, '2025-01-03T02:20:00Z'),
    (5, 'alpha', 2, 3, 'buy', 300, 101.1000, 3.00, '2025-01-03T02:30:00Z'),
    (6, 'beta', 3, 3, 'buy', 500, 101.0000, 5.00, '2025-01-02T02:00:00Z'),
    (7, 'beta', 3, 4, 'buy', 7000, 5.6000, 7.00, '2025-01-02T02:10:00Z'),
    (8, 'beta', 3, 4, 'sell', 1000, 5.7000, 2.00, '2025-01-03T02:10:00Z');
