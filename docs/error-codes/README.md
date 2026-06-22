# 错误代码系统改进方案 - 完整资源包

> ⚠️ **注意**: 本文档目录中的大部分审查/提案文档（ERROR_CODES_SUMMARY.md, ERROR_CODES_REVIEW.md, ERROR_CODES_IMPLEMENTATION_GUIDE.md, HTTP_ERROR_CODE_GUIDE.md, HTTP_ERROR_QUICK_REFERENCE.md, examples/）描述的是**迁移前的状态**（所有错误直接使用 HTTPException，AppException 定义但未使用）。
>
> **代码已完全迁移至新的错误码体系。** 当前实现：
> - 所有 relay 错误使用 `RelayException` / `UpstreamException`（位于 [app/relay/upstream_errors.py](../../app/relay/upstream_errors.py)）
> - 所有认证错误使用 `UnauthorizedException` / `ForbiddenException` 等子类（位于 [app/exceptions.py](../../app/exceptions.py)）
> - 错误码统一使用 `UNIAPI_` 前缀（定义在 [app/error_codes.py](../../app/error_codes.py)）
> - 响应格式为 `{"success": false, "error": {"code": "...", "type": "...", "status_code": ...}}`
> - 实际测试位于 [tests/phase5/](../../tests/phase5/) (246 tests)
>
> **唯一有效的规范文档是 [UNIAPI_ERROR_CODE_SPEC_DRAFT.md](UNIAPI_ERROR_CODE_SPEC_DRAFT.md)**，其与当前代码实现一致。
>
> 以下内容保留作为历史参考。

## 📂 目录结构

```
docs/error-codes/
├── README.md (本文件)
├── 📖 审查文档/
│   ├── ERROR_CODES_INDEX.md              - 文档导航索引
│   ├── ERROR_CODES_SUMMARY.md            - 5分钟总结
│   ├── ERROR_CODES_REVIEW.md             - 30分钟深度审查
│   ├── ERROR_CODES_IMPLEMENTATION_GUIDE.md - 15分钟实施指南
│   ├── HTTP_ERROR_CODE_GUIDE.md          - HTTP状态码详解
│   └── HTTP_ERROR_QUICK_REFERENCE.md     - 快速参考卡
├── 📖 前端集成/
│   ├── FRONTEND_INTEGRATION_GUIDE.md     - 详细集成指南
│   └── FRONTEND_QUICK_REFERENCE.md       - 快速参考
├── examples/
│   ├── examples/ERROR_CODES_EXAMPLE.py   - ErrorCode枚举定义
│   └── examples/EXCEPTIONS_IMPROVED_EXAMPLE.py - 改进的异常处理
└── tests/
    # 错误代码系统资源包

    错误代码、HTTP 状态码、前端集成和测试资源已统一收拢到此目录。

    ## 目录结构

    ```text
    docs/error-codes/
    ├── README.md
    ├── ERROR_CODES_INDEX.md
    ├── ERROR_CODES_SUMMARY.md
    ├── ERROR_CODES_REVIEW.md
    ├── ERROR_CODES_IMPLEMENTATION_GUIDE.md
    ├── HTTP_ERROR_CODE_GUIDE.md
    ├── HTTP_ERROR_QUICK_REFERENCE.md
    ├── FRONTEND_INTEGRATION_GUIDE.md
    ├── FRONTEND_QUICK_REFERENCE.md
    ├── examples/
    │   ├── ERROR_CODES_EXAMPLE.py
    │   └── EXCEPTIONS_IMPROVED_EXAMPLE.py
    └── tests/
            └── test_token_permissions.py
    ```

    ## 快速入口

    - [ERROR_CODES_INDEX.md](ERROR_CODES_INDEX.md) - 总索引
    - [ERROR_CODES_SUMMARY.md](ERROR_CODES_SUMMARY.md) - 5 分钟总结
    - [ERROR_CODES_REVIEW.md](ERROR_CODES_REVIEW.md) - 深度审查
    - [ERROR_CODES_IMPLEMENTATION_GUIDE.md](ERROR_CODES_IMPLEMENTATION_GUIDE.md) - 实施指南
    - [UNIAPI_ERROR_CODE_SPEC_DRAFT.md](UNIAPI_ERROR_CODE_SPEC_DRAFT.md) - UniAPI 错误码规范草案
    - [HTTP_ERROR_CODE_GUIDE.md](HTTP_ERROR_CODE_GUIDE.md) - HTTP 状态码详解
    - [HTTP_ERROR_QUICK_REFERENCE.md](HTTP_ERROR_QUICK_REFERENCE.md) - HTTP 快速参考
    - [FRONTEND_INTEGRATION_GUIDE.md](FRONTEND_INTEGRATION_GUIDE.md) - 前端集成指南
    - [FRONTEND_QUICK_REFERENCE.md](FRONTEND_QUICK_REFERENCE.md) - 前端快速参考
    - [examples/ERROR_CODES_EXAMPLE.py](examples/ERROR_CODES_EXAMPLE.py) - ErrorCode 示例
    - [examples/EXCEPTIONS_IMPROVED_EXAMPLE.py](examples/EXCEPTIONS_IMPROVED_EXAMPLE.py) - 异常实现示例
    - [tests/test_token_permissions.py](tests/test_token_permissions.py) - Token 权限测试

    ## 阅读建议

    - 想快速了解现状：先看 [ERROR_CODES_SUMMARY.md](ERROR_CODES_SUMMARY.md)
    - 想评估改进方案：再看 [ERROR_CODES_REVIEW.md](ERROR_CODES_REVIEW.md)
    - 想开始改代码：看 [ERROR_CODES_IMPLEMENTATION_GUIDE.md](ERROR_CODES_IMPLEMENTATION_GUIDE.md)
    - 想参考实现：看 [examples/](examples/)
    - 想参考测试：看 [tests/](tests/)

    ## 说明

    本目录仅收纳错误代码相关资料。项目入口仍保留在根目录的 [README.md](../../README.md) 和 [CLAUDE.md](../../CLAUDE.md)。
前端集成 (30分钟)
    ↓ FRONTEND_INTEGRATION_GUIDE.md
测试 (20分钟)
    ↓ tests/
```

