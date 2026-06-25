# 登录安全体系升级计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复登录安全体系的 6 项风险，提升整体安全性。

**Architecture:** 在现有认证体系上做增量改动，通过配置驱动（.env / options 表）控制功能开关，确保向后兼容。改动范围控制在后端 auth 相关模块。

**Tech Stack:** bcrypt, pyotp, FastAPI, SQLAlchemy, pydantic-settings

---

## 待修复风险汇总

| # | 风险 | 级别 | 任务 |
|---|------|------|------|
| R1 | Session Cookie `Secure=False` | 🔴 高 | Task 1 |
| R2 | 注册密码强度仅 `>=8` 字符 | 🟡 中 | Task 2 |
| R3 | TOTP pending 状态存内存 | 🟡 中 | Task 3 |
| R4 | 登录页无 Turnstile 防护 | 🟡 中 | Task 4 |
| R5 | `locked_until=1年` 语义不精确 | 🟢 低 | Task 5 |
| R6 | Passkey RP ID 从 Host header 提取 | 🟢 低 | Task 6 |

---

## 全局约束

- `.env` 中已配置 `session_secret` 和 `turnstile_secret_key`
- SMTP 配置已完成（QQ 邮箱，`107105108@qq.com`）
- 数据库使用 SQLite（`uniapi.db`），模型变更需创建 Alembic migration
- 依赖：`bcrypt`, `pyotp`, `pydantic-settings`, `itsdangerous`

---

## 文件映射

```
app/
  config.py                        ← 添加密码策略配置项
  routers/api/auth.py              ← 修复 Secure cookie；集成登录 Turnstile
  services/user.py                 ← 增强密码强度检查
  services/totp.py                 ← 无改动（仅逻辑位置确认）
  routers/api/totp.py              ← TOTP pending 持久化到 DB
  routers/api/passkey.py           ← RP ID 硬编码域名
  models/user.py                   ← 添加 pending_totp_secret 字段
  models/passkey.py                ← 无改动

migrations/                       ← Alembic version
tests/
  phase5/
    test_auth_security.py          ← 新建测试文件
```

---

## Task 1: Session Cookie 启用 Secure 标志

**Files:**
- Modify: `app/routers/api/auth.py:75-91`
- Modify: `app/config.py` — 添加 `session_cookie_secure` 配置
- Test: `tests/phase5/test_auth_security.py` — `test_session_cookie_flags`

**Interfaces:**
- 消耗: `app/config.settings.session_cookie_secure` (bool, 默认 True)
- 产生: `set_cookie(..., secure=session_cookie_secure)` 行为变化

- [ ] **Step 1: 添加配置项**

在 `app/config.py` 的 `Settings` 类中添加：
```python
session_cookie_secure: bool = True  # 生产环境必须为 True
```

- [ ] **Step 2: 修改 auth.py 的 set_cookie 调用**

修改 `app/routers/api/auth.py` 中 `login` 函数，将 `secure=False` 改为：
```python
secure=settings.session_cookie_secure,
```

- [ ] **Step 3: 写测试**

```python
def test_session_cookie_flags():
    from app.config import settings
    assert settings.session_cookie_secure == True
    # 验证 login 路由返回的 Set-Cookie 包含 Secure
```

- [ ] **Step 4: commit**

---

## Task 2: 增强注册密码强度检查

**Files:**
- Modify: `app/services/user.py:register_user()` — 替换 `len(password) < 8` 检查
- Modify: `app/config.py` — 添加密码策略配置
- Test: `tests/phase5/test_auth_security.py` — `test_password_strength`

**Interfaces:**
- 消耗: `settings.password_min_length`, `settings.password_require_uppercase`, `settings.password_require_digit`
- 产生: `register_user()` 中的验证逻辑变化

- [ ] **Step 1: 添加密码策略配置**

在 `app/config.py` 中添加：
```python
password_min_length: int = 8
password_require_uppercase: bool = True
password_require_digit: bool = True
password_require_special: bool = False
```

- [ ] **Step 2: 添加密码验证辅助函数**

