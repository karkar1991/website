-- =====================================================================
-- Example queries the admin API will use
-- =====================================================================

-- 1) Member list: filter by brand + date + status, newest first, page 1 (100 rows)
SELECT *
FROM member_list_view
WHERE brand_id = ANY (ARRAY[1, 2])            -- admin_users.allowed_brands
  AND created_at >= now() - interval '30 days'
  AND status = 'normal'
ORDER BY created_at DESC
LIMIT 100 OFFSET 0;

-- 2) Exact username search
SELECT * FROM member_list_view WHERE brand_id = 1 AND username = 'u2_000123';

-- 3) All members under one agent (whole downline, every depth)
SELECT m.*
FROM members m
JOIN members a ON a.id = 5                      -- agent id
WHERE m.path LIKE a.path || '%'
  AND m.id <> a.id;

-- 4) Direct invitees count per top agent
SELECT top_agent_username, count(*) AS members
FROM member_list_view
WHERE brand_id = 1
GROUP BY top_agent_username
ORDER BY members DESC;

-- 5) Change status (blacklist) + write audit log
BEGIN;
UPDATE members SET status = 'blacklist', updated_at = now() WHERE id = 1234;
INSERT INTO audit_logs (admin_id, action, target_id, detail)
VALUES (1, 'member.status_change', 1234, '{"to": "blacklist"}');
COMMIT;
