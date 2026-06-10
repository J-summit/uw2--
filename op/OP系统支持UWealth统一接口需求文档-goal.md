# OP 系统支持 UWealth 统一接口端到端目标案例

日期：2026-05-18
Change：`001-standalone-op-uwealth`
PRD 文档：`C:/workspace/2026-agentic/op-agent/docs/uw2--/op/OP系统支持UWealth统一接口需求文档.md`
负责人：`<op-owner>`

> 本文是 goal 模板案例，按当前 `op-agent` 代码实现和 PRD 对照生成。
> 目标是给后续 `/goal` 执行提供可验证、可追踪的样例口径；其中已实现内容标为“已落地”，未确认业务规则保留为“待确认”或“暂缓”。

## 目标

本轮目标是关闭 OP 操作员处理 UWealth 待处理订单的主业务闭环：OP 操作员在 `op-front` 打开订单队列页面，通过 `op-service` 拉取 UWealth `ORDER_PENDING_QUERY` 待处理订单，保存本地订单快照、命令审计、操作审计和 workflow history；随后在本地待人工确认池中执行人工确认、NAV / unit 回写、完成或拒绝，并通过审计页面追踪每次 UWealth command 的 request/response、结果、耗时和失败原因。

示例口径：

- 谁执行：OP 操作员。
- 从哪里开始：`/quotation/op-pull`、`/quotation/newOrderList`、`/quotation/processing-orders`、`/quotation/writeback-results`、`/quotation/audit-log`。
- 做什么动作：拉取订单、查看详情、人工确认、删除或作废本地记录、NAV / unit 回写、完成、拒绝、失败重试、查看审计。
- 系统必须产生什么结果：`op_order` 订单快照、`log_op_command_attempt` 命令审计、`log_op_operation_audit` 操作审计、`log_op_order_workflow_history` workflow history。
- 如何确认闭环结束：订单进入 `COMPLETED` / `REJECTED` / `DELETED` / `VOIDED` 等终态，或失败停留在 `COMMAND_FAILED` 并可从审计页定位到 `requestId`。

## 范围

本轮包含：

- `ORDER_PENDING_QUERY` 拉取 `WF00000004` 待处理订单，并保存本地订单快照。
- 拉取完成后展示本次返回总数、实际写入数、新增数、覆盖数，并展示被覆盖的重复订单明细。
- 本地待人工确认池：查询、详情、人工确认、删除、作废、失败原因与重试入口。
- 写回命令：`ORDER_ENTRY_CONFIRM`、`ORDER_NAV_CONFIRM`、`ORDER_UNIT_CONFIRM`、`COMPLETED`、`ORDER_REJECT`。
- 命令幂等：`requestId` 去重、重复请求回放、失败请求重新发送。
- 审计追踪：命令尝试、操作审计、workflow history、原始 request/response 保留。
- 前端 5 个 MVP 页面路由和 typed service 调用。
- 后端 targeted tests、前端 lint/test/build、本地 `dev.ps1 status`、核心接口冒烟验证。

本轮不包含：

- `OP_TRANSACTION_PUSH`、`CLIENT_ONBOARDING`、`CLIENT_UPDATE` 的完整实现。
- `SW`、`TI`、`TO` 的完整处理闭环。
- PRS / EPF 买卖回写差异、完整补偿、取消和人工修复路径。
- 完整生产权限矩阵、生产 AppId / Secret 配置、真实 UWealth 联调 endpoint。

## PRD 对照结论

