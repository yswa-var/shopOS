
-- PostgreSQL 14+
-- Migration 001: normalized purchase bills
BEGIN;

CREATE TABLE vendors (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL CHECK (btrim(name) <> ''),
    address text,
    phone_number varchar(20),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL CHECK (btrim(name) <> ''),
    unit text NOT NULL CHECK (btrim(unit) <> ''), -- e.g. kg, g, piece; shared purchase/sell unit
    purchase_price numeric(14,2) NOT NULL DEFAULT 0 CHECK (purchase_price >= 0),
    sell_price numeric(14,2) CHECK (sell_price >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE bills (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vendor_id bigint NOT NULL REFERENCES vendors(id) ON DELETE RESTRICT,
    due_date date NOT NULL,
    document_url text NOT NULL CHECK (btrim(document_url) <> ''),
    is_paid boolean NOT NULL DEFAULT false,
    paid_at timestamptz,
    paid_amount numeric(14,2) NOT NULL DEFAULT 0 CHECK (paid_amount >= 0),
    charges numeric(14,2) CHECK (charges >= 0),
    tax numeric(14,2) CHECK (tax >= 0),
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT bills_payment_state_chk CHECK (
        (paid_amount = 0 AND paid_at IS NULL AND NOT is_paid)
        OR (paid_amount > 0 AND paid_at IS NOT NULL)
    )
);

CREATE TABLE bill_items (
    bill_id bigint NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
    line_number integer NOT NULL CHECK (line_number > 0),
    item_id bigint NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
    quantity numeric(14,3) NOT NULL CHECK (quantity > 0),
    purchase_unit_price numeric(14,2) NOT NULL CHECK (purchase_unit_price >= 0),
    -- Snapshot prices; existing bills do not change when item catalogue prices change.
    line_total numeric(18,2) GENERATED ALWAYS AS (round(quantity * purchase_unit_price, 2)) STORED,
    PRIMARY KEY (bill_id, line_number)
);

CREATE TABLE tags (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL CHECK (btrim(name) <> ''),
    CONSTRAINT tags_name_unique UNIQUE (name)
);

CREATE TABLE bill_tags (
    bill_id bigint NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
    tag_id bigint NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (bill_id, tag_id)
);

CREATE INDEX idx_bills_vendor_id ON bills(vendor_id);
CREATE INDEX idx_bills_due_date_unpaid ON bills(due_date) WHERE NOT is_paid;
CREATE INDEX idx_bill_items_item_id ON bill_items(item_id);
CREATE INDEX idx_bill_tags_tag_id ON bill_tags(tag_id);

-- Convenient calculated bill totals; no redundant total stored.
CREATE VIEW bill_totals AS
SELECT b.id AS bill_id,
       COALESCE(SUM(bi.line_total), 0)::numeric(18,2) AS subtotal,
       b.charges,
       b.tax,
       (COALESCE(SUM(bi.line_total), 0) + COALESCE(b.charges, 0) + COALESCE(b.tax, 0))::numeric(18,2) AS total_amount,
       b.paid_amount,
       (COALESCE(SUM(bi.line_total), 0) + COALESCE(b.charges, 0) + COALESCE(b.tax, 0) - b.paid_amount)::numeric(18,2) AS balance_due
FROM bills b
LEFT JOIN bill_items bi ON bi.bill_id = b.id
GROUP BY b.id;

COMMIT;
