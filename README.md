# AstrBot Plugin: Claude Code

将 Claude Code 作为 LLM 函数工具集成到 AstrBot。

## 功能

- `claude_exec`: 在安全沙箱中执行文件操作
  - 创建/写入文件
  - 读取文件
  - 列出文件

## 安装

将插件目录放入 `/AstrBot/data/plugins/` 即可。

## 配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| workspace_name | 工作目录名称 | workspace |

## 安全

所有文件操作限制在 `workspace` 目录内，防止路径穿越攻击。
