# Member Admin

Multi-brand member management system with a referral / agent tree and a payment (wallet) module.

Brand အများကြီးကို စနစ်တစ်ခုတည်းကနေ စီမံနိုင်တဲ့ Admin စနစ်ပါ။ Member တစ်ယောက်ချင်းကို ဘယ်သူက ဖိတ်ခေါ်ခဲ့လဲ (agent အဆင့်ဆင့်) ခြေရာခံနိုင်ပြီး ငွေသွင်း/ငွေထုတ်ကို approve စနစ်နဲ့ စီမံနိုင်ပါတယ်။ ငွေလှုပ်ရှားမှုတိုင်းကို ledger ထဲမှာ မှတ်တမ်းတင်ထားပါတယ်။

> Repo ထဲက data အားလုံးဟာ **fake test data** သက်သက်ပါ။

## Features

| Module | ဘာလုပ်လဲ |
|---|---|
| **Login** | JWT access token (၁၅ မိနစ်) + refresh token (၇ ရက်)၊ **2FA** (Google Authenticator)၊ password ၅ ခါမှားရင် ၁၅ မိနစ် lock |
| **Members** | All / Blacklist / Leaving / Left tab၊ **Today / Yesterday / Week / Month** ခလုတ်၊ username၊ ဖုန်း၊ inviter၊ VIP၊ member level၊ account type (formal/test)၊ traffic source၊ tag နဲ့ ရှာခြင်း၊ ⚙️ column ရွေးခြင်း၊ member ထည့်ခြင်း၊ **Excel/CSV import**၊ bulk status၊ Excel export |
| **Member detail** | Wallet + ledger၊ balance ညှိခြင်း၊ referral tree (100 ယောက်စီ "Load more")၊ profile / VIP / level / source / status / tag ပြင်ခြင်း |
| **Agents** | Invite လုပ်ထားတဲ့ member အားလုံး: တိုက်ရိုက် invite၊ team တစ်ခုလုံး၊ ကာလအတွင်း member အသစ်၊ team ငွေသွင်း၊ commission — အစီအစဉ်ပြောင်းကြည့်လို့ရ |
| **Deposits** | ငွေသွင်း request → Approve / Reject၊ channel min/max စစ်ခြင်း၊ approve ရင် agent commission အလိုအလျောက် |
| **Withdrawals** | Request တင်တာနဲ့ ငွေ freeze → Approve (transfer ID ထည့်ရ) / Reject၊ blacklist member ငွေထုတ်ခွင့် ပိတ် |
| **Notifications** | 🔔 Pending request အရေအတွက် (၁၅ စက္ကန့်တစ်ခါ စစ်)၊ အသစ်ဝင်ရင် popup + အသံ၊ **Telegram group** ထဲ alert (optional) |
| **Ledger** | ငွေလှုပ်ရှားမှုတိုင်း (deposit, withdraw, commission, adjust) — ဖျက်/ပြင်လို့ မရ |
| **Payment channels** | KBZPay / WavePay / Bank account၊ ကန့်သတ်ပမာဏ၊ ဖွင့်/ပိတ် |
| **Traffic sources** | Member ဘယ်ကလာလဲ (Facebook ads, TikTok, telesale, referral link …) |
| **Reports** | Brand summary၊ နေ့စဉ်၊ **source အလိုက် conversion**၊ test account တွေကို default ဖယ်ထား |
| **Admin users** | Account၊ role၊ brand ခွင့်ပြုချက်၊ 2FA အခြေအနေ၊ last login၊ Unlock / Reset 2FA |
| **Audit log** | ဘယ် admin က ဘာလုပ်ခဲ့လဲ (login, login မှား, approve, import, export, ပြင်ဆင်မှု …) |
| **Backup** | `scripts/backup.sh` (နေ့စဉ်၊ ၁၄ ရက်စာ သိမ်း) + `scripts/restore.sh` |

### Roles

| Role | ခွင့်ပြုချက် |
|---|---|
| `super_admin` | အကုန်လုံး |
| `finance` | Member ကြည့်၊ deposit/withdraw ဖန်တီး + approve |
| `marketing` | Member ကြည့်၊ export၊ traffic source စီမံ |
| `support` | Member ကြည့်/ပြင်၊ finance ကြည့်ရုံ |

Admin တစ်ယောက်ချင်းစီဟာ `allowed_brands` ထဲက brand data ကိုပဲ မြင်ရပါတယ်။

