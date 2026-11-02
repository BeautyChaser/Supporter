# 自检测后端插件

本目录中的 `.json` 是后端注册入口，不需要修改主程序。内置 `codex.json`、`opencode.json`、`hermes.json`，每项都可单独停用或移除。检测依据是当前电脑的 PATH、Windows 用户/系统 PATH、插件路径声明及 CLI 版本探测，不保存另一台电脑的可执行文件绝对路径。

- 安装 CLI 后，对应插件检测通过才进入可选列表。
- 卸载/删除 CLI、停用插件（`"enabled": false`）或移除插件 JSON 后，从可选列表移除。
- 后台约每 10 秒巡检；唤醒助手、打开后端/模型/推理菜单时也会请求复查。F5 或 `/refresh` 强制更新模型目录。
- 可执行文件、插件描述、已知模型配置/缓存发生变化时重新验证；未变化的模型目录最多缓存 180 秒。重新验证阶段保留当前选择，确认不可用后才回退到其他可用后端。
- 回退保留对话、草稿和候选，在途请求继续完成；下一次请求使用新的可用后端。重装后重新出现，原模型偏好仍保留，可手动切回。
- 模型目录更新暂时失败时保留上次目录并标明待复核；没有任何可用后端时保留输入，不发起生成。

不同电脑分别使用本机 CLI 的登录和模型配置。目录检测成功不等于账号拥有调用所有模型的权限。当前桌面输入与快捷键集成面向 Windows。

## 增加自己的 CLI

复制 `custom-ai.json.example` 为新的 `.json`，按你的 CLI 非交互协议修改。示例中的程序名和参数是占位说明。其 CLI 需要接收完整提示，并通过 stdout 输出模型文字；Supporter 的提示要求模型文字本身遵循 `reply/kind/candidates` JSON 格式。

```json
{
  "schemaVersion": 1,
  "id": "my-agent",
  "label": "我的 CLI",
  "adapter": "generic",
  "detect": {"commands": ["my-agent.exe"], "versionArgs": ["--version"]},
  "models": {"args": ["models"], "format": "lines"},
  "reasoning": {"*": ["low", "medium"]},
  "generate": {
    "args": ["chat", "--oneshot", "--no-tools"],
    "modelArgs": ["--model", "{model}"],
    "reasoningArgs": ["--reasoning", "{reasoning}"],
    "stdin": "prompt",
    "output": {"format": "text"}
  }
}
```

`adapter` 可使用内置的 `codex`、`opencode`、`hermes` 协议，或无需改核心代码的 `generic` 协议。不同 `id` 可以复用同一适配器。

| 字段 | 含义 |
| --- | --- |
| `schemaVersion` | 必须为整数 `1`。 |
| `id` / `label` | 唯一标识（小写字母、数字、`_`、`-`）/显示名。 |
| `enabled` | 可选布尔值，默认 `true`。 |
| `priority` | 可选整数，较小值在前。 |
| `detect.commands` | 可执行命令名或路径；相对路径基于项目目录。 |
| `detect.pathGlobs` | 可选安装路径模式，支持环境变量和 `~`。 |
| `detect.versionArgs` | 只用于版本探测的固定参数，默认 `--version`。 |
| `detect.selection` | `first`（默认）或 `newest`；后者比较版本及预发布版本。 |
| `models.values` | 可选静态模型名数组。 |
| `models.args` | 可选模型目录命令参数。 |
| `models.format` / `field` | `lines` 或 `json`；JSON 可用点路径提取名称数组。 |
| `reasoning` | 模型名到档位数组的映射；`*` 为通用档位，未声明则仅有默认。 |
| `generate.args` | 非交互生成的参数数组，按真实 CLI 配置关闭执行工具。 |
| `generate.modelArgs` | 选具体模型时附加；选择 CLI 默认模型时省略。 |
| `generate.reasoningArgs` | 选非默认推理档位时附加。 |
| `generate.stdin` | `prompt`（默认，提示走标准输入）或 `none`。 |
| `generate.env` | 可选的固定子进程环境，不改全局环境。 |
| `generate.output.format` | `text`、`json` 或 `jsonl`。 |
| `generate.output.field` | JSON/JSONL 中模型文本的点路径，默认 `text`。 |
| `generate.output.eventType` | JSONL 可选 `type` 筛选条件。 |
| `generate.output.fromFile` | 布尔值；读取 `{output_file}` 而非 stdout。 |

生成参数模板：`{prompt}`、`{model}`、`{reasoning}`、`{query_file}`、`{output_file}`。模板一次替换，提示内出现同名花括号仍保持原文；参数以 argv/标准输入传递。通用插件使用原生可执行文件或 Python/Node 解释器入口，不支持 `.cmd`、`.bat`、`.ps1` 作为直接入口。使用解释器时，将固定脚本路径放在 `versionArgs`、模型参数及生成参数开头；这样脚本可以随项目迁移。

CLI 与模型探测有超时、缓存和并发限制；只会执行插件明确声明的版本/模型探测命令。插件描述错误会单独报告，其他插件继续可用。插件目录本身是用户维护的本地配置，请按真实 CLI 的协议填写。