在 `app/services/user.py` 顶部添加：
```python
import re

def validate_password_strength(password: str) -> str | None:
    """Validate password meets policy. Returns error message or None if valid."""
    if len(password) < settings.password_min_length:
        return f"Password must be at least {settings.password_min_length} characters"
    if settings.password_require_uppercase and not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if settings.password_require_digit and not re.search(r"\d", password):
        return "Password must contain at least one digit"
    if settings.password_require_special and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return "Password must contain at least one special character"
    return None
```

- [ ] **Step 3: 修改 register_user() 中的验证逻辑**

替换 `app/services/user.py` 中的：
```python
if len(password) < 8:
    raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
```
改为：
```python
strength_error = validate_password_strength(password)
if strength_error:
    raise HTTPException(status_code=400, detail=strength_error)
```

- [ ] **Step 4: 写测试**

```python
def test_password_strength_rejects_weak():
    from app.services.user import validate_password_strength
    assert validate_password_strength("abc") is not None  # too short
    assert validate_password_strength("abcdefgh") is not None  # no uppercase
    assert validate_password_strength("ABCDEFGH") is not None  # no digit

def test_password_strength_accepts_strong():
    from app.services.user import validate_password_strength
    assert validate_password_strength("Abc12345") is None
```

- [ ] **Step 5: commit**

---

## Task 3: TOTP Pending 状态持久化到数据库

**Files:**
- Modify: `app/models/user.py` — 添加 `pending_totp_secret` 字段
- Create: `migrations/versions/xxxx_add_pending_totp.py` — Alembic migration
- Modify: `app/routers/api/totp.py` — `_pending_setups` 替换为 DB 读写
- Modify: `app/config.py` — 添加 `totp_pending_ttl_seconds` 配置
- Test: `tests/phase5/test_auth_security.py` — `test_totp_pending_persistence`

**Interfaces:**
- 消耗: `User.pending_totp_secret`, `User.pending_totp_expires_at`
- 产生: `/api/user/totp/setup` 和 `/api/user/totp/confirm` 的 DB 读写

- [ ] **Step 1: 添加 User 模型字段**

在 `app/models/user.py` 中添加：
```python
pending_totp_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
pending_totp_expires_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
```

- [ ] **Step 2: 创建 Alembic migration**

生成 migration 文件：
```bash
cd /Users/sunm15/Documents/uniapi-py && alembic revision --autogenerate -m "add pending_totp fields"
```

- [ ] **Step 3: 修改 totp.py 的 setup 逻辑**

替换 `_pending_setups[user.id] = secret` 为：
```python
from app.config import settings
expires = int(time.time() * 1000) + settings.totp_pending_ttl_seconds * 1000
user.pending_totp_secret = secret
user.pending_totp_expires_at = expires
await db.commit()
```

- [ ] **Step 4: 修改 totp.py 的 confirm 逻辑**

在 `totp_confirm` 中，替换从内存读取为 DB 读取，并验证过期时间：
```python
now_ms = int(time.time() * 1000)
pending_secret = user.pending_totp_secret
expires_at = user.pending_totp_expires_at

if not pending_secret or not expires_at or expires_at < now_ms:
    return JSONResponse(status_code=400, content=GenericApiResponse(
        success=False, message="TOTP setup expired, please retry"
    ).model_dump())

# verify the code against pending secret first
if not verify_totp_code(pending_secret, body["code"]):
    return GenericApiResponse(success=False, message="Invalid TOTP code")

# commit to permanent secret
user.totp_secret = pending_secret
user.pending_totp_secret = None
user.pending_totp_expires_at = None
await db.commit()
```

- [ ] **Step 5: 修改 totp.py 的 cancel 逻辑**

添加 `DELETE /api/user/totp/cancel` endpoint，清空 pending 字段：
```python
@router.delete("/api/user/totp/pending")
async def totp_cancel(db=Depends(get_db), user=Depends(user_auth)):
    user.pending_totp_secret = None
    user.pending_totp_expires_at = None
    await db.commit()
    return GenericApiResponse(data={"cancelled": True})
```

- [ ] **Step 6: 写测试**

