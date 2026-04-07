-- ============================================================
--  Paper Trading Platform — Oracle 19c / XE
--  04_sample_data.sql  |  Seed data for development / demo
-- ============================================================

-- Demo user  (password = "demo1234" bcrypt-hashed — app layer hashes, this is placeholder)
INSERT INTO users (username, email, password_hash, balance)
VALUES ('demo_trader', 'demo@papertrading.com',
        '$2b$12$demoHashPlaceholderReplaceWithRealBcryptHash', 1000000.00);

-- Stock catalogue seed — Nifty 50 / popular NSE-listed Indian stocks
-- Tickers use the .NS suffix (NSE) as required by yfinance
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('RELIANCE.NS',   'Reliance Industries Ltd.',          'Energy',              'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('TCS.NS',        'Tata Consultancy Services Ltd.',    'Technology',          'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('HDFCBANK.NS',   'HDFC Bank Ltd.',                    'Financial Services',  'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('INFY.NS',       'Infosys Ltd.',                      'Technology',          'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('ICICIBANK.NS',  'ICICI Bank Ltd.',                   'Financial Services',  'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('HINDUNILVR.NS', 'Hindustan Unilever Ltd.',           'Consumer Staples',    'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('SBIN.NS',       'State Bank of India',               'Financial Services',  'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('BAJFINANCE.NS', 'Bajaj Finance Ltd.',                'Financial Services',  'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('BHARTIARTL.NS', 'Bharti Airtel Ltd.',                'Communication',       'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('KOTAKBANK.NS',  'Kotak Mahindra Bank Ltd.',          'Financial Services',  'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('LT.NS',         'Larsen & Toubro Ltd.',              'Industrials',         'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('WIPRO.NS',      'Wipro Ltd.',                        'Technology',          'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('HCLTECH.NS',    'HCL Technologies Ltd.',             'Technology',          'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('AXISBANK.NS',   'Axis Bank Ltd.',                    'Financial Services',  'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('ITC.NS',        'ITC Ltd.',                          'Consumer Staples',    'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('MARUTI.NS',     'Maruti Suzuki India Ltd.',          'Automotive',          'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('TITAN.NS',      'Titan Company Ltd.',                'Consumer Discretionary','NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('SUNPHARMA.NS',  'Sun Pharmaceutical Industries Ltd.','Healthcare',          'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('TATAMOTORS.NS', 'Tata Motors Ltd.',                  'Automotive',          'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('ULTRACEMCO.NS', 'UltraTech Cement Ltd.',             'Materials',           'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('ASIANPAINT.NS', 'Asian Paints Ltd.',                 'Materials',           'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('NESTLEIND.NS',  'Nestle India Ltd.',                 'Consumer Staples',    'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('BAJAJFINSV.NS', 'Bajaj Finserv Ltd.',                'Financial Services',  'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('ONGC.NS',       'Oil & Natural Gas Corporation Ltd.','Energy',              'NSE');
INSERT INTO stocks (ticker, company_name, sector, exchange) VALUES ('TATASTEEL.NS',  'Tata Steel Ltd.',                   'Materials',           'NSE');

COMMIT;

PROMPT Sample data inserted successfully.
PROMPT Default paper-trading balance: Rs.10,00,000
