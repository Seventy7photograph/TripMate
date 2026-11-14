# Security Policy

## Supported Versions

| Version | Supported |
| --- | --- |
| 1.x | Yes |
| < 1.0 | No |

## Reporting a Vulnerability

请不要通过公开 Issue 披露安全漏洞。使用 GitHub 仓库的
**Security → Report a vulnerability** 私下提交报告，并包含：

- 受影响版本和组件
- 可复现步骤或最小 PoC
- 影响范围
- 是否可能泄露凭据、用户数据或执行任意代码
- 建议修复方向

维护者会先确认报告，再协调修复和披露时间。请给修复与回归验证保留合理时间。

## Secret Handling

- 不提交 `.env`、API Key、JWT Secret、数据库密码、用户数据或日志。
- Provider 凭据只通过服务端 Secret 或加密配置提供。
- 管理后台只显示密钥是否已配置，不返回原始值。
- 怀疑凭据泄露时，应立即轮换凭据并检查 Provider 账单与访问日志。

## Security Boundaries

- 用户上传、网页、附件、Tool 结果和 MCP 结果均是不可信输入。
- Tool 必须通过 Schema、allowlist、超时、预算和审计。
- MCP Gateway 只接受服务端固定 endpoint，不允许用户填写 URL。
- 外部 URL 必须阻止私网、回环和链路本地地址。
- 所有旅行、分享、附件、收藏和记忆资源必须校验 owner。

## Disclosure

修复发布后再公开技术细节。未经协调，请不要公开可直接利用的 PoC 或用户数据。
