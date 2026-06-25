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