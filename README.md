# Member Admin

Multi-brand member management system with a referral / agent tree and a payment (wallet) module.

Brand အများကြီးကို စနစ်တစ်ခုတည်းကနေ စီမံနိုင်တဲ့ Admin စနစ်ပါ။ Member တစ်ယောက်ချင်းကို ဘယ်သူက ဖိတ်ခေါ်ခဲ့လဲ (agent အဆင့်ဆင့်) ခြေရာခံနိုင်ပြီး ငွေသွင်း/ငွေထုတ်ကို approve စနစ်နဲ့ စီမံနိုင်ပါတယ်။ ငွေလှုပ်ရှားမှုတိုင်းကို ledger ထဲမှာ မှတ်တမ်းတင်ထားပါတယ်။

> Repo ထဲက data အားလုံးဟာ **fake test data** သက်သက်ပါ။

## Features

| Module | ဘာလုပ်လဲ |
|---|---|
| **Login** | JWT access token (၁၅ မိနစ်) + refresh token (၇ ရက်)၊ token ကုန်ရင် အလိုအလျောက် refresh လုပ်ပေးပါတယ် |
| **Members** | ရှာဖွေခြင်း (ရက်စွဲ၊ username၊ inviter၊ VIP၊ tag)၊ status tab များ၊ member အသစ်ထည့်ခြင်း၊ bulk status ပြောင်းခြင်း၊ Excel export |
| **Member detail** | Wallet balance၊ ledger၊ status/tag ပြောင်းခြင်း၊ balance ညှိခြင်း၊ referral tree (အဆင့်ဆင့် ဖွင့်ကြည့်နိုင်) |
| **Deposits** | ငွေသွင်း request → Approve / Reject၊ channel အလိုက် min/max စစ်ခြင်း၊ approve ရင် agent commission အလိုအလျောက် ပေးခြင်း |
| **Withdrawals** | Request တင်တာနဲ့ ငွေကို freeze လုပ်ခြင်း → Approve (transfer ID ထည့်ရ) / Reject (freeze ပြန်ဖြေ)၊ blacklist member ငွေထုတ်ခွင့် ပိတ်ခြင်း |
| **Ledger** | ငွေလှုပ်ရှားမှုတိုင်း (deposit, withdraw, commission, adjust)၊ ဖျက်လို့ပြင်လို့ မရပါ |
| **Payment channels** | KBZPay / WavePay / Bank account များ၊ ကန့်သတ်ပမာဏ၊ ဖွင့်/ပိတ် |
| **Reports** | Brand အလိုက် summary + နေ့စဉ် ငွေဝင်/ထွက်/commission/new members |
| **Admin users** | Admin account၊ role၊ ကြည့်ခွင့်ရှိတဲ့ brand သတ်မှတ်ခြင်း |
| **Audit log** | ဘယ် admin က ဘာလုပ်ခဲ့လဲ (login, approve, status change, export …) |

### Roles

| Role | ခွင့်ပြုချက် |
|---|---|
| `super_admin` | အကုန်လုံး |
| `finance` | Member ကြည့်၊ deposit/withdraw ဖန်တီး + approve |
| `marketing` | Member ကြည့်၊ export |
| `support` | Member ကြည့်/ပြင်၊ finance ကြည့်ရုံ |

Admin တစ်ယောက်ချင်းစီဟာ `allowed_brands` ထဲက brand data ကိုပဲ မြင်ရပါတယ်။

## Stack

PostgreSQL 16 · FastAPI (Python) · Vue 3 + Element Plus · Docker Compose · Traefik

```
.
├── db/init/            # SQL: schema, fake members, finance tables (first start only)
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

**5. (Optional) Demo ငွေသွင်း/ထုတ် data ထည့်ပါ**
```bash
docker compose exec api python -m app.seed_demo --deposits 3000 --withdrawals 600
```

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

- `.env` ကို GitHub ပေါ် **ဘယ်တော့မှ မတင်ပါနဲ့** (`.gitignore` ထဲ ထည့်ပြီးသား)
- Customer data အစစ်၊ export file (`.xlsx`, `.csv`)၊ DB dump တွေ မတင်ပါနဲ့
- Password တွေကို bcrypt hash နဲ့ သိမ်းပါတယ်
- Database နဲ့ web port တွေကို `127.0.0.1` ပေါ်မှာပဲ ဖွင့်ထားပါတယ်၊ အပြင်ကနေ Traefik (HTTPS) ကတဆင့်ပဲ ဝင်ရပါမယ်
- ငွေအစစ် လက်ခံမယ်ဆိုရင် payment provider နဲ့ merchant agreement နဲ့ ဥပဒေဆိုင်ရာ ခွင့်ပြုချက်တွေ လိုအပ်ပါတယ်

## API

API docs (Swagger) ကို run ပြီးရင် `/api/docs` မှာ ကြည့်လို့ရပါတယ်။
