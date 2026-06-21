# UniAPI 错误码规范 — TDD 实施计划

> 基于 [UNIAPI_ERROR_CODE_SPEC_DRAFT.md](./UNIAPI_ERROR_CODE_SPEC_DRAFT.md) v2 制定
>
> 原则：所有代码改动前先写测试，红 → 绿 → 重构。

---

## 实施概览

```
Phase 0  →  错误码常量 + Schema 定义        [基础设施]
Phase 1  →  核心异常层重构                   [app/exceptions.py]
Phase 2  →  上游错误映射层                   [app/relay/upstream_errors.py]
Phase 3  →  依赖层异常替换 (auth)            [app/dependencies.py]
Phase 4  →  Relay 层异常替换                 [app/routers/v1/relay.py]
Phase 5  →  中间件适配                       [app/middleware.py]
Phase 6  →  上游映射集成 + 端到端测试         [集成]
Phase 7  →  快照测试 + 兼容性验证             [回归保障]
```

每个 Phase 内按 TDD 红→绿→重构循环推进。

---

## Phase 0: 错误码常量 + Schema 定义

### Task 0.1: 定义错误码常量枚举

**文件**：`app/error_codes.py`（新建）

```
包含:
- ErrorCode 常量（20 个首批 code）
- ErrorType 常量（8 个 type）
- code → (status_code, type) 映射表
- 辅助函数: get_error_meta(code) → (status, type)
```

**测试**：`tests/phase5/test_error_codes.py` — `TestErrorCodeConstants`

```
□ test_all_codes_have_unique_values       # 20 个 code 值不重复
□ test_code_naming_prefix                 # code 必须以 UNIAPI_ / UPSTREAM_ / PROVIDER_ 开头
□ test_error_type_enum_values             # type 必须是 8 个枚举之一
□ test_get_error_meta_known_code          # 查已知 code 返回正确 (status, type)
□ test_get_error_meta_unknown_code        # 未知 code 返回默认 (500, internal)
□ test_code_count_matches_spec            # 首批 20 个 code
```

### Task 0.2: 创建错误响应 Pydantic Schema

**文件**：`app/schemas/error.py`（新建）

```
包含:
- UpstreamErrorDetail (provider, status_code, code, message, request_id)
- StandardErrorDetail (code, message, type, status_code, details?, suggestion?, request_id, timestamp, upstream?)
- StandardErrorResponse (success: false, error: StandardErrorDetail)
- 工厂函数: build_error_response(code, message, **kwargs)
```

**测试**：`tests/phase5/test_error_schemas.py` — `TestErrorSchemas`

```
□ test_build_minimal_error_response        # 仅 code + message 生成合法结构
□ test_build_full_error_response           # 完整字段均填充
□ test_build_error_with_upstream           # upstream 子对象正确
□ test_build_error_with_details            # details 任意 dict
□ test_build_error_with_suggestion         # suggestion 字段
□ test_timestamp_is_iso8601_utc            # timestamp 格式校验
□ test_request_id_is_present               # request_id 不为空
□ test_error_response_serializes_to_json   # Pydantic model_dump 输出正确 JSON
□ test_upstream_no_raw_field               # upstream 不允许 raw 字段
```

### Task 0.3: 兼容期 Schema（阶段 A）

**文件**：`app/schemas/error.py`（同上）

```
包含:
- CompatErrorResponse: 同时包含 detail (顶层) 和 error 对象
- 工厂函数: build_compat_error_response(...)
```

**测试**：`tests/phase5/test_error_schemas.py` — `TestCompatErrorResponse`

```
□ test_compat_response_has_both_detail_and_error
□ test_detail_matches_error_message
□ test_compat_response_success_is_false
```

---

## Phase 1: 核心异常层重构

### Task 1.1: 扩展 AppException

**文件**：`app/exceptions.py`（修改）

改动点：
```
AppException.__init__ 增加参数:
  - code: str = "UNIAPI_INTERNAL_ERROR"
  - type: str = "internal"
  - details: dict = None
  - suggestion: str = None
  - upstream: dict = None
  # data: Any = None  (保留兼容)
```

