-- =====================================================================
-- Extra member fields, traffic sources and admin login security
-- =====================================================================

-- ---------- Account type: real accounts vs internal test accounts ----------
CREATE TYPE account_type AS ENUM ('formal', 'test');
ALTER TABLE members ADD COLUMN account_type account_type NOT NULL DEFAULT 'formal';

-- ---------- Member level (separate from VIP; e.g. Free / Basic / ...) ----------
CREATE TABLE member_levels (
    id        SERIAL PRIMARY KEY,
    brand_id  INT  NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    sort      INT  NOT NULL DEFAULT 0,
    UNIQUE (brand_id, name)
);
ALTER TABLE members ADD COLUMN member_level_id INT REFERENCES member_levels(id);

-- ---------- Traffic source: where the member came from ----------
CREATE TABLE traffic_sources (
    id        SERIAL PRIMARY KEY,
    brand_id  INT  NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    code      TEXT NOT NULL,          -- short code used in links / imports, e.g. fb_nov
    name      TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (brand_id, code)
);
ALTER TABLE members ADD COLUMN source_id INT REFERENCES traffic_sources(id);

CREATE INDEX idx_members_type   ON members (brand_id, account_type);
CREATE INDEX idx_members_level  ON members (member_level_id);
CREATE INDEX idx_members_source ON members (source_id);

-- ---------- Admin login security ----------
ALTER TABLE admin_users
    ADD COLUMN totp_secret    TEXT,
    ADD COLUMN totp_enabled   BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN failed_logins  INT     NOT NULL DEFAULT 0,
    ADD COLUMN locked_until   TIMESTAMPTZ,
    ADD COLUMN last_login_at  TIMESTAMPTZ;

-- ---------- FAKE data for the new fields ----------
INSERT INTO member_levels (brand_id, name, sort)
SELECT b.id, l.name, l.sort
FROM brands b
CROSS JOIN (VALUES ('Free', 0), ('Basic', 1), ('Standard', 2), ('Premium', 3)) AS l(name, sort);

INSERT INTO traffic_sources (brand_id, code, name)
SELECT b.id, s.code, s.name
FROM brands b
CROSS JOIN (VALUES ('facebook', 'Facebook ads'), ('tiktok', 'TikTok'),
                   ('telesale', 'Telesale team'), ('referral', 'Referral link')) AS s(code, name);

UPDATE members m
SET member_level_id = l.id
FROM member_levels l
WHERE l.brand_id = m.brand_id
  AND l.sort = (CASE WHEN (m.id * 31) % 100 < 75 THEN 0
                     WHEN (m.id * 31) % 100 < 90 THEN 1
                     WHEN (m.id * 31) % 100 < 97 THEN 2
                     ELSE 3 END);

UPDATE members m
SET source_id = s.id
FROM traffic_sources s
WHERE s.brand_id = m.brand_id
  AND s.code = (ARRAY['facebook', 'tiktok', 'telesale', 'referral'])[1 + abs(hashtext(m.id::text)) % 4];

UPDATE members SET account_type = 'test' WHERE id % 97 = 0;

ANALYZE members;

-- marketing may manage traffic sources
UPDATE admin_roles SET permissions = permissions || ARRAY['source.manage'] WHERE name = 'marketing';