| PRD 点 | 本轮目标/实现结论 | 说明 | 状态 |
| --- | --- | --- | --- |
| 统一入口 `POST /openapi/fund/op/commands` | 已落地在 `op-service` UWealth client 调用层 | `UWealthClientImpl` 按统一 envelope 调用 UWealth command URL，OP 对外本地 API 是 `/api/op/...` | 已确认 |
| `ORDER_PENDING_QUERY` 拉取待处理订单 | 已覆盖 | `OpOrderPullService` 生成 `ORDER_PENDING_QUERY` envelope，固定 `workflowCode = WF00000004`，支持 `orderTypes`、`pageNo`、`pageSize` | 已确认 |
| 拉取成功先进入 OP 本地待人工确认池 | 已覆盖 | `op_order.local_status = PULLED`，不自动写 `opOrderNo`，不自动执行 `ORDER_ENTRY_CONFIRM` | 已确认 |
| 拉取结果展示数量和重复覆盖明细 | 已覆盖 | 后端返回 `totalCount`、`pulledCount/savedCount`、`createdCount`、`overwrittenCount`、`overwrittenOrders`；前端保留最近一次拉取摘要并展示被覆盖记录的 `uwOrderNo`、`orderType`、`clientCode` / `accountCode`、覆盖前后 `localStatus`、`lastRequestId` | 已确认 |
| 本地删除或作废不改变 UWealth workflow | 已覆盖 | `DELETE_LOCAL` / `VOID_LOCAL` 只更新本地状态并写 operation audit / workflow history，不调用 UWealth | 已确认 |
| 人工确认后调用 `ORDER_ENTRY_CONFIRM` | 已覆盖 | 前端行操作和批量确认调用 typed service；后端要求 `opOrderNo` 且本地状态为 `PULLED` 或 `COMMAND_FAILED` | 已确认 |
| `ORDER_NAV_CONFIRM` 处理 Buy | 已覆盖 | 后端要求 `orderType = B`、状态为 `ENTRY_CONFIRMED`，校验 NAV 和 unit | 已确认 |
| `ORDER_UNIT_CONFIRM` 处理 Sell / Force Sell | 已覆盖 | 后端允许 `S` / `FS`，状态要求 `ENTRY_CONFIRMED`，校验 NAV 和 unit / soldUnit | 已确认 |
| `COMPLETED` 完成订单 | 已覆盖 | Buy 要求已 NAV 确认，Sell / FS 要求已 unit 确认，DP / WD 可在录入确认后完成 | 部分待确认 |
| `ORDER_REJECT` 拒绝订单 | 已覆盖 | 默认推进 `WF00000015` / `REJECTED`，允许状态可通过配置控制 | 部分待确认 |
| 批量全成全败 | 已覆盖为后端事务与批量 envelope | `executeBatch` 在同一事务内校验并发送，失败抛异常；仍需真实 UWealth 批量失败联调证据 | 待联调确认 |
| `requestId` 幂等与重复请求 | 已覆盖 | pull 使用 coordinator 与 command attempt；写回使用 `log_op_command_attempt.request_id` 唯一记录与 replay | 已确认 |
| 原始 request/response 审计 | 已覆盖 | `request_body` / `response_body` 存入 `log_op_command_attempt` | 已确认 |
| DP FPX 入金排除 | 已覆盖但字段仍需业务确认 | 当前按 `depositMethod`、`paymentMethod`、`payment_mode_code` 等 extra 字段匹配 `FPX` | 待业务确认 |
| PRS / EPF client code 后缀转换 | 已覆盖 pull 侧 | `WP7`、`WP3`、`WE` 转换为 `WWN` 口径 | 已确认 |
| 5 个 MVP 页面 | 已覆盖为路由/页面复用 | 当前路由包括拉单、本地待确认池、处理中订单、回写结果、审计日志 | 已确认 |
| `OP_TRANSACTION_PUSH`、客户资料同步 | 暂缓 | 当前应拒绝为 unsupported，不进入主闭环实现 | 暂缓 |

## 固定测试数据 / Fixture

默认测试账号：

| 角色 | 登录用户 | 登录密码 | 交易密码 / 操作密码 | 备注 |
| --- | --- | --- | --- | --- |
| Advisor | `testadvisor` | `123456a.` | `123456a.` | 顾问端页面、代客交易、客户选择相关流程优先使用 |
| Client | `testclient` | `123456a.` | `123456a.` | 客户端确认、交易密码弹窗、客户自助流程优先使用 |
| OP | `<op-user>` | `<op-password>` | `<op-password>` | OP 后台操作员，真实账号待确认 |

- 常用测试产品账户：`C00375WWN`
- 账户说明：`C00375WWN` 当前用于平时测试，已有持仓和余额，可优先作为 Unit Trust、Cash、持仓可用性相关流程的 fixture。

业务 fixture：

