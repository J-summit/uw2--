# OP 系统支持 UWealth 统一接口需求文档

日期：2026-05-11

## 目标

本轮目标是把 OP 与 UWealth 的历史多接口对接收敛为一个统一 OpenAPI command 入口，由 OP 通过 `type` 区分拉单、录入确认、NAV / unit 回写、完成、拒绝、主动推送交易和客户资料同步等业务动作。

统一入口需要同时解决以下问题：

- OP 可从 UWealth 拉取待处理订单，并先保存到 OP 本地待人工确认池。
- OP 可向 UWealth 回写订单录入结果、NAV / unit 成交结果、最终完成结果和拒绝结果。
- 普通交易订单从客户确认到 OP 处理完成形成可审计的状态闭环。
- 每次请求都具备统一鉴权、签名校验、幂等、防重、审计和错误返回。
- 保留与老系统 OP 字段、订单类型、workflow、审计表和存储过程语义的兼容映射。

## 固定接口口径

- 统一入口：`POST /openapi/fund/op/commands`
- 鉴权方式：OpenAPI HMAC-SHA256 签名。
- 请求幂等号：`requestId`，建议 UUID，全局唯一。
- 接口版本：`version` 默认 `1.0`。
- 请求时间戳：`timestamp`，毫秒。
- 批量规则：所有批量类请求遵循“全部成功或全部失败”，不支持部分成功。
- 审计要求：每次 OP 请求必须记录原始报文、处理结果、失败原因、关联订单和处理耗时。
- 状态推进要求：必须同时更新订单当前状态和 workflow history。

必传 header：

| Header | 必填 | 说明 |
| --- | --- | --- |
| `X-App-Id` | 是 | OP 分配的应用标识 |
| `X-Timestamp` | 是 | 请求时间戳，毫秒 |
| `X-Sign` | 是 | HMAC-SHA256 签名 |
| `Content-Type` | 是 | `application/json` |

签名内容：

```text
timestamp + method + path + queryString + body
```

请求外层格式：

```json
{
  "type": "ORDER_ENTRY_CONFIRM",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": 1778121000000,
  "request": {}
}
```

