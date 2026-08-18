CREATE TABLE public.users (
    id BIGINT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('analyst', 'manager')),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE public.securities (
    id BIGINT PRIMARY KEY,
    symbol TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    currency CHAR(3) NOT NULL
);

CREATE TABLE public.daily_prices (
    security_id BIGINT NOT NULL REFERENCES public.securities(id),
    price_date DATE NOT NULL,
    close NUMERIC(18, 4) NOT NULL CHECK (close > 0),
    volume BIGINT NOT NULL CHECK (volume >= 0),
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (security_id, price_date)
);

CREATE TABLE public.portfolios (
    id BIGINT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    owner_user_id BIGINT NOT NULL REFERENCES public.users(id),
    name TEXT NOT NULL,
    base_currency CHAR(3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE public.positions (
    portfolio_id BIGINT NOT NULL REFERENCES public.portfolios(id),
    security_id BIGINT NOT NULL REFERENCES public.securities(id),
    position_date DATE NOT NULL,
    quantity NUMERIC(18, 4) NOT NULL,
    market_value NUMERIC(18, 2) NOT NULL,
    PRIMARY KEY (portfolio_id, security_id, position_date)
);

CREATE TABLE public.transactions (
    id BIGINT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    portfolio_id BIGINT NOT NULL REFERENCES public.portfolios(id),
    security_id BIGINT NOT NULL REFERENCES public.securities(id),
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity NUMERIC(18, 4) NOT NULL CHECK (quantity > 0),
    price NUMERIC(18, 4) NOT NULL CHECK (price > 0),
    fee NUMERIC(18, 2) NOT NULL CHECK (fee >= 0),
    traded_at TIMESTAMPTZ NOT NULL
);