### WG backend နဲ့ နှိုင်းယှဉ်ချက်

| WG | ဒီ system |
|---|---|
| 所有会员 / 黑名单 / 劝退中 / 已劝退 | Members tabs: All / Blacklist / Leaving / Left |
| 注册时间 + 日 / 周 / 月 | Registered date + Today / Yesterday / Week / Month |
| 精准会员账号 / 高级搜索 | Exact username + "More filters" |
| 新增会员 / 导入 / 导出报表 | Add member / Import / Export |
| 账号类型 (正式账号) | Account type (formal / test) |
| 会员层级 / VIP | Member level / VIP |
| 邀请人 / 顶层代理 / 上级代理 | Inviter / Top agent / referral tree |
| 代理 | Agents page |
| 引流 | Traffic sources + source report |
| 消息 | 🔔 notifications + Telegram |
| ⚙️ column settings | ⚙️ column chooser |
| 批量操作 | Bulk action |

## Stack

PostgreSQL 16 · FastAPI (Python) · Vue 3 + Element Plus · Docker Compose · Traefik

```
.
├── db/init/            # SQL: schema, fake members, finance, extra fields (first start only)
├── scripts/            # backup.sh, restore.sh
├── backend/            # FastAPI API  (app/routers, app/services/wallet.py, tests/)
├── frontend/           # Vue 3 admin UI (src/views)
├── docker-compose.yml
├── docker-compose.traefik.yml
└── .env.example
```

## VPS ပေါ်မှာ Run နည်း (အဆင့်လိုက်)

**1. Code ကို ဆွဲယူပါ**
```bash
git clone git@github.com:karkar1991/website.git member-admin
cd member-admin
```

**2. `.env` ပြင်ဆင်ပါ**
```bash
cp .env.example .env
openssl rand -hex 32        # ထွက်လာတဲ့စာကို JWT_SECRET ထဲ ထည့်ပါ
nano .env                   # POSTGRES_PASSWORD, ADMIN_PASSWORD ကိုလည်း ပြောင်းပါ
```

**3. စတင် run ပါ**

Traefik မပါရင်:
```bash
docker compose up -d --build
# လုံခြုံရေးအတွက် VPS ရဲ့ 127.0.0.1:8080 မှာပဲ ဖွင့်ထားပါတယ်။ ကိုယ့်စက်ကနေ ကြည့်ဖို့:
ssh -L 8080:127.0.0.1:8080 user@VPS_IP     # ပြီးရင် http://localhost:8080
```

Traefik ရှိပြီးသား VPS ပေါ်မှာ (`.env` ထဲ `DOMAIN`, `TRAEFIK_NETWORK`, `TRAEFIK_CERTRESOLVER` သတ်မှတ်ပါ):
```bash
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d --build
# https://DOMAIN
```

**4. Login ဝင်ပါ** — username `admin`၊ password က `.env` ထဲက `ADMIN_PASSWORD` ဖြစ်ပါတယ်။
ဝင်ပြီးတာနဲ့ ညာဘက်အပေါ် နာမည် → **Two-factor login (2FA)** ကို ဖွင့်ပါ (ငွေကိုင်တဲ့ admin အားလုံး ဖွင့်သင့်ပါတယ်)။

**5. (Optional) Demo ငွေသွင်း/ထုတ် data ထည့်ပါ**
```bash
docker compose exec api python -m app.seed_demo --deposits 3000 --withdrawals 600
```

**6. နေ့စဉ် backup ဖွင့်ပါ**
```bash
chmod +x scripts/*.sh
./scripts/backup.sh                       # တစ်ခါ စမ်း run ကြည့်ပါ
crontab -e                                # ပြီးရင် ဒီစာကြောင်း ထည့်ပါ (မနက် ၃:၃၀ တိုင်း)
30 3 * * * /root/member-admin/scripts/backup.sh >> /var/log/member-admin-backup.log 2>&1
```
Backup ကို VPS တစ်ခုတည်းမှာပဲ မထားပါနဲ့၊ တခြားနေရာ (Google Drive, another server) ကို ကူးထားပါ။
ပြန်ထည့်ရန်: `./scripts/restore.sh backups/member_admin_YYYYMMDD_HHMMSS.sql.gz`