**测试**：`tests/phase5/test_exceptions.py` — `TestAppExceptionExtended`

```
□ test_app_exception_defaults              # 新参数默认值正确
□ test_app_exception_full_construction     # 所有字段可设置
□ test_app_exception_is_instance_of_exception
□ test_subclasses_unchanged_signature      # NotFoundException 等子类行为不变
```

### Task 1.2: 新增 Relay 专用异常子类

**文件**：`app/exceptions.py`（修改）

```
新增:
- RelayException(AppException): 默认 type 根据 code 推断
- UpstreamException(RelayException): 
    __init__(self, code, message, upstream_provider, upstream_status, upstream_code=None, upstream_message=None, upstream_request_id=None)
- 各子类便捷构造器或使用 build_xxx_error() 工厂
```

**测试**：`tests/phase5/test_exceptions.py` — `TestRelayExceptions`

```
□ test_relay_exception_inherits_app_exception
□ test_upstream_exception_builds_upstream_field
□ test_upstream_exception_default_code
□ test_upstream_exception_with_all_upstream_fields
```

### Task 1.3: 改造 app_exception_handler

**文件**：`app/exceptions.py`（修改）

改动点：
```
app_exception_handler 现在:
  1. 从 request.state 读取 request_id（由 RequestIDMiddleware 设置）
  2. 调用 build_error_response() 生成标准结构
  3. 阶段 A: 同时返回 detail 和 error
  4. 设置响应 status_code 为 error.status_code
```

**测试**：`tests/phase5/test_exception_handler.py` — `TestExceptionHandler`

```
□ test_handler_returns_standard_error_format
□ test_handler_returns_correct_status_code
□ test_handler_includes_request_id
□ test_handler_phase_a_includes_detail_field
□ test_handler_with_upstream_exception       # upstream 字段正确序列化
□ test_handler_unauthorized_subclass         # UnauthorizedException → UNIAPI_INVALID_TOKEN
□ test_handler_forbidden_subclass            # ForbiddenException → UNIAPI_ADMIN_REQUIRED
□ test_handler_not_found_subclass            # NotFoundException → UNIAPI_RESOURCE_NOT_FOUND
□ test_handler_quota_subclass                # QuotaExceededException → UNIAPI_QUOTA_EXHAUSTED
```

### Task 1.4: 注册 FastAPI HTTPException handler

**文件**：`app/main.py`（修改）

```
新增: 注册 HTTPException → 标准错误响应 的 handler
  - 将 FastAPI 原生的 HTTPException 也转换为标准 error 结构
  - 这样未迁移的旧代码也能输出统一格式（渐进迁移）
```

**测试**：`tests/phase5/test_exception_handler.py` — `TestHTTPExceptionHandler`

```
□ test_fastapi_http_exception_mapped_to_standard_format
□ test_http_401_maps_to_authentication_type
□ test_http_403_maps_to_authorization_type
□ test_http_429_maps_to_rate_limit_type
□ test_http_500_maps_to_internal_type
```

---

## Phase 2: 上游错误映射层

### Task 2.1: 创建上游错误映射模块

**文件**：`app/relay/upstream_errors.py`（新建）

```
功能:
- map_upstream_http_error(provider, status_code, response_body) → UniAPI error code + upstream dict
  映射规则（来自 spec §7.2）:
    429 → UPSTREAM_RATE_LIMITED
    404 → UNIAPI_MODEL_NOT_SUPPORTED（上游模型不存在）
    400/403 + content_filter → PROVIDER_<provider>_SAFETY_BLOCKED
    500-599 → UPSTREAM_UNAVAILABLE
- map_upstream_connection_error(provider, error_type) → UniAPI error code
    timeout → UPSTREAM_TIMEOUT
    connection → UPSTREAM_CONNECTION_FAILED
    其他 → UPSTREAM_BAD_RESPONSE

- extract_upstream_info(provider, httpx_response) → UpstreamErrorDetail
```

