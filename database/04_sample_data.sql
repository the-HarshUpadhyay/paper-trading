-- ============================================================
--  Paper Trading Platform — Oracle 19c / XE
--  04_sample_data.sql  |  Seed data for development / demo
-- ============================================================

-- Demo user  (password = "demo1234" bcrypt-hashed — app layer hashes, this is placeholder)
INSERT INTO users (username, email, password_hash, balance)
VALUES ('demo_trader', 'demo@papertrading.com',
        '$2b$12$demoHashPlaceholderReplaceWithRealBcryptHash', 100000.00);

-- Stock catalogue seed (frequently searched tickers)
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('AAPL',  'Apple Inc.',                    'Technology',       'NASDAQ');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('MSFT',  'Microsoft Corporation',         'Technology',       'NASDAQ');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('GOOGL', 'Alphabet Inc.',                 'Technology',       'NASDAQ');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('AMZN',  'Amazon.com Inc.',               'Consumer Cyclical','NASDAQ');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('META',  'Meta Platforms Inc.',           'Technology',       'NASDAQ');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('TSLA',  'Tesla Inc.',                    'Automotive',       'NASDAQ');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('NVDA',  'NVIDIA Corporation',            'Technology',       'NASDAQ');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('JPM',   'JPMorgan Chase & Co.',          'Financial',        'NYSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('JNJ',   'Johnson & Johnson',             'Healthcare',       'NYSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('V',     'Visa Inc.',                     'Financial',        'NYSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('WMT',   'Walmart Inc.',                  'Consumer Defensive','NYSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('XOM',   'Exxon Mobil Corporation',       'Energy',           'NYSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('UNH',   'UnitedHealth Group Inc.',       'Healthcare',       'NYSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('MA',    'Mastercard Incorporated',       'Financial',        'NYSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('HD',    'The Home Depot Inc.',           'Consumer Cyclical','NYSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('PG',    'Procter & Gamble Co.',          'Consumer Defensive','NYSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('BAC',   'Bank of America Corp.',         'Financial',        'NYSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('DIS',   'The Walt Disney Company',       'Communication',    'NYSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('NFLX',  'Netflix Inc.',                  'Communication',    'NASDAQ');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('PYPL',  'PayPal Holdings Inc.',          'Financial',        'NASDAQ');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('ADBE',  'Adobe Inc.',                    'Technology',       'NASDAQ');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('CRM',   'Salesforce Inc.',               'Technology',       'NYSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('INTC',  'Intel Corporation',             'Technology',       'NASDAQ');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('AMD',   'Advanced Micro Devices Inc.',   'Technology',       'NASDAQ');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('SPOT',  'Spotify Technology S.A.',       'Communication',    'NYSE');

COMMIT;

PROMPT Sample data inserted successfully.
PROMPT Default paper-trading balance: $100,000
