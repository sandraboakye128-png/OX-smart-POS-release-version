CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    brand TEXT,
    cost_price REAL,
    selling_price REAL,
    stock INTEGER
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    quantity INTEGER,
    total REAL,
    profit REAL,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);