```python
@pytest.mark.asyncio
async def test_totp_pending_expiry():
    # Setup TOTP pending
    # Verify pending_secret is written to DB
    # Simulate expiry and verify confirm fails
    pass
```

- [ ] **Step 7: commit**

---

## Task 4: 登录页集成 Cloudflare Turnstile

**Files:**
- Modify: `app/routers/api/auth.py` — `login` 路由集成 Turnstile
- Modify: `app/services/user.py` — `login_user()` 签名不变（验证前置到路由层）
- Test: `tests/phase5/test_auth_security.py` — `test_login_turnstile`

**Interfaces:**
- 消耗: `body.turnstile_token` (LoginRequest), `verify_turnstile()`
- 产生: 登录失败时返回 Turnstile 验证提示

- [ ] **Step 1: 在 LoginRequest schema 添加 turnstile_token**

检查 `app/schemas/user.py` 中的 `LoginRequest`，添加：
```python
turnstile_token: Optional[str] = None
```

- [ ] **Step 2: 在 login 路由中添加 Turnstile 验证**

在 `app/routers/api/auth.py` 的 `login()` 函数开头（`login_user` 调用前）添加：
```python
turnstile_enabled_result = await db.execute(
    select(Option).where(Option.key == "TurnstileCheckEnabled")
)
turnstile_enabled = turnstile_enabled_result.scalar_one_or_none()

if turnstile_enabled and turnstile_enabled.value.lower() == "true":
    if not await verify_turnstile(body.turnstile_token or ""):
        return JSONResponse(
            status_code=403,
            content=GenericApiResponse(
                success=False,
                message="Turnstile verification failed, please refresh and try again",
            ).model_dump(),
        )
```

- [ ] **Step 3: 写测试**

```python
@pytest.mark.asyncio
async def test_login_turnstile_fails_with_bad_token(client, test_db):
    # Mock TurnstileCheckEnabled = true, verify_turnstile returns False
    # POST /api/user/login with bad turnstile_token
    # Expect 403
    pass
```

- [ ] **Step 4: commit**

---

## Task 5: 锁定语义精确化（locked_until = -1 表示永久）

**Files:**
- Modify: `app/services/user.py` — `login_user()` 中的锁定逻辑
- Modify: `app/routers/api/admin_user.py` — 管理解锁逻辑适配
- Test: `tests/phase5/test_auth_security.py` — `test_account_lockout_semantics`

**Interfaces:**
- 消耗: `User.locked_until` 语义约定（-1 = 永久锁定）
- 产生: `login_user()` 中的永久锁定判断逻辑

- [ ] **Step 1: 修改变更永久锁定赋值**

在 `app/services/user.py` 的 `login_user()` 中，锁定时改为：
```python
# Permanent lock (until admin unlocks)
user.locked_until = -1
```

同时修改锁定检查逻辑：
```python
# locked_until = -1 means permanent lock (admin must unlock)
# locked_until > now means temporary lock
if user.locked_until == -1 or (user.locked_until is not None and user.locked_until > now):
    raise HTTPException(status_code=423, detail="帐户已被锁定，请使用邮箱重置密码")
```

- [ ] **Step 2: 添加管理解锁接口**

在 `app/routers/api/admin_user.py` 中添加或确认解锁 endpoint：
```python
@router.post("/api/admin/users/{user_id}/unlock")
async def unlock_user(user_id: int, db=Depends(get_db), admin=Depends(admin_auth)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.locked_until = None
    user.failed_login_attempts = 0
    await db.commit()
    return GenericApiResponse(data={"unlocked": True, "user_id": user_id})
```

- [ ] **Step 3: 写测试**

```python
def test_permanent_lock_requires_admin():
    # Simulate 5 failed logins
    # Verify locked_until == -1
    # Verify next login fails 423 regardless of password
    pass

def test_admin_unlock_resets_lock():
    # Admin calls unlock endpoint
    # Verify locked_until == None
    # Verify next login succeeds with correct password
    pass
```

- [ ] **Step 4: commit**

---

## Task 6: Passkey RP ID 硬编码为配置文件域名