**测试**：`tests/phase5/test_upstream_errors.py` — `TestUpstreamErrorMapping`

```
□ test_map_429_to_upstream_rate_limited
□ test_map_404_to_model_not_supported
□ test_map_500_to_upstream_unavailable
□ test_map_502_to_upstream_unavailable
□ test_map_503_to_upstream_unavailable
□ test_map_connection_timeout_to_upstream_timeout
□ test_map_connection_refused_to_upstream_connection_failed
□ test_map_content_filter_to_provider_safety_blocked
□ test_map_unknown_4xx_passthrough
□ test_extract_upstream_info_from_response
□ test_upstream_info_includes_request_id_when_present
```

---

## Phase 3: 依赖层异常替换 (auth)

### Task 3.1: 替换 token_auth 中的 HTTPException

**文件**：`app/dependencies.py`（修改）

改动点（约 6 处 `raise HTTPException`）：
```
- "No token provided"        → UNIAPI_INVALID_TOKEN
- "Invalid token"            → UNIAPI_INVALID_TOKEN
- "Token is disabled/expired"→ UNIAPI_TOKEN_EXPIRED  
- "Token has expired"        → UNIAPI_TOKEN_EXPIRED
- "Token quota exhausted"    → UNIAPI_QUOTA_EXHAUSTED
- "User is disabled"         → UNIAPI_INVALID_TOKEN
```

**测试**：`tests/phase5/test_auth_errors.py` — `TestTokenAuthErrors`

```
□ test_no_token_returns_401_with_uni_api_invalid_token
□ test_invalid_token_returns_401_with_uni_api_invalid_token
□ test_disabled_token_returns_401_with_uni_api_token_expired
□ test_expired_token_returns_401_with_uni_api_token_expired
□ test_quota_exhausted_token_returns_401_with_uni_api_quota_exhausted
□ test_disabled_user_returns_401_with_uni_api_invalid_token
□ test_valid_token_still_works                         # 正常流程不受影响
□ test_channel_pinning_syntax_still_works              # "key:channel_id" 仍正常
```

### Task 3.2: 替换 user_auth / admin_auth / root_auth

**文件**：`app/dependencies.py`（修改）

```
- "Not logged in"            → UNIAPI_INVALID_TOKEN
- "Access denied"            → UNIAPI_ADMIN_REQUIRED
- "Admin access required"    → UNIAPI_ADMIN_REQUIRED
- "Root access required"     → UNIAPI_ADMIN_REQUIRED
```

**测试**：`tests/phase5/test_auth_errors.py` — `TestManagementAuthErrors`

```
□ test_unauthenticated_returns_uni_api_invalid_token
□ test_insufficient_role_returns_uni_api_admin_required
□ test_admin_auth_rejects_regular_user
□ test_root_auth_rejects_admin_user
□ test_root_auth_accepts_root_user
```

---

## Phase 4: Relay 层异常替换

### Task 4.1: 替换 Relay 业务错误（验证/权限/配额）

**文件**：`app/routers/v1/relay.py`（修改）

映射表（约 12 处 `raise HTTPException`，对应 247-451 行）：

| 行号 | 当前 detail | 新 code | 新 status |
|------|------------|---------|-----------|
| 247 | Token model not allowed | `UNIAPI_TOKEN_MODEL_NOT_ALLOWED` | 403 |
| 256 | Model not specified + restrictions | `UNIAPI_MODEL_NOT_SPECIFIED` | 400 |
| 267 | Fusion not available | `UNIAPI_INVALID_REQUEST` | 400 |
| 281 | No fusion-authorized models | `UNIAPI_TOKEN_MODEL_NOT_ALLOWED` | 403 |
| 325 | Insufficient token quota (fusion) | `UNIAPI_QUOTA_EXHAUSTED` | 402 |
| 348 | No channels for auto | `UNIAPI_CHANNEL_UNAVAILABLE` | 503 |
| 375 | No suitable model for auto | `UNIAPI_MODEL_NOT_SUPPORTED` | 400 |
| 387 | Model not supported | `UNIAPI_MODEL_NOT_SUPPORTED` | 400 |
| 399 | No enabled channels | `UNIAPI_CHANNEL_UNAVAILABLE` | 503 |
| 407 | No adaptor configured | `UNIAPI_INTERNAL_ERROR` | 500 |
| 413 | Token model not allowed (final) | `UNIAPI_TOKEN_MODEL_NOT_ALLOWED` | 403 |
| 424 | Group access denied | `UNIAPI_GROUP_ACCESS_DENIED` | 403 |
| 440 | Budget rejected | `UNIAPI_QUOTA_EXHAUSTED` | 402 |
| 449 | Insufficient token quota | `UNIAPI_QUOTA_EXHAUSTED` | 402 |
| 451 | Insufficient user quota | `UNIAPI_QUOTA_EXHAUSTED` | 402 |

