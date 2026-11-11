# Member Admin

Multi-brand (multi-tenant) member management system with a referral / agent tree.
Brand အများကြီးကို စနစ်တစ်ခုတည်းကနေ စီမံပြီး member တစ်ယောက်ချင်းကို ဘယ်သူက ဖိတ်ခေါ်ခဲ့လဲ (agent အဆင့်ဆင့်) ခြေရာခံနိုင်တဲ့ Admin စနစ်ပါ။

> **Status:** Step 1 – Database schema + fake test data (~100,000 members)

## Stack (plan)

| Part     | Tech                                   |
|----------|----------------------------------------|
| Database | PostgreSQL 16                          |
| Backend  | FastAPI (Python) – *next step*         |
| Frontend | Vue 3 + Element Plus + vxe-table – *later* |
| Deploy   | Docker Compose + Traefik (VPS)         |

## Project structure

```
.
├── db/
│   ├── init/
│   │   ├── 01_schema.sql   # tables, indexes, member_list_view
│   │   └── 02_seed.sql     # FAKE test data (2 brands, 100k members)
│   └── queries.sql         # example queries for the admin API
├── docker-compose.yml
├── .env.example
└── README.md
```

## Run (VPS / local)

```bash
git clone git@github.com:karkar1991/website.git
cd website
cp .env.example .env        # .env ထဲက password တွေ ပြောင်းပါ
docker compose up -d        # ပထမဆုံးအကြိမ်မှာ schema + test data အလိုအလျောက် ထည့်ပေးပါတယ်
```

Database ထဲဝင်ကြည့်ရန်:

```bash
docker compose exec db psql -U member_admin -d member_admin
```

```sql
SELECT * FROM member_list_view ORDER BY created_at DESC LIMIT 20;
```

> `db/init/` ထဲက script တွေဟာ database volume အလွတ်ဖြစ်တဲ့ ပထမဆုံးအကြိမ်မှာပဲ run ပါတယ်။
> အစကနေ ပြန်စချင်ရင်: `docker compose down -v && docker compose up -d`

## Database design

- **brands** – tenant / site တစ်ခုချင်း
- **vip_levels**, **tags** – brand တစ်ခုချင်းအလိုက် setting
- **members** – member အားလုံး (member တိုင်း agent လည်း ဖြစ်နိုင်ပါတယ်)
  - `inviter_id` → တိုက်ရိုက် ဖိတ်ခေါ်သူ (上级代理)
  - `path` → referral tree, ဥပမာ `/12/45/678/` (ပထမဆုံး ID = top agent)
  - `depth` → tree ထဲက အဆင့်
- **admin_users**, **admin_roles** – admin login + permission, `allowed_brands` နဲ့ brand ကန့်သတ်ချက်
- **audit_logs** – ဘယ် admin က ဘာပြောင်းခဲ့လဲ မှတ်တမ်း
- **member_list_view** – admin ဇယားအတွက် brand, VIP, inviter, top agent တွေ ပေါင်းထားတဲ့ view

Agent တစ်ယောက်အောက်က member အားလုံး (အဆင့်တိုင်း):

```sql
SELECT m.* FROM members m
JOIN members a ON a.id = :agent_id
WHERE m.path LIKE a.path || '%' AND m.id <> a.id;
```

## Security rules

- `.env` ကို GitHub ပေါ် **ဘယ်တော့မှ မတင်ပါနဲ့** (`.gitignore` ထဲ ထည့်ပြီးသား)
- Test data က **fake data** သက်သက်ပါ။ Customer data အစစ်တွေ၊ data export file တွေ မတင်ပါနဲ့။
- Query တိုင်းမှာ admin ရဲ့ `allowed_brands` နဲ့ filter လုပ်ရပါမယ်။
- Password ကို bcrypt / argon2 hash နဲ့ပဲ သိမ်းပါ။

## Roadmap

1. [x] Database schema + fake test data
2. [ ] Admin login (JWT access + refresh token)
3. [ ] Member list API (filter + pagination)
4. [ ] Vue admin frontend (member table + search)
5. [ ] Agent tree view
6. [ ] Status change / blacklist / bulk actions
7. [ ] Excel export
8. [ ] Roles, permissions, audit log UI
