# 好友申请处理 (friend-request-handler)

> 本插件由 [Wenaixi](https://github.com/Wenaixi) 维护，是专为生产环境深度调优的高可用分支。

## 简介与定位

监听加好友事件，支持 Webhook（18080端口）与指令审批。

- **插件目录**：`whitefox_friend-request-handler`
- **生效版本**：`v1.3.0`
- **开源许可证**：`MIT`

---

## 核心特性与本地深度调优

- 支持 SDK 标准持久化目录 ctx.paths.data_dir，彻底消除了启动黄色告警

---

## 指令与工具速查

### 常用指令 (Command)
- `/同意 <QQ号> [备注] - 手动同意好友申请`
- `/拒绝 <QQ号> - 拒绝好友申请`

### 大模型工具 (Tool)
- `(好友事件监听型插件，无独立大模型工具)`

---

## 快速配置

配置文件统一定位于插件根目录下的 `config.toml`。修改后重启或通过 WebUI 热重载即可生效。

---

## 上游项目与开源溯源

- **原作者 / 组织**：`whitefox`
- **官方原版开源仓库**：[https://github.com/whitefox/friend-request-handler](https://github.com/whitefox/friend-request-handler)
- **开源协议**：`MIT`
- **声明**：本项目遵循开源协议，特此致敬原作者的杰出贡献。本分支针对生产环境的高并发网络、个性化社交和抗风控需求进行了深度稳定性修复与定制化演进。