---

### 路径 C：我只需要快速查询（5 分钟）
```
需要查错误代码？
    ↓ examples/ERROR_CODES_EXAMPLE.py

需要查HTTP状态码？
    ↓ HTTP_ERROR_QUICK_REFERENCE.md

需要查前端集成？
    ↓ FRONTEND_QUICK_REFERENCE.md
```

---

## 📞 常见问题速查

**Q: 我应该从哪里开始阅读？**
A: 从 `ERROR_CODES_INDEX.md` 开始选择适合你的角色的阅读路径。

**Q: 这个改进有多紧急？**
A: 中等优先级。系统当前是功能性的，改进主要是为了可维护性和用户体验。

**Q: 代码示例能直接用吗？**
A: 是的，`examples/` 中的代码可以作为参考实现直接使用。

**Q: 改进会破坏现有 API 吗？**
A: 不会。改进是向后兼容的，HTTP状态码保持不变。

**Q: 我能边改进边保持系统运行吗？**
A: 是的，建议分阶段改进，优先改进关键路径。

---

## 🎯 下一步

1. **选择你的角色** → 按照上面的快速导航选择文档
2. **阅读相关文档** → 理解问题和解决方案
3. **制定计划** → 使用 `ERROR_CODES_IMPLEMENTATION_GUIDE.md` 制定改进计划
4. **开始改进** → 使用 `examples/` 中的代码作为参考
5. **测试验证** → 使用 `tests/` 中的用例验证改进

---

## 📝 文档维护

这个资源包包含的所有文档都已完成，可以立即使用。随着改进的进行，建议：

1. 在 `docs/error-codes/` 中添加更多的实现示例
2. 添加改进完成后的最佳实践指南
3. 定期更新错误代码目录
4. 收集改进过程中的教训

---

**资源包创建时间：** 2026-06-21  
**总文档数：** 11 份  
**总行数：** ~1,000+ 行（文档 + 代码）  
**建议改进时间：** 10 小时  
**预期ROI：** 显著提升代码质量和可维护性