**测试**：`tests/phase5/test_relay_errors.py` — `TestRelayBusinessErrors`

```
□ test_token_model_not_allowed_returns_403
□ test_model_not_specified_returns_400
□ test_fusion_not_available_returns_400
□ test_no_fusion_models_returns_403
□ test_insufficient_fusion_quota_returns_402
□ test_no_channels_for_auto_returns_503
□ test_no_suitable_model_auto_returns_400
□ test_model_not_supported_returns_400
□ test_no_enabled_channels_returns_503
□ test_no_adaptor_configured_returns_500
□ test_group_access_denied_returns_403
□ test_budget_rejected_returns_402
□ test_insufficient_token_quota_returns_402
□ test_insufficient_user_quota_returns_402
□ test_all_errors_include_request_id
□ test_all_errors_include_error_code
```

### Task 4.2: 替换 Relay 上游错误

**文件**：`app/routers/v1/relay.py`（修改）

改动点（574-657 行）：
```
- httpx.HTTPStatusError catch → 调用 upstream_errors.map_upstream_http_error()
  生成正确的 UniAPI code + upstream 字段，抛出 UpstreamException
- general Exception catch → 调用 upstream_errors.map_upstream_connection_error()
  生成正确的 UniAPI code，抛出 UpstreamException
```

**测试**：`tests/phase5/test_relay_errors.py` — `TestRelayUpstreamErrors`

```
□ test_upstream_429_maps_to_upstream_rate_limited
□ test_upstream_500_maps_to_upstream_unavailable
□ test_upstream_timeout_maps_to_upstream_timeout
□ test_upstream_connection_error_maps_to_upstream_connection_failed
□ test_upstream_error_includes_upstream_provider_field
□ test_upstream_error_includes_upstream_status_code
□ test_channel_auto_disabled_after_3_consecutive_failures
□ test_fallback_channel_success_clears_failure_count
□ test_quota_refunded_on_upstream_error
```

---

## Phase 5: 中间件适配

### Task 5.1: RateLimitMiddleware 输出标准错误

**文件**：`app/middleware.py`（修改）

改动点：
```
RateLimitMiddleware 当前输出:
  {"success": false, "message": "Rate limit exceeded"}

改为标准格式:
  {"success": false, "error": {"code": "UNIAPI_RATE_LIMITED", ...}}
```

同时增加 `request_id` 到响应中。

**测试**：`tests/phase5/test_middleware_errors.py` — `TestRateLimitMiddleware`

```
□ test_rate_limit_returns_standard_error_format
□ test_rate_limit_code_is_uni_api_rate_limited
□ test_rate_limit_status_is_429
□ test_rate_limit_includes_retry_after_header
□ test_rate_limit_response_has_request_id
```

### Task 5.2: RequestIDMiddleware 存储 ID 到 request.state

**文件**：`app/middleware.py`（修改）

改动点：
```
RequestIDMiddleware 当前只设置响应头 X-Request-Id。
需增加: request.state.request_id = request_id
这样 exception_handler 可以读取到 request_id。
```

**测试**：`tests/phase5/test_middleware_errors.py` — `TestRequestIDMiddleware`

