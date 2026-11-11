-- =====================================================================
-- FAKE test data only. No real customer data.
-- 2 brands, ~100,000 members in a 5-level referral tree.
-- =====================================================================

INSERT INTO brands (name, currency) VALUES
    ('demo-shop-a', 'MMK'),
    ('demo-shop-b', 'THB');

INSERT INTO vip_levels (brand_id, level, name)
SELECT b.id, l, 'VIP' || l
FROM brands b, generate_series(0, 5) AS l;

INSERT INTO tags (brand_id, name)
SELECT b.id, t
FROM brands b, unnest(ARRAY['new', 'active', 'inactive', 'priority']) AS t;

INSERT INTO admin_roles (name, permissions) VALUES
    ('super_admin', ARRAY['*']),
    ('marketing',   ARRAY['member.view', 'member.export']),
    ('finance',     ARRAY['member.view', 'finance.view']);

-- Demo admin. password_hash is a placeholder: replace with a real bcrypt hash.
INSERT INTO admin_users (username, password_hash, role_id, allowed_brands)
SELECT 'admin', 'CHANGE_ME', r.id, ARRAY(SELECT id FROM brands)
FROM admin_roles r WHERE r.name = 'super_admin';

-- ---------- Build the referral tree level by level ----------
DO $$
DECLARE
    -- members per brand at each depth: 20 top agents -> ~50,000 per brand
    per_level INT[] := ARRAY[20, 200, 2000, 15000, 32780];
    lvl INT;
BEGIN
    -- depth 0: top-level agents
    INSERT INTO members (brand_id, username, status, depth, created_at)
    SELECT b.id, 'agent' || lpad(g::text, 3, '0'), 'normal', 0,
           now() - interval '365 days' * random()
    FROM brands b, generate_series(1, per_level[1]) AS g;

    UPDATE members SET path = '/' || id || '/' WHERE depth = 0;

    -- depth 1..4: each new member gets a random inviter from the level above
    FOR lvl IN 1 .. array_length(per_level, 1) - 1 LOOP
        INSERT INTO members (brand_id, username, status, inviter_id, depth, created_at)
        SELECT n.brand_id,
               'u' || lvl || '_' || lpad(n.g::text, 6, '0'),
               (CASE
                    WHEN r < 0.90 THEN 'normal'
                    WHEN r < 0.95 THEN 'blacklist'
                    WHEN r < 0.98 THEN 'leaving'
                    ELSE 'left'
                END)::member_status,
               p.id,
               lvl,
               now() - interval '365 days' * random()
        FROM (
            SELECT b.id AS brand_id, g, random() AS r,
                   1 + floor(random() * (SELECT count(*) FROM members
                                         WHERE brand_id = b.id AND depth = lvl - 1))::int AS pick
            FROM brands b, generate_series(1, per_level[lvl + 1]) AS g
        ) n
        JOIN (
            SELECT id, brand_id,
                   row_number() OVER (PARTITION BY brand_id ORDER BY id) AS rn
            FROM members WHERE depth = lvl - 1
        ) p ON p.brand_id = n.brand_id AND p.rn = n.pick;

        UPDATE members c
        SET path = p.path || c.id || '/'
        FROM members p
        WHERE c.inviter_id = p.id AND c.depth = lvl;
    END LOOP;
END $$;

-- ---------- Random VIP level (most members VIP0) ----------
UPDATE members m
SET vip_level_id = v.id
FROM vip_levels v
WHERE v.brand_id = m.brand_id
  AND v.level = (CASE
                     WHEN (m.id * 7919) % 100 < 70 THEN 0
                     WHEN (m.id * 7919) % 100 < 85 THEN 1
                     WHEN (m.id * 7919) % 100 < 93 THEN 2
                     WHEN (m.id * 7919) % 100 < 97 THEN 3
                     WHEN (m.id * 7919) % 100 < 99 THEN 4
                     ELSE 5
                 END);

-- ---------- Tag ~10% of members ----------
INSERT INTO member_tags (member_id, tag_id)
SELECT m.id, t.id
FROM members m
JOIN tags t ON t.brand_id = m.brand_id
WHERE random() < 0.025;

ANALYZE;