- 登录用户：`<op-user>`，本地开发可暂用前端默认 operator `OP001`。
- 登录密码：待确认。
- 交易密码 / 操作密码：本轮 OP 页面未实现操作密码校验，写“本轮不涉及”。
- 客户/账户：`C00375WWN` 或 UWealth mock response 中的 `accountCode` / `clientCode`。
- 核心表：`op_order`、`log_op_command_attempt`、`log_op_operation_audit`、`log_op_order_workflow_history`。
- 核心字段：`uw_order_no`、`order_type`、`workflow_code`、`op_order_no`、`op_pk_id`、`local_status`、`request_id`。
- 关键枚举：`PULLED`、`ENTRY_CONFIRMED`、`NAV_CONFIRMED`、`UNIT_CONFIRMED`、`COMPLETED`、`REJECTED`、`COMMAND_FAILED`、`DELETED`、`VOIDED`。
- 初始状态：UWealth `workflowCode = WF00000004`，OP 本地不存在或处于可重新拉取状态。
- 目标终态：`WF00000010 / COMPLETED`，或 `WF00000015 / REJECTED`，或本地 `DELETED` / `VOIDED`。
- Fixture 初始化方式：后端 service tests 使用 mock UWealth response；本地联调可通过 PostgreSQL 清理 `op_service` schema 后重新 pull。
- Fixture 清理方式：测试事务回滚或 H2 test migration；本地联调用唯一 `requestId` 和唯一 `uwOrderNo` 保持可重复。

## 当前业务与数据口径

- 主账本/主表：`op_order` 是 OP 本地订单快照事实来源。
- 业务主键：`uw_order_no` 唯一；不要与 `op_order_no` 或 `op_pk_id` 合并。
- 前端展示字段：`uwOrderNo`、`orderType`、`workflowCode`、`localStatus`、`opOrderNo`、`accountCode`、`clientCode`、`fundCode`、`amount`、`unit`、`currency`、`lastRequestId`；拉取结果区必须展示 `totalCount`、`pulledCount/savedCount`、`createdCount`、`overwrittenCount` 和覆盖记录明细。
- 后端交易字段：`requestId`、`type`、`operator`、`opOrderNo`、`payload.uwOrderNo`、`payload.nav`、`payload.unit`、`payload.opPkId`、`payload.currency`、`reason`。
- 订单类型与状态：拉取主要围绕 `WF00000004`；写回目标包括 `WF00000005`、`WF00000016`、`WF00000010`、`WF00000015`。
- 金额、单位或余额口径：OP 仅保存 UWealth / OP 回写字段，不在本地重新计算资金或持仓口径。
- 外部系统字段映射：保留 `uwOrderNo`、`opOrderNo`、`opPkId`、`orderType`、`workflowCode` 原字段语义。
- 不再使用或历史遗留表：老 OP / UWealth 存储过程和 raw data 仅作参考，不作为本地 OP 第一事实来源。
- 迁移或治理策略：使用 Flyway `V1__create_op_pull_tables.sql` 初始化 OP 业务与审计表。

## 阶段 0：诊断基线

状态：已完成

诊断目标：

- 确认 `PRD 文档` 路径已填写且文件可访问。
- 阅读 PRD，提取已确认规则、待确认项、验收标准和参考资料。
- 确认当前代码存在 `op-service`、`op-front`、Spec-Kit plan/spec/tasks/completion audit。
- 确认目标页面/API/任务入口存在。
- 确认核心表、字段、索引、迁移脚本、实体映射存在。
- 确认可复用的 service、controller、client、workflow history、审计 service 和前端 typed service。

完成标准：

- PRD 已读取，goal 中目标、范围、阶段、测试和暂缓项均能回溯到 PRD 或当前代码。
- `op-service` 存在 `/api/op/orders`、`/api/op/orders/pull`、`/api/op/orders/{uwOrderNo}/commands`、`/api/op/orders/commands/batch`、`/api/op/orders/{uwOrderNo}/local-actions`。
- `op-front` 存在 5 个 MVP 路由。
- `op_order`、`log_op_command_attempt`、`log_op_operation_audit`、`log_op_order_workflow_history` 已有 migration。

验证证据：

- 用例或检查项：PRD / template / code review。
- 命令：`Get-Content -Raw -Encoding UTF8 <PRD>`、`rg --files op-service`、`rg --files op-front`。
- 结果：通过。
- 关键证据：`OpOrderPullService`、`OpOrderCommandService`、`OpOrderController`、`routes.ts`、`orders.ts`、`V1__create_op_pull_tables.sql`。

