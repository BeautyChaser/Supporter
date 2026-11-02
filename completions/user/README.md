# 个人命令补全目录

按环境维护 `bash.json`、`powershell.json`、`cmd.json`。这些文件属于用户，自动学习不会改写它们。`/tool:completion` 或 F5 重新读取目录；无需重启应用。

例如在 `bash.json` 中增加自己的工具：

```json
{
  "version": 1,
  "commands": [
    {
      "name": "mygpu",
      "description": "我的 GPU 检查工具",
      "aliases": ["mgpu"],
      "flags": [["--brief", "简短状态"], ["--device=", "选择设备"]],
      "subcommands": [["status", "查看状态"], ["watch", "持续查看"]],
      "values": {"--device=": [["0", "第一张卡"], ["1", "第二张卡"]]}
    }
  ]
}
```

同名命令可扩展内置参数。命令名、参数和子命令均为单个命令词；补全不会运行任何程序。目录加载错误会显示在工具面板，保留上次可用目录。

`habits.json` 自动积累实际发送的反引号命令，以及确认接受/复制的命令。仅保存命令名、参数名、已知子命令、次数与时间，用于优先展示常用项；不保存参数值、路径或对话。敏感名称参数不自动学习。看到补全或按 Tab 补词本身不会被计为使用。

自动识别环境不学习，必须显式设置 shell 环境。不同 shell 的习惯独立。自定义脚本的子命令请先在对应目录声明，再由使用次数排序。

将 `config.json` 的 `learning` 改为 `false` 停止后续学习，现有自定义目录和排序仍可用。清空 `habits.json` 的 `environments` 对象可重置习惯；`/tool:completion` 重新读取。此目录保存在本地项目，应用不会把习惯文件发送给 AI。