```
□ test_request_id_stored_in_request_state
□ test_request_id_in_error_response_matches_header
□ test_request_id_from_client_header_preserved   # X-Request-Id 请求头
```

---

## Phase 6: 上游映射集成 + 端到端测试

### Task 6.1: 在 relay_chat_completion 中集成上游映射

**文件**：`app/relay/openai_compatible.py`（修改） + `app/routers/v1/relay.py`（修改）

改动点：
```
relay_chat_completion 中:
  - httpx.HTTPStatusError catch 中调用 upstream_errors.map_upstream_http_error()
  - 构建 UpstreamException 而非抛出泛型 HTTPException
  - relay.py 的 exception handler 自动处理 UpstreamException → 标准 error 响应
```

### Task 6.2: 端到端测试

**文件**：`tests/phase5/test_e2e_errors.py`（新建）

使用 `httpx.AsyncClient` + `ASGITransport` 模拟完整请求链路：

```
□ test_e2e_invalid_token_on_relay                    # /v1/chat/completions 无 token → 401 + UNIAPI_INVALID_TOKEN
□ test_e2e_model_not_allowed                         # 请求不允许的模型 → 403 + UNIAPI_TOKEN_MODEL_NOT_ALLOWED
□ test_e2e_model_not_specified_with_restricted_token # 受限 token 不指定模型 → 400 + UNIAPI_MODEL_NOT_SPECIFIED
□ test_e2e_quota_exhausted                           # 配额不足 → 402 + UNIAPI_QUOTA_EXHAUSTED
□ test_e2e_invalid_request_empty_body                # 空请求体 → 400 + UNIAPI_INVALID_REQUEST
□ test_e2e_model_not_found                           # GET /v1/models/nonexistent → 404 + UNIAPI_RESOURCE_NOT_FOUND
□ test_e2e_response_structure_matches_spec           # 响应结构与 spec §5 一致
□ test_e2e_compat_detail_field_present               # 阶段 A: detail 字段共存
```

---

## Phase 7: 快照测试 + 兼容性验证

### Task 7.1: 错误码快照测试

**文件**：`tests/phase5/test_error_snapshots.py`（新建）

```
对每个错误码生成一次响应并做快照比对:
□ test_snapshot_uni_api_invalid_token
□ test_snapshot_uni_api_token_expired
□ test_snapshot_uni_api_token_model_not_allowed
□ test_snapshot_uni_api_admin_required
□ test_snapshot_uni_api_group_access_denied
□ test_snapshot_uni_api_invalid_request
□ test_snapshot_uni_api_model_not_specified
□ test_snapshot_uni_api_model_not_supported
□ test_snapshot_uni_api_unsupported_parameter
□ test_snapshot_uni_api_resource_not_found
□ test_snapshot_uni_api_quota_exhausted
□ test_snapshot_uni_api_rate_limited
□ test_snapshot_upstream_timeout
□ test_snapshot_upstream_unavailable
□ test_snapshot_upstream_bad_response
□ test_snapshot_upstream_rate_limited
□ test_snapshot_upstream_connection_failed
□ test_snapshot_uni_api_service_disabled
□ test_snapshot_uni_api_channel_unavailable
□ test_snapshot_uni_api_internal_error

快照文件: tests/phase5/snapshots/error_codes.json
```

### Task 7.2: 兼容性回归测试

**文件**：`tests/phase5/test_compatibility.py`（新建）

```
确保阶段 A 改造后不影响现有测试:

□ test_existing_phase2_tests_pass
□ test_existing_phase3_tests_pass
□ test_existing_phase4_tests_pass
□ test_existing_glm_tests_pass
□ test_existing_test_api_tests_pass
□ test_old_app_exception_subclasses_still_work  # NotFoundException 等仍可用
```

---

## 文件变更清单汇总