## 阶段 1：前端主流程

状态：已落地，Playwright E2E 已补齐为当前 OP 订单主流程门禁

目标流程：

1. OP 操作员打开 `/quotation/op-pull` 或 `/quotation/newOrderList`。
2. 页面展示查询表单、拉取表单、订单表格、批量操作栏。
3. 用户输入 `requestId`、`operator`、`orderTypes`、分页参数后触发拉取。
4. 页面通过 `src/services/op/orders.ts` 调用 `POST /api/op/orders/pull`。
5. 拉取成功后展示 UWealth 返回总数、实际保存数、新增数、覆盖数；若 `uwOrderNo` 重复且本地记录被覆盖，页面必须展示这些覆盖记录明细。
6. 用户在待确认池中查看订单详情，执行 `ORDER_ENTRY_CONFIRM`、`DELETE_LOCAL`、`VOID_LOCAL`。
7. 用户在处理中页面执行 `ORDER_NAV_CONFIRM`、`ORDER_UNIT_CONFIRM`、`COMPLETED`、`ORDER_REJECT` 或失败重试。
8. 用户在审计页按 `requestId`、`uwOrderNo`、`opOrderNo`、`commandType`、状态和时间范围查询命令。
9. 详情页展示订单原始 payload 和 workflow history。

完成标准：

- 页面 API 调用必须经过 `src/services/op/orders.ts` 或 `src/services/op/audit.ts` typed service。
- 前端不能直接调用 UWealth。
- 路由必须通过 `/api/...` 代理到 `op-service`。
- 拉取完成反馈不能只显示一条 toast；必须在页面保留本次拉取摘要，至少包含 `requestId`、`totalCount`、`pulledCount/savedCount`、`createdCount`、`overwrittenCount`，并能展开查看覆盖记录列表。
- 所有高风险操作必须有禁用条件或二次确认。
- 如涉及页面主流程，必须新增或更新 Playwright E2E 测试。

验证证据：

- 用例：`op-front` lint/test/build；Playwright `op-front/e2e/op-orders/*.spec.ts`。
- 命令：`cd op-front; corepack yarn lint; corepack yarn test; corepack yarn build; corepack yarn test:e2e e2e/op-orders --project=chromium`。
- 结果：lint 通过；unit test 4 passed；build 通过；Playwright 5 passed。
- 关键证据：`op-front/config/routes.ts`、`op-front/src/pages/OpOrders/Pending/index.tsx`、`op-front/src/pages/OpOrders/Detail/index.tsx`、`op-front/src/pages/OpAudit/CommandAttempts/index.tsx`、`op-front/playwright.config.ts`、`op-front/e2e/op-orders/`。

## 阶段 2：后端主流程

状态：已落地

目标流程：

1. `OpOrderController` 接收 OP 前端请求。
2. controller 做权限和 request body 边界校验后委派 service。
3. `OpOrderPullService` 生成 `ORDER_PENDING_QUERY` envelope，调用 `UWealthClient`。
4. 成功响应中仅保存 `WF00000004` 且非 FPX Deposit 的订单。
5. 保存订单时区分新增和覆盖：同一 `uwOrderNo` 已存在且处于可被 pull 覆盖状态时，更新快照并记录覆盖明细；不可覆盖状态不得被静默重置。
6. pull response 返回 `totalCount`、`pulledCount/savedCount`、`createdCount`、`overwrittenCount`、`overwrittenOrders`。
7. `OpOrderCommandService` 校验 `requestId`、operator、命令类型、本地状态、订单类型和 payload 上下文。
8. 写回命令统一通过 UWealth command envelope 发送。
9. 成功后更新 `op_order` 本地状态和 workflowCode，并写入 workflow history。
10. 失败后写入 command attempt / operation audit，并把订单置为 `COMMAND_FAILED`。
11. 重复 requestId 返回首次处理结果，不重复执行业务动作。

失败规则：

- 未支持的 `type` 必须返回 `OP_COMMAND_TYPE_UNSUPPORTED`。
- 订单不存在必须返回 `ORDER_NOT_FOUND`。
- 状态不允许、订单类型不匹配、上下文字段不匹配必须拒绝。
- UWealth 返回失败或 item 失败时，不得推进业务状态到下一节点。
- 同一订单同一命令有 in-progress attempt 时，必须拒绝重复提交。

