# Supporter

Windows 全键盘编辑助手：Electron 前端浮层，Python 连接 Windows 输入和本机 Codex / OpenCode / Hermes CLI。默认 Codex + 检测到的 GPT Luna。

系统托盘右键可打开独立设置、查看说明或退出。Ctrl+, 或 `/settings` 同样打开设置。外观支持跟随系统/深色/浅色、六种强调色、字号、宽度、圆角、不透明度与过程显示开关。设置还包括唤醒快捷键、登录启动、CLI、模型与推理强度，支持预览和保存。设置组织参考 [zTools](https://github.com/ZToolsCenter/ZTools)。

运行 `start.cmd` 或 `python run.py`，按 Ctrl+Space 唤起。读取当前选区，没有选区则使用当前可编辑输入框。原文范围在浮层中显示。

Enter 发送要求，可多轮修改。AI 回复与待替换结果分开展示。Tab / Ctrl+Enter 确认后替换原文。失焦只隐藏到托盘，保留对话、草稿、候选和正在进行的生成；重新唤起继续。**Esc 关闭并清空当前上下文**。接受前重新校验目标和原文，内容变化、不可读或超过 16000 字符时停止自动替换。密码控件不读取。

命令请求按适用环境拆成独立分支。多个候选时先用 ↑↓ 或 Alt+1…8 选择，Tab 只接受所选命令，不会默认猜测显卡/平台，也不会把整段说明压成一行。混有多行、控制字符、注释或列表说明的命令会被拒绝。

只读网页选区仅作为参考。不可编辑或无法可靠写回时，Tab 复制所选候选到剪贴板并返回原窗口，可直接 Ctrl+V；不自动执行命令。Ctrl+Shift+C 可在任意位置复制候选。完整内容与换行保留。Ctrl+L 仍可保留上下文并更换输入位置。

多行普通编辑器使用完整文本粘贴；已识别的 Chrome 富文本输入使用软换行写入，避免普通 Enter 提交消息和浏览器粘贴新增空段落。接受的多行结果同时保留在剪贴板。

## 对话环境与冒号命令

`/env:bash` 使用 Linux/Bash 语法；`/env:powershell` 使用 PowerShell 语法；`/env:cmd` 使用 cmd 语法。`/env:markdown`、`/env:text`、`/env:code` 保留多行、段落、缩进与原始格式。`/env:auto` 根据输入环境判断。对话环境不等于底层输入控件，无法自动写回时仍可复制。

支持 `/model:模型名`、`/backend:codex`、`/reasoning:low` 等直接写法；冒号后提供值补全与说明。模型名自身的冒号（如 Ollama tag）不会被截断。生成中切换后端/模型/强度，会取消旧请求并用新配置重试当前要求。

## 命令补全与检测

显式选择 `/env:bash`、`/env:powershell` 或 `/env:cmd` 后，输入框内单反引号包围的命令自动获得补全。例如输入 ``请解释 `nvid` 的输出``，将光标留在 `nvid` 后按 Tab，可补成 `nvidia-smi`；`Get-ChildItem -Re`、`dir /`、`git st` 也分别提供对应环境的参数或子命令。↑↓ 选择，Tab / Enter 应用当前补全，只替换光标处的命令词。闭合反引号后按 Enter 发送对话。生成期间可继续补全草稿，不会停止 AI 请求。

`/tool:completion` 打开检测与来源面板；也可用 `/tool` 选择。无需手动启用，具体 shell 环境就是开启条件。`/env:auto` 即使识别到 Bash 也不自动开启，Markdown/text/code 同样不会启用 shell 补全。反引号内无法补全时，Tab 显示检测提示，不会误接受 AI 候选。

当前内置常用命令名、参数、Git 子命令及 NVIDIA 查询字段的公开文档目录，支持管道后命令与光标位于词中间的补全。字符串、注释、路径及参数值由用户填写。目录未收录不代表命令不存在；不执行用户输入、不调用 shell 自定义补全脚本、不读取远端文件，也不宣称已验证远端安装或完整命令语法。来源随匹配命令展示，包括 [GNU 手册](https://www.gnu.org/software/coreutils/manual/coreutils.html)、[PowerShell 文档](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-childitem?view=powershell-5.1)、[cmd 文档](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/dir)、[Git 文档](https://git-scm.com/docs/git) 和 [NVIDIA 文档](https://docs.nvidia.com/deploy/nvidia-smi/index.html)。

个人额外补全维护在 [`completions/user`](completions/user/README.md)。三个 shell 分别拥有自定义 JSON，支持命令、别名、参数、子命令与参数值候选。`habits.json` 根据你已发送的反引号命令及成功接受/复制的命令，积累名称、参数名、已知子命令及使用次数，常用项优先展示；不保存原始命令参数值、路径或对话，不把习惯库发送给 AI。仅预览补全与模型自动重试不计数。自动学习只写独立习惯文件，不改你的自定义目录。`/tool:completion` 或 F5 重载，`config.json` 可关闭学习，清空 `habits.json` 的 `environments` 可重置习惯。

## 全键盘定位输入区域

`/loc:window` 检测唤醒前的原窗口，列出可见、可编辑的输入区域。输入名称筛选，↑↓ 选择，Enter 聚焦；浮层随后跟随该区域重新定位，保留对话历史与候选，正在生成的请求继续运行。

定位只改变键盘焦点，不写入文本、不执行终端命令。密码、只读、禁用、隐藏、窗口边界外控件和其他顶层窗口均不列出；对控件数量和探测耗时设有限制。控件消失或系统不提供可用的辅助接口时会提示失败并保留上下文，可重新执行定位，或在原窗口用键盘聚焦后再唤醒。

## 全键盘操作

| 功能 | 快捷键 | 命令 |
| --- | --- | --- |
| CLI | Ctrl+B | /backend |
| 模型 | Ctrl+M | /model |
| 推理强度 | Ctrl+R | /reasoning |
| 终端模式 | Ctrl+T | /terminal |
| 选择候选分支 | ↑↓ / Alt+数字 | |
| 保留候选并更换输入框 | Ctrl+L | |
| 重新检测 | F5 | /refresh |
| 停止当前生成，保留上下文与草稿 | Ctrl+C（生成中） | /cancel |
| 命令补全检测与来源 | | /tool:completion |
| 定位原窗口的可输入区域 | | /loc:window |
| 清除本轮 | | /clear |
| 说明 | | /help |
| 关闭并清空当前上下文 | Esc | |
| 退出 | Ctrl+Q | /quit |

输入 `/` 查看带功能说明的菜单。上下选择，Tab 补全，Enter 执行。模型、后端、强度菜单可输入筛选。Shift+Enter 换行。中文输入法确认不会误发送。

`/cancel` 和生成期间的 Ctrl+C 只停止当前请求，保留对话和未发送草稿；停止后可继续输入新要求。停止后的迟到回复不会覆盖新请求。空闲时 Ctrl+C 保留普通复制行为，Ctrl+Shift+C 仍复制所选 AI 候选。

## 模型与推理

自动检测已安装 CLI、可启动状态与模型目录。目录不代表账号调用权限。设置保存到 `settings.json`，推理强度按后端和模型保存。

后端已改为自检测插件机制，注册入口为 [`backend-plugins`](backend-plugins/README.md)。启动、唤醒、打开相关菜单和后台巡检自动更新本机可用列表；删除 CLI、移除插件或设置 `enabled:false` 后自动移出可选项。当前后端确认失效后回退到其他可用后端，保留对话和候选；临时重新检测时保留原选择。所有后端不可用时保留输入并提示。不同 Windows 电脑使用各自 PATH/安装位置、登录与模型配置。

新增符合非交互协议的 CLI 可以添加 `adapter:generic` 的 JSON 描述，声明版本检测、模型目录、推理档位、生成参数和文本/JSON/JSONL 输出，不改主程序。现有三个后端也分别由插件描述注册，适配器实现独立。目录刷新保留设置页未保存的外观、连接、模型和推理草稿。

- Codex：读取缓存中模型声明的推理档位，使用 `model_reasoning_effort`。
- Hermes：提供 CLI 的 reasoning 档位；模型供应商是否接受以实际调用为准。`provider :: model` 同时指定供应商。
- OpenCode：读取配置中显式声明的 variants；未声明则只提供默认。本机 v2 使用 `provider/model#variant`，旧版使用 `--variant`。

Codex 使用 CLI 常驻 app-server，每轮独立临时只读线程，复用连接启动开销。Supporter 进程内禁用无关插件、MCP 和执行工具，不修改用户全局账号/provider。启动就绪时间与模型响应时间分开展示；模型或网络延迟不等于 CLI 初始化耗时。

Supporter 的 Codex/Luna 在未保存推理偏好且模型报告支持时默认使用 `low`；显式选择“默认”仍继承 CLI 的全局推理配置，可能是 `xhigh`。浮层和设置页保持一致，每次执行过程显示实际档位，支持仅返回最终文本时的首字计时。等待首字时每约 8 秒更新等待状态，重试单独计数。

Ctrl+, 打开设置 → AI 与模型 → Codex 连接，可选择跟随启动环境、直连或指定 HTTP(S) 代理。连接参数只用于 Supporter 的 Codex 子进程，保存后下次请求使用对应常驻连接；不修改系统代理、全局环境或 Codex 的账号与全局配置。代理地址不接受内嵌账号密码。

## 终端替换

Windows Terminal、传统控制台和 mintty 自动识别；内嵌终端可 Ctrl+T。识别常见 PowerShell、cmd、`$`、`#`、`❯` 提示符后的命令，在浮层显示待替换原命令。无法可靠识别时拒绝替换。

接受时使用 Home / Shift+End 选择当前行再输入，适用于支持这些编辑键的终端输入层。不同 shell、特殊提示符和多行命令仍需兼容性验证。每次仅接受所选单行命令，格式不合规则停止，不通过压平多行来修复，不发送 Enter。

## 界面与执行过程

无系统标题栏，默认宽 520 逻辑像素，随内容展开，优先显示在输入点上方，处理系统缩放、多显示器和负坐标。优先原生 caret，然后使用常驻 UI Automation 探针的文字范围或编辑框边界。空输入框锚定编辑框上缘；无法定位时明确提示回退。

窗口展开采用短时缓动，内容更新与测量合并，重复尺寸不再反复调整；输入框与底栏固定，上方长内容单独滚动。设置中的“平滑动效”可关闭动画。设置写入成功后自动关闭；保存失败或快捷键冲突则留在设置页。

不是正文中的原生 Ghost Text，无法保证所有应用都提供坐标或可编辑范围。浮层显示执行阶段、CLI / 模型 / 强度、耗时及错误，实时更新可用的 CLI 阶段事件。不会展示未公开的内部思考过程。原文、对话与候选只保留在当前进程内。

## 安装与验证

Windows 10/11、Python 3.11+、Node.js 22.12+、至少一个已登录 CLI。首次执行 `npm install`，再执行 `node node_modules/electron/install.js` 安装运行文件；`python -m pip install --target .vendor -r requirements.txt` 安装隔离的 Windows COM 依赖。`start.ps1` 编译本地辅助组件并启动。

验证：`npm run check`、`python -m unittest discover -s tests -v`、`node tests/placement.cjs`。CLI 检测：`python run.py --diagnose`。

动效逻辑：`node tests/motion.cjs`。隔离界面回归：`node_modules/electron/dist/electron.exe tests/ui-app`。富文本与只读范围回归：`node_modules/electron/dist/electron.exe tests/accessibility-app`。测试使用本地示例内容，不操作用户页面。

参考：[Codex 配置](https://learn.chatgpt.com/docs/config-file/config-reference)、[OpenCode CLI](https://dev.opencode.ai/docs/cli/)。Hermes 按本机帮助适配。
