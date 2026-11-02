# Supporter

光标旁的全键盘 AI 输入助手。按 **Ctrl+Space** 唤醒，与 AI 对话，确认后用 **Tab** 将独立候选填入原位置。

支持 Windows 10/11 x64。安装包内置 Electron、Python 和原生输入组件，使用者无需另装 Node.js/Python。AI 对话使用本机已安装、已登录的 Codex / OpenCode / Hermes CLI，也可通过插件扩展。

## 下载与开始

从 [Releases](https://github.com/BeautyChaser/Supporter/releases) 下载：

- `Supporter-…-Setup-x64.exe`：安装版，提供开始菜单与卸载入口。
- `Supporter-…-x64.zip`：解压后运行 `Supporter.exe`。

首次启动提供环境检测与配置向导。选择后端、模型和快捷键后开始；尚未安装 AI CLI 时可先完成安装，再按[接入说明](docs/QUICKSTART.md)配置。

当前包未做代码签名，Windows 可能显示未知发布者提示。设置保存在当前用户的数据目录，升级覆盖程序文件时保留。

## 功能

- 多轮修改、独立回复与结果、分支选择、Tab 接受，多行文本保留换行。
- `/env:bash`、`powershell`、`cmd` 提供对应命令约束；终端填入时不发送 Enter。Markdown/text/code 保留原格式。
- 自检测可插拔后端：安装、卸载、停用、移除后自动更新列表，失效后回退并保留上下文。[插件说明](backend-plugins/README.md)。
- `/backend:…`、`/model:…`、`/reasoning:…` 按当前 CLI 目录和能力提供选项。
- 具体 shell 环境下，单反引号内自动命令补全；`/tool:completion` 查看来源，个人目录与本地习惯独立维护。
- `/loc:window` 用键盘定位原窗口输入区域；无法可靠写回时复制结果供 Ctrl+V。
- 系统/深浅色、主题色、字号、动效与毛玻璃。Windows 11 22H2+ 使用 Acrylic，其他系统使用半透明回退。

| 操作 | 按键 |
| --- | --- |
| 唤醒 | Ctrl+Space |
| 发送 / 换行 | Enter / Shift+Enter |
| 补全 / 接受所选候选 | Tab |
| 选择分支 | ↑↓ / Alt+数字 |
| 停止生成，保留对话 | Ctrl+C 或 `/cancel` |
| 关闭当前上下文 | Esc |
| 设置 | Ctrl+, |

失焦只隐藏，保留对话、草稿、候选和在途生成。输入 `/` 查看命令菜单。[完整说明](docs/USAGE.md)。

## 数据与兼容性

分发包采用干净默认设置，不包含作者的代理、账号、模型偏好或补全习惯。AI 请求通过所选本机 CLI 发送；Supporter 不收集登录密钥。习惯只存本地，不保存命令参数值、路径和对话。

特殊终端、TUI、多行提示符和远程编辑器可能无法提供可靠光标/编辑范围，接受前会校验目标并提供剪贴板回退。模型延迟受网络、服务负载和推理档位影响。

## 开发与 agent 维护

[开发验证](docs/DEVELOPMENT.md) · [架构](docs/ARCHITECTURE.md) · [发布](docs/RELEASING.md) · [测试](TEST_REPORT.md)

- [AGENTS.md](AGENTS.md)：项目维护约束。
- [.agents/skills](.agents/skills)：维护、后端插件、发布技能。
- [.codex/agents](.codex/agents)：前端测试、后端测试、发布审查角色。
- [第三方声明](THIRD_PARTY_NOTICES.md)。

源码构建需要 Node.js 22.12+、Python 3.11+ 和 Windows PowerShell。`npm ci` 后运行 `npm run dist:win`，产物位于 `release/`。