完成标准：

- 成功路径产生预期 `op_order` 状态变化和审计记录。
- 拉取路径必须能断言新增数、覆盖数和覆盖记录明细；覆盖只允许发生在 `PULLED` 或 `COMMAND_FAILED` 等可重新拉取队列状态。
- 失败路径没有不允许的 UWealth 或本地状态副作用。
- 并发、幂等、重复请求、失败重试和批量路径有后端测试覆盖。
- 所有 UWealth 调用保留 request/response 原始报文。

验证证据：

- 用例：`OpOrderPullServiceTest`、`OpOrderCommandServiceTest`、`OpCommandAttemptServiceTest`、`OpOperationAuditServiceTest`、controller tests。
- 命令：`cd op-service; mvn test`。
- 结果：本次验证为 165 tests 通过。
- 关键证据：`op-service/src/main/java/tech/tongyu/op/service/OpOrderPullService.java`、`op-service/src/main/java/tech/tongyu/op/service/OpOrderCommandService.java`。

## 阶段 3：外部、异步或工作流闭环

状态：已落地主闭环，真实 UWealth 联调待确认

目标流程：

1. OP 通过 `ORDER_PENDING_QUERY` 只拉取 UWealth `WF00000004` 订单。
2. OP 本地保存订单并等待人工确认。
3. 人工确认后调用 `ORDER_ENTRY_CONFIRM`，本地进入 `ENTRY_CONFIRMED`；配置允许时推进 `WF00000005`。
4. Buy 订单通过 `ORDER_NAV_CONFIRM` 写回 NAV / unit，进入 `NAV_CONFIRMED` 和 `WF00000016`。
5. Sell / Force Sell 订单通过 `ORDER_UNIT_CONFIRM` 写回 unit / NAV，进入 `UNIT_CONFIRMED` 和 `WF00000016`。
6. Buy / Sell / FS 完成后调用 `COMPLETED`，进入 `WF00000010` / `COMPLETED`。
7. DP / WD 当前允许在录入确认后直接 `COMPLETED`，该口径仍需业务确认。
8. 拒绝走 `ORDER_REJECT`，记录原因并进入 `WF00000015` / `REJECTED`。

完成标准：

- 拉取接口不会保存非 `WF00000004` 或 FPX Deposit。
- 每个外部 command 都有 `requestId` 和审计记录。
- workflow history 可按 `uwOrderNo` 查询。
- 外部字段映射完整且不改变 UWealth 字段语义。
- 真实 UWealth 环境联调通过后才能标为生产完成。

验证证据：

- 用例：pull / writeback service tests、UWealth client tests、OpenAPI signature tests。
- 命令：`cd op-service; mvn test -Dtest=OpOrderPullServiceTest,OpOrderCommandServiceTest,UWealthClientImplTest,OpenApiSignatureSupportTest`。
- 结果：历史完成审计记录为通过；本次生成文档未重新运行。
- 关键证据：`log_op_order_workflow_history`、`UWealthCommandEnvelope`、`UWealthClientImpl`。

## 阶段 4：失败、取消、拒绝与补偿

状态：部分已落地，完整补偿暂缓

目标流程：

1. UWealth 失败、超时、非 `0` code、item-level failure 或本地校验失败时，记录失败 command attempt。
2. 对已存在订单的写回失败，订单进入 `COMMAND_FAILED` 并保存 `commandFailureReason`。
3. 操作员可在订单页面或审计页对失败写回发起 retry，生成新的 retry requestId。
4. 本地删除或作废仅影响 OP 队列，进入 `DELETED` / `VOIDED`，不调用 UWealth。
5. `ORDER_REJECT` 成功时进入 `REJECTED` 并保存拒绝原因。
6. 重复触发同一 requestId 时回放首次结果。

完成标准：

- 失败路径必须可按 `requestId` 查到失败原因。
- 删除、作废、拒绝必须记录 operator、原因和操作审计。
- 重试只允许针对失败写回命令，不支持对 `ORDER_PENDING_QUERY` 做写回 retry。
- 完整资金、持仓、cart / trust item 释放由 UWealth 处理或后续规则确认，本地 OP 不自行发明补偿。

