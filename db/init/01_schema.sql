-- =====================================================================
-- Member Admin - Database schema (PostgreSQL 16)
-- Multi-brand (multi-tenant) member + referral/agent tree
-- =====================================================================

-- ---------- Brands (tenants) ----------
CREATE TABLE brands (
    id          SERIAL PRIMARY KEY,
    name        TEXT        NOT NULL UNIQUE,
    currency    TEXT        NOT NULL DEFAULT 'MMK',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- VIP levels (per brand) ----------
CREATE TABLE vip_levels (
    id        SERIAL PRIMARY KEY,
    brand_id  INT  NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    level     INT  NOT NULL,
    name      TEXT NOT NULL,
    UNIQUE (brand_id, level)
);

-- ---------- Tags (per brand) ----------
CREATE TABLE tags (
    id        SERIAL PRIMARY KEY,
    brand_id  INT  NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    UNIQUE (brand_id, name)
);

-- ---------- Members ----------
-- Every member can also act as an agent (invites other members).
-- path  = materialized path of the referral tree, e.g. '/12/45/678/'
--         first id in path = top-level agent
-- depth = 0 for top-level agents, 1 for their direct invitees, ...
CREATE TYPE member_status AS ENUM ('normal', 'blacklist', 'leaving', 'left');

CREATE TABLE members (
    id            BIGSERIAL PRIMARY KEY,
    brand_id      INT           NOT NULL REFERENCES brands(id),
    username      TEXT          NOT NULL,
    full_name     TEXT,
    phone         TEXT,
    status        member_status NOT NULL DEFAULT 'normal',
    vip_level_id  INT           REFERENCES vip_levels(id),
    inviter_id    BIGINT        REFERENCES members(id),
    path          TEXT          NOT NULL DEFAULT '/',
    depth         INT           NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (brand_id, username)
);

CREATE INDEX idx_members_brand_created ON members (brand_id, created_at DESC);
CREATE INDEX idx_members_inviter       ON members (inviter_id);
CREATE INDEX idx_members_status        ON members (brand_id, status);
CREATE INDEX idx_members_path          ON members (path text_pattern_ops);

-- ---------- Member <-> Tag ----------
CREATE TABLE member_tags (
    member_id  BIGINT NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    tag_id     INT    NOT NULL REFERENCES tags(id)    ON DELETE CASCADE,
    PRIMARY KEY (member_id, tag_id)
);

-- ---------- Admin users & roles ----------
CREATE TABLE admin_roles (
    id           SERIAL PRIMARY KEY,
    name         TEXT  NOT NULL UNIQUE,            -- super_admin, marketing, finance
    permissions  TEXT[] NOT NULL DEFAULT '{}'      -- e.g. {member.view, member.edit}
);

CREATE TABLE admin_users (
    id              SERIAL PRIMARY KEY,
    username        TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,              -- bcrypt/argon2 hash, never plain text
    role_id         INT     NOT NULL REFERENCES admin_roles(id),
    allowed_brands  INT[]   NOT NULL DEFAULT '{}', -- brands this admin may see
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- Audit log (who changed what) ----------
CREATE TABLE audit_logs (
    id          BIGSERIAL PRIMARY KEY,
    admin_id    INT    REFERENCES admin_users(id),
    action      TEXT   NOT NULL,                   -- e.g. member.status_change
    target_id   BIGINT,
    detail      JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- Convenience view for the admin member list ----------
CREATE VIEW member_list_view AS
SELECT
    m.id,
    b.name                                     AS brand_name,
    m.brand_id,
    m.username,
    m.full_name,
    m.status,
    v.name                                     AS vip_level,
    inv.id                                     AS inviter_id,
    inv.username                               AS inviter_username,
    top.id                                     AS top_agent_id,
    top.username                               AS top_agent_username,
    b.currency,
    m.created_at
FROM members m
JOIN brands b          ON b.id = m.brand_id
LEFT JOIN vip_levels v ON v.id = m.vip_level_id
LEFT JOIN members inv  ON inv.id = m.inviter_id
LEFT JOIN members top  ON top.id = NULLIF(split_part(m.path, '/', 2), '')::BIGINT
                      AND m.depth > 0;
