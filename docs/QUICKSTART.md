# 安装与后端接入

1. 从 [Releases](https://github.com/BeautyChaser/Supporter/releases) 下载安装包或ZIP，启动 Supporter。
2. 欢迎页检测本机工具。Supporter自带自身运行环境，AI对话需要至少一个已安装、已登录的后端。
3. 按官方说明安装和登录，再回欢迎页按 F5：

| 后端 | 官方说明 |
| --- | --- |
| Codex | [安装与登录](https://learn.chatgpt.com/docs/cli) |
| OpenCode | [下载与接入](https://opencode.ai/) |
| Hermes | [安装](https://hermes-agent.nousresearch.com/docs/getting-started/installation/) |

Supporter按本机PATH和插件路径检测，不代替账号授权。仅WSL内安装的CLI不等于Windows原生入口。

4. 选择模型、推理和快捷键。Luna报告支持时默认低档；“默认”继承CLI配置。
5. 在文本框中按Ctrl+Space，发送要求，选分支后Tab接受。

## 常见情况

- 快捷键与输入法冲突：在欢迎页或Ctrl+,设置中改为其他组合，例如 `Control+Alt+Space`。
- 后端未出现：确认CLI在本机能启动，F5重新检测；后台也会检查安装变化。
- 请求慢：查看实际档位、连接、首字等待和重试；设置中使用自己已有的连接/代理。分发版没有私人代理预设。
- 无法写回：Ctrl+V粘贴复制的结果，或 `/loc:window` 定位输入区。
- 毛玻璃影响阅读：在外观中关闭或提高背景浓度；系统模糊依赖Windows版本及透明效果设置。
- 失焦只隐藏；Esc清上下文；`/cancel`与生成中Ctrl+C只停止生成。

用户数据通常在 `%APPDATA%\Supporter`。程序卸载保留偏好；重置前请先退出并备份该目录。