验证证据：

- 用例：`OpOrderCommandServiceTest` failure / retry / reject / local action cases。
- 命令：`cd op-service; mvn test -Dtest=OpOrderCommandServiceTest`。
- 结果：历史完成审计记录为通过；本次生成文档未重新运行。
- 关键证据：`COMMAND_FAILED`、`DELETE_LOCAL`、`VOID_LOCAL`、`ORDER_REJECT`。

## 阶段 5：数据、配置与迁移

状态：已落地

要求：

- Flyway migration 创建 `op_order`、`log_op_command_attempt`、`log_op_operation_audit`、`log_op_order_workflow_history`。
- `request_id` 在 `log_op_command_attempt` 中唯一。
- `uw_order_no` 在 `op_order` 中唯一。
- `application.yml` 配置 UWealth endpoint、timeout、batch size、pull page size、retry、`entry-confirm-advance-workflow`、FPX payment method values。
- 本地 profile 使用 PostgreSQL，本地禁用 Redisson autoconfig，保持 `dev.ps1` 启动方式。

完成标准：

- migration 可在 test profile 和本地 PostgreSQL 上执行。
- 实体字段与数据库字段一致。
- 配置不会破坏 `.\dev.ps1 up` 启动链路。
- 相关配置有测试或启动测试覆盖。

验证证据：

- 用例：`OpServiceApplicationStartupTest`、`UWealthPropertiesTest`。
- 命令：`cd op-service; mvn test -Dtest=OpServiceApplicationStartupTest,UWealthPropertiesTest`。
- 结果：历史完成审计记录为通过；本次生成文档未重新运行。
- 关键证据：`V1__create_op_pull_tables.sql`、`application.yml`、`application-local.yml`。

## 回归测试

本节是强制验收，不是建议项。

必须新增或更新的 Playwright E2E：

- `op-front/e2e/op-orders/pull-pending-orders.spec.ts`：覆盖拉单、重复 `requestId`、空结果或失败提示。
- `op-front/e2e/op-orders/pull-overwrite-summary.spec.ts`：覆盖第二次拉取同一 `uwOrderNo` 时，页面展示新增数、覆盖数和被覆盖订单明细。
- `op-front/e2e/op-orders/order-writeback-happy-path.spec.ts`：覆盖人工确认、NAV / unit 回写、完成。
- `op-front/e2e/op-orders/reject-local-actions-and-retry.spec.ts`：覆盖删除、作废、拒绝、失败重试。
- 如果项目暂未接入 Playwright，则必须先补齐 e2e 脚手架，或在 completion audit 中说明替代浏览器验证证据。

必须新增或更新的前端单元测试：

- `op-front/src/services/op/orders.test.ts`：typed service 路径和 payload。
- `op-front/src/pages/OpOrders/Pending/index.test.tsx`：按钮禁用、二次确认、错误提示。
- `op-front/src/pages/OpAudit/CommandAttempts/index.test.tsx`：筛选、详情 drawer、retry 可用性。

必须新增或更新的后端 targeted tests：

- `OpOrderPullServiceTest`：成功、空结果、UWealth 失败、重复 `requestId`、pull lock、FPX 排除、PRS/EPF suffix、新增数统计、重复 `uwOrderNo` 覆盖统计、覆盖明细返回、不可覆盖状态不被静默重置。
- `OpOrderCommandServiceTest`：5 类写回命令、状态不允许、订单不存在、上下文字段不匹配、批量全成全败、retry、duplicate replay。
- `UWealthClientImplTest`：签名 header、4xx 响应解析、空响应、invalid response、timeout/retry。
- `OpCommandAttemptServiceTest` / `OpOperationAuditServiceTest`：审计查询和保存。

前端测试必须覆盖：

- 主路径：拉单 -> 人工确认 -> NAV / unit 回写 -> 完成 -> 审计查询。
- 边界条件：空列表、分页、重复 requestId、重复 `uwOrderNo` 覆盖展示、失败重试、权限禁用。
- 前端校验失败：缺少 `opOrderNo`、缺少原因、缺少 NAV / unit。
- 后端返回业务失败：状态不允许、订单不存在、UWealth failure。
- 提交 payload 完整性：`uwOrderNo`、`opOrderNo`、`opPkId`、`requestId`、`operator`、`reason`。

