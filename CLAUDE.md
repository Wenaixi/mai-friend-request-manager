# CLAUDE.md - 好友申请处理 (friend-request-handler) (whitefox_friend-request-handler)

## 1. 模块定位与系统职责
- **插件标识符**：`whitefox_friend-request-handler`
- **当前生效版本**：`v1.3.0`
- **托管仓库**：[`Wenaixi/friend-request-handler`](https://github.com/Wenaixi/friend-request-handler)
- **核心定位**：监听加好友事件，支持 Webhook（18080端口）与指令审批。

## 2. 关键工程规范与配置说明
- **配置路径**：`config.toml`（所有业务调优与鉴权参数收敛于此）；
- **数据持久化**：优先遵循 MaiBot SDK 标准持久化规范，不直接向源码目录写入易失数据；
- **编码与日志规范**：严格遵循 PEP 8 风格，文档与代码注释杜绝 emoji，避免虚假套话。

## 3. 本地深度定制与稳定性修复
支持 SDK 标准持久化目录 ctx.paths.data_dir，彻底消除了启动黄色告警。

---

## 上游项目与开源溯源
- **原作者 / 组织**：`whitefox`
- **官方上游仓库**：[https://github.com/whitefox/friend-request-handler](https://github.com/whitefox/friend-request-handler)
- **开源许可证**：`MIT`
- **分支演进模式**：本仓库作为主人的深度定制与生产维护分支（`Wenaixi/friend-request-handler`）。在保持与官方上游架构演进对齐的同时，锁死并持续维护针对本服务器生产环境的稳定性补丁与核心特性。