**7. (Optional) Telegram alert** — @BotFather မှာ bot လုပ်ပြီး finance group ထဲ ထည့်ပါ။ `.env` ထဲ `TELEGRAM_BOT_TOKEN` နဲ့ `TELEGRAM_CHAT_ID` ထည့်ပြီး `docker compose up -d` ပြန် run ပါ။

**အချိန်ဇုန်** — `APP_TIMEZONE` (default `Asia/Yangon`) က "ဒီနေ့"၊ နေ့စဉ် report တွေရဲ့ နေ့ပိုင်းခြားချက်ကို ဆုံးဖြတ်ပါတယ်။ ထိုင်းအချိန်လိုရင် `Asia/Bangkok`။

ပထမဆုံးအကြိမ် start လုပ်တဲ့အခါ fake member ၁ သိန်းကို ထည့်ပေးတာကြောင့် ၁ မိနစ်လောက် ကြာနိုင်ပါတယ်။
Database ကို အစကနေ ပြန်စချင်ရင်: `docker compose down -v && docker compose up -d --build`

## Local development

```bash
# backend
cd backend
pip install -r requirements.txt
export DATABASE_URL=postgresql://member_admin:PASSWORD@localhost:5432/member_admin ADMIN_PASSWORD=admin12345
uvicorn app.main:app --reload            # http://localhost:8000/api/docs  (API docs)

# frontend (another terminal)
cd frontend
npm install
npm run dev                              # http://localhost:5173
```

Tests (database ထဲမှာ `db/init/*.sql` ထည့်ပြီးသား ဖြစ်ရပါမယ်):
```bash
cd backend
python -m app.seed_demo
pytest -q
```

GitHub ပေါ် push လုပ်တိုင်း `.github/workflows/ci.yml` က tests နဲ့ frontend build ကို အလိုအလျောက် run ပေးပါတယ်။

## Payment design (ငွေကြေးစနစ် စည်းကမ်းများ)

- `wallets` = လက်ရှိ balance + frozen (ထုတ်ဖို့ ဆိုင်းငံ့ထားတဲ့ငွေ)
- `wallet_transactions` = **append-only ledger**: ငွေလှုပ်ရှားမှုတိုင်း တစ်ကြောင်းစီ မှတ်ပါတယ်။ DB trigger က UPDATE/DELETE ကို ပိတ်ထားပါတယ်။ မှားရင် `adjust` transaction အသစ်ထည့်ပြီး ပြင်ပါ။
- Wallet ပြောင်းတိုင်း `SELECT ... FOR UPDATE` နဲ့ lock လုပ်ပါတယ်။ ဒါကြောင့် တစ်ပြိုင်နက် request ၂ ခုဝင်လာလည်း ငွေနှစ်ခါ မထုတ်မိပါဘူး။
- `request_key` (idempotency) — request တစ်ခုတည်းကို ၂ ခါ ပို့လည်း တစ်ခုပဲ ဖြစ်ပါတယ်။
- `balance >= frozen` ကို DB CHECK နဲ့ပါ ထပ်စောင့်ထားပါတယ်။
- Commission: `commission_rules` (default L1 2%, L2 1%, L3 0.5%)၊ status `normal` agent တွေပဲ ရပါတယ်။
- ငွေနဲ့ဆိုင်တဲ့ logic အားလုံးဟာ `backend/app/services/wallet.py` ထဲမှာပဲ ရှိပါတယ်။

## Security
- Admin login: bcrypt password + 2FA (TOTP) + failed-login lock + audit log

- `.env` ကို GitHub ပေါ် **ဘယ်တော့မှ မတင်ပါနဲ့** (`.gitignore` ထဲ ထည့်ပြီးသား)
- Customer data အစစ်၊ export file (`.xlsx`, `.csv`)၊ DB dump တွေ မတင်ပါနဲ့
- Password တွေကို bcrypt hash နဲ့ သိမ်းပါတယ်
- Database နဲ့ web port တွေကို `127.0.0.1` ပေါ်မှာပဲ ဖွင့်ထားပါတယ်၊ အပြင်ကနေ Traefik (HTTPS) ကတဆင့်ပဲ ဝင်ရပါမယ်
- ငွေအစစ် လက်ခံမယ်ဆိုရင် payment provider နဲ့ merchant agreement နဲ့ ဥပဒေဆိုင်ရာ ခွင့်ပြုချက်တွေ လိုအပ်ပါတယ်

## API

API docs (Swagger) ကို run ပြီးရင် `/api/docs` မှာ ကြည့်လို့ရပါတယ်။