后端测试必须覆盖：

- 成功路径。
- 业务拒绝且无副作用。
- 并发保护。
- 幂等保护。
- 本地删除/作废/拒绝和 retry 路径。

数据断言必须覆盖：

- 操作前：`op_order.local_status`、`workflow_code`、`op_order_no`、`last_request_id`、审计表记录数、重复 `uw_order_no` 的已有快照字段。
- 操作后：目标 `local_status` / `workflow_code`、`log_op_command_attempt.status`、`log_op_operation_audit.result`、`log_op_order_workflow_history.to_local_status`、覆盖后 `last_request_id` / `raw_payload` / `last_pulled_at`。
- 变化值：订单状态变化、审计新增、拉取新增数、拉取覆盖数、覆盖记录明细、重复 requestId 后不重复新增业务副作用。
- 查询方式：后端 service test、API 响应、SQL 查询、前端页面断言。
- 幂等断言：同一 `requestId` 重试返回 duplicate/replay，订单状态不再变化。

以下命令模板必须按实际模块替换，并在交付说明中保留执行结果：

```powershell
.\dev.ps1 status

cd op-service
mvn test

cd ..\op-front
yarn lint
yarn test
yarn build

cd ..
git diff --check
```

## /goal 完成门禁

标记 `/goal` 完成前，必须逐项确认：

- `PRD 文档` 路径已记录，且实现范围与 PRD 已确认规则一致。
- `specs/001-standalone-op-uwealth/` 的 plan/spec/tasks/completion audit 与代码一致。
- 相关后端单元测试已运行并通过。
- 相关前端 lint/test/build 已运行并通过。
- 如涉及页面主流程，Playwright E2E 已运行并通过；若未接入，必须有明确替代验证和后续 owner。
- 如涉及本地联调，必须通过 `.\dev.ps1 up` 或 `.\dev.ps1 status` 确认 `op-service 9090`、`op-front 9091`、`/api` proxy。
- 真实 UWealth endpoint / signing / timeout / retry 未联调前，不得声明生产完成。
- 未验证项必须明确写出原因、影响范围、替代验证方式和下一步负责人。

不能因为代码已修改、测试“应该能过”、或环境暂时不可用而标记 `/goal` 完成。

## 交付证据

交付说明必须包含：

- PRD 文档路径。
- 修改文件列表。
- 新增或更新的测试列表。
- 阶段状态与验证证据。
- 数据断言前后快照。
- 实际执行的验证命令及结果。
- 未执行验证项及原因。
- 剩余风险和后续建议。

## 已知依赖代码点

- `op-front/config/routes.ts`：5 个 OP MVP 页面路由。
- `op-front/src/services/op/orders.ts`：订单拉取、列表、详情、写回、本地动作 typed service。
- `op-front/src/services/op/audit.ts`：命令审计、操作审计、retry typed service。
- `op-front/src/pages/OpOrders/Pending/index.tsx`：订单队列、拉单、批量确认、行操作和 retry。
- `op-front/src/pages/OpOrders/Detail/index.tsx`：订单详情、原始 payload、workflow history、单笔命令操作。
- `op-front/src/pages/OpAudit/CommandAttempts/index.tsx`：命令审计、操作审计、详情 drawer、导出和 retry。
- `op-service/src/main/java/tech/tongyu/op/controller/OpOrderController.java`：订单 API 边界。
- `op-service/src/main/java/tech/tongyu/op/controller/OpCommandAttemptController.java`：命令审计 API。
- `op-service/src/main/java/tech/tongyu/op/controller/OpOperationAuditController.java`：操作审计 API。
- `op-service/src/main/java/tech/tongyu/op/service/OpOrderPullService.java`：`ORDER_PENDING_QUERY` 拉单与本地保存。
- `op-service/src/main/java/tech/tongyu/op/service/OpOrderCommandService.java`：写回命令、校验、状态推进、retry、批量命令。
- `op-service/src/main/java/tech/tongyu/op/service/OpCommandAttemptService.java`：命令审计与幂等记录。
- `op-service/src/main/java/tech/tongyu/op/service/OpOperationAuditService.java`：操作审计。
- `op-service/src/main/java/tech/tongyu/op/service/OpOrderWorkflowHistoryService.java`：workflow history。
- `op-service/src/main/java/tech/tongyu/op/client/UWealthClientImpl.java`：UWealth 统一 command client、签名、超时和 retry。
- `op-service/src/main/java/tech/tongyu/op/constants/OpConstants.java`：command type 和 workflow code 常量。
- `op-service/src/main/java/tech/tongyu/op/enums/OpOrderLocalStatus.java`：OP 本地状态枚举。
- `op-service/src/main/resources/db/migration/V1__create_op_pull_tables.sql`：OP 订单与审计表。
- `specs/001-standalone-op-uwealth/completion-audit.md`：历史完成审计和验证证据。
- `C:/workspace/2026-agentic/op-agent/docs/uw2--/op/OP系统支持UWealth统一接口需求文档.md`：PRD 来源。