统一响应格式：

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": {}
}
```

## 固定业务口径

推荐 MVP 主闭环：

```text
ORDER_PENDING_QUERY
-> ORDER_ENTRY_CONFIRM
-> ORDER_NAV_CONFIRM / ORDER_UNIT_CONFIRM
-> COMPLETED
-> ORDER_REJECT
```

MVP 推荐覆盖订单类型：

- `B` Buy
- `S` Sell
- `DP` Deposit，排除 FPX 入金
- `WD` Withdrawal
- `FS` Force Sell，复用 Sell 类处理

常用 workflow：

| workflowCode | 含义 | 使用场景 |
| --- | --- | --- |
| `WF00000002` | Pending Client Approval | 客户待确认 |
| `WF00000004` | Pending Processing | 客户确认后等待 OP 处理 |
| `WF00000005` | Pending Confirmation | OP 已录入，等待成交确认 |
| `WF00000016` | Pending Execution | OP 已回写 NAV / unit，等待最终完成 |
| `WF00000010` | Complete Transaction | 交易完成 |
| `WF00000015` | Admin / OP Reject | OP 拒绝或失败 |
| `WF00000019` | Partially Paid | Debit Note 部分付款 |

状态推进要求：

- 必须校验当前状态是否允许目标动作。
- 必须同步更新订单当前状态和 workflow history。
- 失败或拒绝必须记录原因。
- `WF00000005` 是否作为强制节点需要业务确认。

## 阶段 0：背景与边界

当前 OP 与 UWealth 的历史对接存在两种模式：

1. UWealth 在客户确认订单后主动调用 OP 的 `IntegrationExt/*` 接口送单。
2. OP 在完成录入、NAV / unit、workflow 或直接入账后，回调 UWealth 的多个 `/OP/*` 接口。

新方案边界：

- OP 只调用 UWealth 统一 command 入口。
- UWealth 内部按 `type` 分发到不同业务处理器。
- 鉴权、幂等、审计、事务控制、状态推进和错误响应统一处理。
- 字段命名需兼容老 OP 口径，例如 `OrderCurr/orderCurr`、`Currency/currency` 差异在映射层消化。
- PRS / EPF 的 client code 后缀转换需延续老规则：`WP7`、`WP3`、`WE`。
- 老系统审计类型可映射到新统一命名，同时保留查询兼容。

参考资料：

- `uw2--/op/OP系统对接UWealth统一接口Demo.md`
- `uw2--/op/v1/OP对接UWealth统一接口流程图.md`
- `uw2--/op/v1/OP老系统接口实现说明.md`
- `uw2--/op/json/order_type_S_OD260408105203588491.md`
- `uw2--/op/openapi/openapi-integration-guide.md`

状态：统一入口方向已明确，具体签名配置、超时、重试和部分 workflow 推进规则仍需最终确认。

## 阶段 1：拉单与本地待人工确认池

`type`: `ORDER_PENDING_QUERY`

OP 可拉取 UWealth 中等待 OP 处理的订单，并先保存到 OP 本地待人工确认池。

需求：

- 本接口只用于查询和返回待处理订单，不自动确认 OP 已接单，不自动推进 workflow，不写入 `opOrderNo`。
- 查询 `workflowCode = WF00000004` 的待处理订单。
- 支持按 `orderTypes` 过滤；为空、缺省或空数组时表示查询全部待处理订单。
- 支持分页，至少支持 `pageSize`，建议补充游标或页码机制。
- 返回订单总数和订单列表。
- `DP` Deposit 订单中，FPX 入金必须排除，不进入 OP pull 范围。
- 返回字段需兼容 OP 当前接收口径，如 `accountCode`、`tradeDate`、`trnCode`、`stockCode`、`amount`、`unit`、`salesChargeRate`、`taxAmount` 等。
- OP 拉取成功后，必须先写入 OP 本地待人工确认池，状态为“待确认”。
- OP 操作员可在本地待确认池中查看订单详情、执行人工核对、删除或作废本地待确认记录。
- 删除或作废 OP 本地待确认记录只影响 OP 本地处理队列，不代表拒绝 UWealth 订单，不触发 UWealth workflow 变更。
- OP 操作员人工确认后，OP 才生成或确认 OP 单号，并显式调用 `ORDER_ENTRY_CONFIRM` 完成 UWealth 接单确认。

本地待人工确认池要求：

- OP 拉取订单后，需要按 `uwOrderNo`、`orderType`、`clientCode`、`fundCode`、金额、unit、币种、拉取时间、拉取批次等字段保存本地记录。
- 本地记录需要有明确状态，例如 `待确认`、`已确认`、`已删除`、`已作废`、`确认失败`。
- 操作员可查看待确认订单详情，人工核对后执行确认。
- 操作员可删除或作废待确认记录；删除或作废必须记录操作人、操作时间和原因。
- 已删除或已作废的本地记录不得继续发起 `ORDER_ENTRY_CONFIRM`。
- 人工确认时，OP 需要生成或确认 `opOrderNo`，并调用 UWealth `ORDER_ENTRY_CONFIRM`。
- 如果 `ORDER_ENTRY_CONFIRM` 调用失败，本地记录应进入 `确认失败` 或类似状态，允许人工重试。

验收标准：

- OP 能拉到 `B/S/DP/WD/FS` 中符合条件的订单。
- 已完成、已拒绝、非待处理状态订单不会被返回。
- FPX Deposit 不会被返回。
- 相同查询不会改变订单状态。
- 拉取成功不会自动产生 `WF00000005`，也不会自动写入 `opOrderNo`。
- OP 拉取订单后，订单先出现在本地待人工确认池，而不是自动向 UWealth 确认。
- 人工删除或作废本地记录后，不会调用 UWealth，也不会改变 UWealth 订单状态。
- 人工确认成功后，本地记录变为 `已确认`，并可关联 UWealth 返回结果。
- 人工确认失败后，本地记录保留失败原因，可重新发起确认。

状态：MVP 优先。

## 阶段 2：录入确认与回写闭环

`type`: `ORDER_ENTRY_CONFIRM`

OP 操作员在本地待人工确认池中完成核对并确认接单后，OP 向 UWealth 回写 OP 单号。

需求：

- 支持批量提交。
- 按 `uwOrderNo` 定位 UWealth 订单。
- 写入或更新 `opOrderNo`。
- 校验订单当前状态允许录入确认。
- 只有 OP 本地待确认记录处于人工确认通过状态时，才允许调用本接口。
- 成功后是否推进到 `WF00000005` 需要业务确认；推荐 MVP 先支持推进，并保留配置开关。
- 写入 workflow history。

验收标准：

- 成功请求返回 `uwOrderNo`、`opOrderNo`、`success`。
- 订单不存在时返回明确错误。
- 当前状态不允许时返回 `Invalid workflow status`。
- 未经 OP 人工确认的本地记录不会触发本接口。
- 同一 `requestId` 重试不重复写历史。

`type`: `ORDER_NAV_CONFIRM`

OP 对 Buy 订单回写 NAV、成交 unit、成交金额、币种、OP 主键等信息。

需求：

- 支持批量提交。
- 校验订单类型为 `B`，后续可扩展支持其他买入类订单。
- 校验 `uwOrderNo`、`clientCode`、`fundId`、`opPkId` 与订单上下文匹配。
- 写入交易明细、trust item / holding 影响。
- 状态成功推进到 `WF00000016`。
- `status != 1` 时应走拒绝或失败路径，具体映射需要业务确认。

验收标准：

- 成功后订单保存 NAV、unit、金额、币种等成交结果。
- 成功后写入 `TrnWorkFlowHistory(WF00000016)`。
- 重复请求不会重复写账。

`type`: `ORDER_UNIT_CONFIRM`

OP 对 Sell 或 Force Sell 订单回写卖出 unit、NAV、赎回金额、币种、OP 主键等信息。

需求：

- 支持批量提交。
- 校验订单类型为 `S` 或 `FS`。
- 写入成交 unit、NAV、gross / net amount、currency、fundId 等结果。
- 更新 trust item / cart / holding。
- 状态成功推进到 `WF00000016`。

验收标准：

- Sell 订单按 OP 回写结果更新成交信息。
- 成功后写入 `WF00000016` 历史。
- Force Sell 可按 Sell 分支处理，并保留 `type = FS` 口径。

`type`: `COMPLETED`

OP 在最终结算完成后，通知 UWealth 将订单推进到完成状态。

需求：

- 支持批量提交。
- 按 `uwOrderNo` 定位订单。
- 校验订单当前状态允许完成。
- 成功推进到 `WF00000010`。
- 写入 workflow history。
- 对 `DP` 和 `WD`，允许携带 OP 结算金额、币种、OP 主键等信息，并按对应业务更新账务。

验收标准：

- 普通订单成功进入 `WF00000010`。
- Buy / Sell 必须已完成必要成交数据回写后才能完成。
- 状态历史能看到 OP 完成节点。

`type`: `ORDER_REJECT`

OP 可拒绝无法处理的订单。

需求：

- 支持批量提交。
- 按 `uwOrderNo` 定位订单。
- 记录拒绝原因、操作人和 OP 单号。
- 按订单类型执行必要的占用回滚、cart / trust item 回滚或失败处理。
- 默认推进到 `WF00000015`，具体拒绝状态可按业务配置。
- 写入 workflow history。

验收标准：

- 被拒绝订单不能继续被 OP pull 为待处理。
- 拒绝原因可在后台或审计中查询。
- 相关资金、持仓或订单占用被正确释放。

状态：主闭环需求已定义，`WF00000005`、失败映射、DP / WD 是否必须录入确认等规则待确认。

## 阶段 3：OP 主动推送交易与资料同步

`type`: `OP_TRANSACTION_PUSH`

OP 可主动推送非 UWealth pull 流程产生的交易。

适用范围：

- `DV` Dividend
- `US` Unit Split
- `CN` Credit Note
- `IN` Interest
- 后续扩展 `DN/TI/TO`

需求：

- 支持批量提交。
- 按 `orderType` 分支处理。
- 创建 UWealth 订单、workflow history、trust item / holding 影响。
- 默认完成态为 `WF00000010`；`DN` 可使用 `WF00000019` 或其他业务状态。
- 请求字段需要基于 OP 实际 payload 补齐。

验收标准：

- OP 推送交易能在 UWealth 形成可查询的交易记录。
- 原始报文、OP 单号、客户、基金、金额、unit、NAV 等核心字段可审计。
- 重复推送不会重复入账。

`type`: `CLIENT_ONBOARDING` / `CLIENT_UPDATE`

OP 可同步客户开户或客户资料变更信息。

需求：

- 支持客户 onboarding 信息同步。
- 支持客户 email / mobile 等资料更新。
- 需要定义字段映射、主键匹配规则、冲突处理规则。
- 需要明确 OP 与 UWealth 谁是资料主数据源。

验收标准：

- 客户资料同步成功后可在 UWealth 查询。
- 重复请求不会重复创建客户。
- 资料冲突有明确失败或覆盖规则。

状态：后续扩展。

## 页面与操作能力

MVP 需要提供 5 个主要页面，用于支撑 OP 从拉单、本地人工确认、向 UWealth 发确认、后续回写到审计追踪的完整操作链路。

| 页面 | 用途 | 核心按钮数量 | 主要按钮 |
| --- | --- | ---: | --- |
| OP 拉单页面 | 从 UWealth 拉取 `WF00000004` 待处理订单，查询拉取结果 | 4 | 拉取订单、查询、重置、查看拉取批次 |
| 本地待人工确认池 | 展示已拉取但尚未发起 `ORDER_ENTRY_CONFIRM` 的本地订单 | 7 | 查看详情、人工确认、批量确认、删除、作废、重试确认、查看失败原因 |
| 已确认 / OP 处理中订单页面 | 展示已向 UWealth 发过 `ORDER_ENTRY_CONFIRM` 的订单 | 5 | 查看详情、回写 NAV / Unit、标记完成、拒绝订单、重试回写 |
| OP 回写结果页面 | 查询确认、NAV / unit、完成、拒绝等回写结果 | 4 | 查询、查看请求报文、查看响应报文、重新发送 |
| 接口审计 / 日志页面 | 查询统一接口调用链路、签名校验结果、幂等结果和失败原因 | 3 | 查询、查看详情、导出 |

页面权限要求：

- 拉取订单、人工确认、删除、作废、回写、重试和导出应受权限控制。
- 删除、作废、拒绝、重新发送等高风险操作需要记录操作人、操作时间和原因。
- 批量确认、批量重试应有二次确认，避免误操作。

状态：MVP 合计建议实现 5 个页面，约 23 个按钮 / 操作能力。实际 UI 可合并相同按钮入口，例如多个页面的 `查看详情` 和 `查询` 可复用组件。

## 通用业务规则

批量事务规则：

- 当 `request` 是数组时，整批在一个业务事务中处理。
- 任意一条记录校验或处理失败，整批失败并回滚。
- 不支持部分成功。
- 成功响应中的单条 `success` 只表示整批成功后的记录级结果明细。

拉取与接单确认边界：

- `ORDER_PENDING_QUERY` 是只读查询动作，只代表 OP 成功获取待处理订单列表。
- 拉取成功不代表 OP 已成功接单，不得自动触发 UWealth 接单确认。
- OP 需要先将拉取结果保存到本地待人工确认池，等待操作员核对。
- 操作员可删除或作废 OP 本地待确认记录；该动作只影响 OP 本地队列，不改变 UWealth 订单状态。
- OP 需要在操作员人工确认后，完成 OP 单号生成或确认，再主动调用 `ORDER_ENTRY_CONFIRM`。
- UWealth 只有收到 `ORDER_ENTRY_CONFIRM` 后，才允许写入 `opOrderNo`，并按配置决定是否推进 `WF00000005`。
- 如果后续需要避免多 OP worker 重复拉取，可单独设计 pull lock / lease / claim 机制；该机制不应等同于业务接单确认。

幂等规则：

- UWealth 首先按 `requestId` 做请求级去重。
- 相同 `requestId` 重试时，返回首次处理结果，不再次执行业务动作。
- 批量请求幂等粒度为整批，不允许只重放其中一部分记录。
- 业务校验建议同时参考 `type`、`uwOrderNo`、`opOrderNo`、`opPkId`。
- 需要落库保存 requestId、type、请求摘要、响应摘要和处理状态。

审计规则：

- 记录请求 header 中的 appId、timestamp、sign 校验结果。
- 记录请求外层字段：`type`、`version`、`requestId`、`timestamp`。
- 记录原始 request payload。
- 记录处理结果、失败原因、异常堆栈摘要。
- 记录关联订单号、OP 单号、客户号。
- 记录创建时间、处理耗时、来源 IP。

安全与可观测性：

- 所有请求必须通过 OpenAPI 签名校验。
- 请求时间戳超出允许窗口时拒绝。
- AppId / Secret 不允许写入代码或日志。
- 生产日志不得输出完整签名内容和敏感客户资料。
- 每类 `type` 需有请求量、成功量、失败量、平均耗时、重复请求量指标。
- 失败需要可按 `requestId`、`uwOrderNo`、`opOrderNo` 查询。
- 需要记录无法处理的异常请求，便于人工补偿。

性能要求：

- `ORDER_PENDING_QUERY` 单次默认最多返回 1000 条，具体上限需配置化。
- 批量回写接口需限制单批最大记录数。
- 待处理订单查询需有 `workflowCode`、`orderType`、更新时间或订单号索引支持。

## 错误码需求

| code | error | 场景 |
| --- | --- | --- |
| `0` | `null` | 成功 |
| `openapi.missing.params` | Missing required parameters | 缺少 header 或必填字段 |
| `openapi.unknown.app` | Unknown AppId | AppId 不存在 |
| `openapi.invalid.timestamp` | Invalid timestamp format | 时间戳格式错误 |
| `openapi.timestamp.expired` | Request expired | 请求过期 |
| `openapi.sign.verify.fail` | Signature verification failed | 签名校验失败 |
| `0200203` | OP order number mismatch | OP 单号不匹配 |
| `0200204` | Invalid workflow status | 当前状态不允许操作 |
| `0200205` | Order not found | 订单不存在 |
| `0200206` | Duplicate request | 重复请求 |
| `0200207` | Unsupported command type | 不支持的 `type` |

## 分阶段交付建议

Phase 1：统一入口与普通订单闭环

- OpenAPI 鉴权与签名校验接入。
- `POST /openapi/fund/op/commands` 统一入口。
- `ORDER_PENDING_QUERY`
- `ORDER_ENTRY_CONFIRM`
- `ORDER_NAV_CONFIRM`
- `ORDER_UNIT_CONFIRM`
- `COMPLETED`
- `ORDER_REJECT`
- 请求幂等表、审计表、错误码。
- 覆盖 `B/S/DP/WD/FS` 主流程。

Phase 2：OP 主动推送交易

- `OP_TRANSACTION_PUSH`
- 覆盖 `DV/US/CN/IN`
- 明确 `DN/TI/TO` 字段和状态。
- 完善 trust / holding 影响和对账规则。

Phase 3：复杂产品与客户资料

- `SW` Switch 完整流程。
- PRS / EPF 买卖回写。
- `RSP` 定投流程。
- `CLIENT_ONBOARDING`
- `CLIENT_UPDATE`
- OP 查询类接口是否纳入统一入口。

## 测试需求

启动测试：

- 后端启动测试必须覆盖 `op-service` 在本地 profile 下可启动成功，数据库迁移、MyBatis mapper、配置绑定、UWealth client bean、审计相关 bean 加载正常。
- 前端启动测试必须覆盖 `op-front` 开发服务可启动成功，`/api` 代理指向本地 `op-service`，订单页面、审计页面路由可正常加载。
- 联调启动测试必须通过根目录 `dev.ps1 up` 启动 `op-service + op-front`，并通过 `dev.ps1 status` 确认 `9090`、`9091` 服务端口正常。
- 启动后必须执行基础健康检查：后端健康接口或首页接口可访问，前端页面可打开，前端到 `/api` 的请求能到达 `op-service`。
- 启动失败必须保留日志证据，包括 `local-dev` 日志、op-service PM2 日志、前端 dev server 日志和端口占用信息。

单元测试：

- 每个 command handler 覆盖成功、必填缺失、状态不允许、订单不存在、重复请求。
- 批量请求覆盖整批成功、单条失败整批回滚。
- 幂等覆盖相同 `requestId` 重试。
- 字段映射覆盖 Buy、Sell、Deposit、Withdrawal。

集成测试：

- 签名通过和签名失败。
- OP 拉单后录入确认，再 NAV / unit 回写，再完成。
- OP 拒绝订单。
- 重复回写不会重复更新账务。
- FPX Deposit 不被 OP pull。

对账测试：

- UWealth 订单状态与 OP 回写状态一致。
- workflow history 完整。
- OP raw data 与业务处理结果可关联。
- Buy / Sell / DP / WD 金额、unit、NAV、currency 与 OP 报文一致。

## MVP 验收清单

- OP 后端、前端和本地联调环境必须通过启动测试。
- OP 能通过签名调用统一入口。
- OP 提供 5 个 MVP 页面：拉单、本地待人工确认池、处理中订单、回写结果、接口审计 / 日志。
- OP 能拉取 `WF00000004` 待处理订单。
- OP 拉取后先进入本地待人工确认池，支持人工确认、删除或作废。
- OP 能回写 `opOrderNo`。
- OP 能对 Buy 回写 NAV / unit 并推进 `WF00000016`。
- OP 能对 Sell / Force Sell 回写 unit / NAV 并推进 `WF00000016`。
- OP 能将订单推进 `WF00000010` 完成。
- OP 能拒绝订单并记录拒绝原因。
- 所有请求有 requestId 幂等控制。
- 所有请求有原始报文审计。
- 批量请求失败时整批回滚。
- FPX Deposit 不进入 OP pull。
- 关键失败场景返回明确错误码。

## 待确认问题

1. `WF00000005` 是否是 OP 录入确认后的强制状态，还是只写 `opOrderNo` 并保持 `WF00000004`。
2. 首期最终完成命令主名称已按当前 UWealth 实现统一为 `COMPLETED`；旧 `ORDER_EXECUTION_RESULT` 是否作为兼容别名需联调确认。
3. `ORDER_NAV_CONFIRM` 是否只用于 Buy，Sell 是否固定使用 `ORDER_UNIT_CONFIRM`。
4. `DP` 的 FPX 判断字段和 payment method 映射需要最终确认。
5. `DP`、`WD` 是否必须经过 `ORDER_ENTRY_CONFIRM`，还是可由 `COMPLETED` 直接完成。
6. OP 主动推送 `DV/US/CN/IN` 的实际 payload 字段需要 OP 提供。
7. `DN`、`RSP`、`SW` 是否纳入第一阶段。
8. 批量接口最大记录数、分页游标规则和查询排序规则需要确认。
9. 幂等数据保存期限和重复请求返回原响应的保留周期需要确认。
10. 客户资料同步中，OP 与 UWealth 谁是主数据源需要确认。

## 暂缓范围

本轮不包含：

- `SW` Switch 完整流程。
- `RSP` 定投流程。
- PRS / EPF 买卖回写差异。
- `CLIENT_ONBOARDING` 和 `CLIENT_UPDATE` 的完整字段映射。
- OP 查询 wrap fee / unrealised fee / unrealised interest 等查询类能力。
- `OP_TRANSACTION_PUSH` 中 `DN/TI/TO` 的完整 payload 和状态规则。
- 完整权限矩阵测试。
- 全部补偿、取消、重复提交和人工修复路径。

这些内容在普通订单主闭环和审计基线稳定后进入后续阶段。