**Files:**
- Modify: `app/routers/api/passkey.py` — `_get_rp_id()` 改为从配置读取
- Modify: `app/config.py` — 添加 `webauthn_rp_id` 配置项
- Test: `tests/phase5/test_auth_security.py` — `test_passkey_rp_id`

**Interfaces:**
- 消耗: `settings.webauthn_rp_id` (str, e.g. `"api.ccbot.chat"`)
- 产生: `_get_rp_id()` 返回硬编码域名而非解析 Host header

- [ ] **Step 1: 添加配置项**

在 `app/config.py` 中添加：
```python
webauthn_rp_id: str = "localhost"  # Relying Party ID for WebAuthn (must match deployment domain)
```

- [ ] **Step 2: 修改 passkey.py**

替换 `app/routers/api/passkey.py` 中的 `_get_rp_id()`：
```python
def _get_rp_id(request: Request) -> str:
    """Get the Relying Party ID from config, not from user-supplied Host header."""
    from app.config import settings
    return settings.webauthn_rp_id
```

- [ ] **Step 3: 写测试**

```python
def test_passkey_rp_id_from_config():
    from app.config import settings
    from app.routers.api.passkey import _get_rp_id
    # Mock request with spoofed Host header
    # Verify _get_rp_id returns config value, not Host header
    pass
```

- [ ] **Step 4: commit**

---

## Task 7: 部署与配置

**Files:**
- Modify: 服务器 `.env` — 添加新配置项

**Interfaces:**
- 产生: 服务器 `.env` 中的新配置值

- [ ] **Step 1: 更新服务器 .env**

SSH 到服务器，在 `.env` 中添加：
```
SESSION_COOKIE_SECURE=true
PASSWORD_REQUIRE_UPPERCASE=true
PASSWORD_REQUIRE_DIGIT=true
WEB_AUTHN_RP_ID=api.ccbot.chat
TOTP_PENDING_TTL_SECONDS=600
```

- [ ] **Step 2: 运行 migration**

```bash
cd /www/wwwroot/api.ccbot.chat && source .venv/bin/activate && alembic upgrade head
```

- [ ] **Step 3: 重启服务**

```bash
systemctl restart uniapi-py.service && sleep 2 && curl http://127.0.0.1:3000/health
```

- [ ] **Step 4: commit**

---

## Task 8: 综合安全测试验证

**Files:**
- Modify: `tests/phase5/test_auth_security.py` — 补充综合测试

- [ ] **Step 1: 写综合测试**

```python
@pytest.mark.asyncio
async def test_end_to_end_security_flow():
    # 1. Register with weak password → rejected
    # 2. Register with strong password → success
    # 3. Login with wrong password 5 times → account locked
    # 4. Login with correct password → 423 (locked)
    # 5. Admin unlocks user
    # 6. Login with correct password → success with session cookie (Secure flag set)
    # 7. Setup TOTP → pending secret in DB
    # 8. Confirm TOTP → secret permanently stored
    # 9. Login requires TOTP code
    pass
```

- [ ] **Step 2: commit**

---

## 执行后自检清单

- [ ] Session Cookie 包含 `Secure; HttpOnly; SameSite=Strict`
- [ ] 注册接口拒绝 `abc123` 类弱密码
- [ ] TOTP setup 后服务重启，pending 状态不丢失
- [ ] 登录接口带无效 turnstile_token 时返回 403
- [ ] 锁定账户 `locked_until == -1`，admin unlock 可恢复
- [ ] Passkey 注册使用 `api.ccbot.chat` 而非 Host header 值
- [ ] `alembic upgrade head` 成功执行
- [ ] `curl http://127.0.0.1:3000/health` 返回 200

---

## 风险优先级回顾

| 任务 | 修复风险 | 优先级 |
|------|---------|--------|
| Task 1 | R1: Secure=False 🔴 | P0 |
| Task 2 | R2: 密码强度 🟡 | P1 |
| Task 3 | R3: TOTP 内存 🟡 | P1 |
| Task 4 | R4: 登录无 Turnstile 🟡 | P1 |
| Task 5 | R5: 锁定语义 🟢 | P2 |
| Task 6 | R6: RP ID 🟢 | P2 |