## 已落地代码点

- `op-service/src/main/java/tech/tongyu/op/service/OpOrderPullService.java`：拉取待处理订单、过滤 `WF00000004`、排除 FPX Deposit、保存 raw payload、写 workflow history。
- `op-service/src/main/java/tech/tongyu/op/dto/OpOrderPullResult.java`：已有 `totalCount`、`pulledCount/savedCount`、`createdCount`、`overwrittenCount`、`overwrittenOrders`。
- `op-service/src/main/java/tech/tongyu/op/service/OpOrderCommandService.java`：写回命令、批量命令、本地删除/作废、retry、幂等 replay。
- `op-service/src/main/java/tech/tongyu/op/client/UWealthClientImpl.java`：统一 envelope 调用 UWealth、签名 header、响应解析和 retry。
- `op-service/src/main/resources/db/migration/V1__create_op_pull_tables.sql`：核心表和索引。
- `op-front/src/pages/OpOrders/Pending/index.tsx`：订单队列与操作入口。
- `op-front/src/pages/OpOrders/Detail/index.tsx`：订单详情与 workflow history。
- `op-front/src/pages/OpAudit/CommandAttempts/index.tsx`：命令/操作审计页面。
- `op-front/src/services/op/orders.ts` 和 `op-front/src/services/op/audit.ts`：前端 typed API。

## 暂缓范围

本轮明确不做：

- `OP_TRANSACTION_PUSH`、`CLIENT_ONBOARDING`、`CLIENT_UPDATE` 完整字段和业务实现。
- `SW`、`TI`、`TO` 首期完整回写闭环。
- PRS / EPF 买卖回写差异。
- UWealth 侧真实账务、holding、trust item、cart 释放或补偿逻辑。
- 完整生产权限矩阵和操作密码校验。
- 真实 UWealth 数据驱动的完整 Playwright E2E fixture 初始化。
- 生产 endpoint、AppId / Secret、超时、retry、签名窗口最终配置。

暂缓项必须满足：

- 不影响本轮 OP 拉单到写回主路径闭环。
- 不破坏当前验收门禁。
- 在后续独立 change 或业务确认后再进入实现。

## 风险与待确认项

- `WF00000005` 是否为 `ORDER_ENTRY_CONFIRM` 后强制状态，当前由 `uwealth.entry-confirm-advance-workflow` 配置控制，默认 `true`。
- 首期最终完成命令主名称已按当前 UWealth 实现统一为 `COMPLETED`；旧 `ORDER_EXECUTION_RESULT` 是否作为兼容别名需联调确认。
- DP / WD 是否必须经过 `ORDER_ENTRY_CONFIRM`，当前实现允许录入确认后直接完成。
- FPX Deposit 的最终判断字段和 payment method 映射仍需 UWealth / OP 业务确认。
- `ORDER_REJECT` 对不同 `orderType` / `workflowCode` 的允许状态仍需最终确认。
- `SW`、`TI`、`TO` 是否仅拉取展示，还是进入第一阶段完整处理，仍需确认。
- 真实 UWealth 批量全成全败、重复 requestId 返回首次结果、生产错误码映射需要联调证据。
- 前端 Playwright E2E 已补齐当前 mock `/api` 稳定覆盖；真实 UWealth 数据驱动 fixture 仍需后续联调确认。
- 拉取重复订单覆盖展示已补齐：后端返回 `createdCount`、`overwrittenCount`、`overwrittenOrders`，前端在拉单页展示本次拉取摘要和覆盖记录明细。