| 文件 | 操作 | Phase |
|------|------|-------|
| `app/error_codes.py` | 新建 | 0 |
| `app/schemas/error.py` | 新建 | 0 |
| `app/exceptions.py` | 修改 | 1 |
| `app/main.py` | 修改 | 1 |
| `app/relay/upstream_errors.py` | 新建 | 2 |
| `app/dependencies.py` | 修改 | 3 |
| `app/routers/v1/relay.py` | 修改 | 4 |
| `app/middleware.py` | 修改 | 5 |
| `app/relay/openai_compatible.py` | 修改 | 6 |
| `tests/phase5/test_error_codes.py` | 新建 | 0 |
| `tests/phase5/test_error_schemas.py` | 新建 | 0 |
| `tests/phase5/test_exceptions.py` | 新建 | 1 |
| `tests/phase5/test_exception_handler.py` | 新建 | 1 |
| `tests/phase5/test_upstream_errors.py` | 新建 | 2 |
| `tests/phase5/test_auth_errors.py` | 新建 | 3 |
| `tests/phase5/test_relay_errors.py` | 新建 | 4 |
| `tests/phase5/test_middleware_errors.py` | 新建 | 5 |
| `tests/phase5/test_e2e_errors.py` | 新建 | 6 |
| `tests/phase5/test_error_snapshots.py` | 新建 | 7 |
| `tests/phase5/test_compatibility.py` | 新建 | 7 |
| `tests/phase5/__init__.py` | 新建 | 0 |

**新建**：15 个文件（5 个源码 + 10 个测试）
**修改**：6 个文件
**总计**：约 120 个测试用例

---

## 执行顺序 (TDD 循环)

```
循环 1: Phase 0  Task 0.1 (RED → GREEN → REFACTOR)
循环 2: Phase 0  Task 0.2 (RED → GREEN → REFACTOR)
循环 3: Phase 0  Task 0.3 (RED → GREEN → REFACTOR)
  ✓ 里程碑 1: 基础设施就绪

循环 4: Phase 1  Task 1.1 (RED → GREEN → REFACTOR)
循环 5: Phase 1  Task 1.2 (RED → GREEN → REFACTOR)
循环 6: Phase 1  Task 1.3 (RED → GREEN → REFACTOR)
循环 7: Phase 1  Task 1.4 (RED → GREEN → REFACTOR)
  ✓ 里程碑 2: 核心异常层完成

循环 8: Phase 2  Task 2.1 (RED → GREEN → REFACTOR)
  ✓ 里程碑 3: 上游映射就绪

循环 9: Phase 3  Task 3.1 (RED → GREEN → REFACTOR)
循环 10: Phase 3 Task 3.2 (RED → GREEN → REFACTOR)
  ✓ 里程碑 4: Auth 层迁移完成

循环 11: Phase 4 Task 4.1 (RED → GREEN → REFACTOR)
循环 12: Phase 4 Task 4.2 (RED → GREEN → REFACTOR)
  ✓ 里程碑 5: Relay 层迁移完成

循环 13: Phase 5 Task 5.1 (RED → GREEN → REFACTOR)
循环 14: Phase 5 Task 5.2 (RED → GREEN → REFACTOR)
  ✓ 里程碑 6: 中间件适配完成

循环 15: Phase 6 Task 6.1 + 6.2 (RED → GREEN → REFACTOR)
  ✓ 里程碑 7: 集成完成

循环 16: Phase 7 Task 7.1 + 7.2 (快照 + 回归)
  ✓ 里程碑 8: 全部完成，可合并
```

---

## 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| `HTTPException` handler 注册后影响管理 API | 管理 API 错误格式意外变化 | Phase 1.4 仅对 `/v1/*` 路径生效，管理 API 保持现有格式 |
| 异常子类行为变化破坏现有测试 | CI 失败 | Phase 7.2 先跑全量回归，每个 Phase 完成即跑 `pytest tests/ -v` |
| `request.state.request_id` 在异常时不可用 | request_id 缺失 | Phase 5.2 中 RequestIDMiddleware 在请求进入时即设置，早于任何异常 |
| 上游错误映射不完整 | 部分上游错误未规范化 | Phase 2 映射表覆盖所有已知场景，`.get()` fallback 到 `UPSTREAM_BAD_RESPONSE` |
