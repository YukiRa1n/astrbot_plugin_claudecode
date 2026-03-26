# AstrBot Plugin: Claude Code

> **注意**: 测试版本，为避免 AI 执行危险操作，建议仅用于个人测试。喜欢的话给个 Star，有问题欢迎提 Issue/PR。

将 Claude Code CLI 作为 LLM 函数工具集成到 AstrBot。

## 功能

- 调用 Claude Code 执行编程任务
- 支持配置面板管理
- 自动安装 Claude Code CLI

## 配置逻辑 (重要)

本插件实现了 **“按需隔离”** 与 **“全局回退”** 机制，确保插件运行不会污染您本地的 Claude Code 设置：

1. **全局模式 (默认)**：
   - 当插件配置中的 `auth_token`、`api_key` 和 `api_base_url` 均为空时，插件将直接使用您系统全局的 Claude Code 配置（通常位于 `~/.claude/`）。
   - 适用于您已经在本地登录过 Claude Code 且希望插件沿用该登录状态的情况。

2. **隔离模式 (自动开启)**：
   - 只要您在插件配置中填入了 `auth_token`、`api_key` 或 `api_base_url` 中的任意一项，插件将开启隔离运行。
   - 插件会在其 `workspace` 下创建一份纯净的私有配置，绝不触碰或修改您系统的全局配置文件。
   - 没填写的项将自动回退到 Claude 官方默认值（而非系统全局值），确保环境纯净。

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

AGPL-3.0
