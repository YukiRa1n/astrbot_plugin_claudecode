# AstrBot Plugin: Claude Code

将 Claude Code CLI 作为 LLM 函数工具集成到 AstrBot。

## 功能

- 调用 Claude Code 执行编程任务
- 支持配置面板管理
- 自动安装 Claude Code CLI

## 配置

| 参数 | 说明 |
|------|------|
| `workspace_name` | 工作目录名称 |
| `claude_md` | CLAUDE.md 内容(项目指令) |
| `auth_token` | Anthropic Auth Token (优先) |
| `api_key` | Anthropic API Key |
| `api_base_url` | 自定义 API 端点 |
| `auto_install_claude` | 自动安装 CLI |
| `allowed_tools` | 允许的工具(如 Bash,Edit,Read) |
| `disallowed_tools` | 禁用的工具 |
| `permission_mode` | 权限模式(default/acceptEdits/plan/dontAsk) |
| `add_dirs` | 额外允许访问的目录 |
| `skills_to_install` | 要安装的 Skills |
| `max_turns` | 最大轮数 |
| `timeout_seconds` | 超时时间 |

## License

MIT
