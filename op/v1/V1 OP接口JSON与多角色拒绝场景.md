# V1 UWealth 与 OP 接口 JSON 及多角色拒绝场景

> 本文只描述 Legacy V1 的现行实现，用于理解和参考老系统行为。
> 文中的示例值均为说明性数据；字段、路由和状态规则来自无日期后缀的现行 WebAPI/WebApp 代码及已核验的 V1 数据资料。
> 存储过程源码不在当前代码仓库时，只记录 PHP 调用边界和可确认结果，不推测内部 SQL。

## 目录

- [1. 范围与证据](#1-范围与证据)
- [2. V1 通信模型](#2-v1-通信模型)
- [3. 角色、Action 与通用拒绝 JSON](#3-角色action-与通用拒绝-json)
- [4. 普通 Buy](#4-普通-buy)
- [5. PRS Buy](#5-prs-buy)
- [6. EPF Buy](#6-epf-buy)
- [7. Deposit](#7-deposit)
- [8. Sell](#8-sell)
- [9. Switch](#9-switch)
- [10. Withdrawal](#10-withdrawal)
- [11. 场景总表](#11-场景总表)
- [12. 已确认的实现边界](#12-已确认的实现边界)

## 1. 范围与证据

### 1.1 本文覆盖

本文覆盖以下 V1 交易结构：

1. 普通 Buy（B）
2. PRS Buy（B.PRS）
3. EPF Buy（B.EPF）
4. Deposit（DP）
5. Sell（S，含普通、PRS、EPF 变体）
6. Withdrawal（WD）

每一类都区分：

- 正常成功；
- OP 拒绝或处理失败；
- BFE 作为 Supervisor 拒绝；
- Client 拒绝；
- BFE 取消；
- Client 取消或撤回是否存在。

### 1.2 事实来源

| 范围 | V1 事实来源 |
| --- | --- |
| WebAPI 路由 | `C:/workspace/mar-fund/UnitTrustMYWebAPI/UnitTrustMYWebAPI/application/config/routes.php` |
| WebAPI 创建订单与 `TrnOrder` INSERT | `.../application/models/mdl_order.php:763-1420,2139-2205` |
| Buy/Sell 创建参数归一化 | `.../application/modules/transaction/controllers/ctrl_order.php:568-666,989-1010,1177-1262,1452-1486` |
| DP/WD 创建参数归一化 | `.../application/modules/transaction/controllers/ctrl_cash_deposit.php:29-142`；`.../ctrl_cash_withdrawal.php:27-113` |
| WebAPI 订单审批 | `.../application/modules/transaction/controllers/ctrl_order.php:733-952,2222-2255` |
| 状态和数据副作用 | `.../application/models/mdl_order.php:2309-2547,2766-2810` |
| UW 向 OP 送单 | `.../application/models/mdl_order.php:4208-4550` |
| OP 出站 URL 配置 | `.../application/config/config.php:661-672` |
| OP 回写 UWealth | `.../application/models/mdl_OP.php:30-813` |
| WebApp 页面提交与 OP 入站路由 | `UnitTrustMYWebApp/.../application/config/routes.php:378,390,443-455,694-704` |
| WebApp 审批页面 | `.../application/modules/Transactions/views/transaction/_vw_detail.php:658-715` |
| WebApp OP wrapper | `.../application/modules/OP/controllers/ctrl_OP.php` |
| Workflow 和 Action 常量 | `.../application/config/constants.php:294-317,341-348` |
| 已核验 V1 生命周期资料 | `C:/workspace/2026-agentic/wealth-agent/wealth-doc/biz/v1-op-json-lifecycle-analysis.md` |
| V1 完成后 `TrnOrder` 与 OP Raw Data 实例 | `C:/workspace/2026-agentic/wealth-agent/uw2--/op/json/order_v1.md` |

文件名带日期的备份文件不作为现行行为依据。

## 2. V1 通信模型

### 2.1 不是 OP 拉单

常规 B、S、DP、WD 的主路径是：

```text
Advisor/BFE/Client 在 UWealth 完成前置审批
  -> UWealth 主动 POST 业务 JSON 给 OP
  -> OP 返回 OP 单号
  -> OP 调用 /OP/update_* 回写成交成功或失败
  -> OP 调用 /OP/update_workflow 推进后续 workflow
```

V1 没有统一的待处理订单 pull 接口。

### 2.2 UW 向 OP 的出站响应

普通交易的 OP 接单响应不是结构化 JSON。V1 代码按文本处理：

```text
OD260701100000000001|UTF*260700001
```

代码要求响应：

- 非空；
- 不包含 `error`；
- 包含 `OD`。

满足条件后，V1 将 OP 单号写入 `TrnOrder.op_order_no`。

依据：`mdl_order.php:4524-4544,4551-4598`。

### 2.3 OP 调用 WebApp 的入站 JSON

OP 调用 WebApp `/OP/*` 时，直接发送业务 JSON，不带统一 envelope：

```json
{
  "OP_PK_ID": "UTF*260700001",
  "UW_order_no": "OD260701100000000001",
  "client_code": "A00001WWN",
  "status": 1
}
```

WebApp wrapper 解析 raw JSON，再转发给 WebAPI。OP 可见响应是 JSON scalar 字符串：

```json
"Data Passed: {\"OP_PK_ID\":\"UTF*260700001\",\"UW_order_no\":\"OD260701100000000001\",\"client_code\":\"A00001WWN\",\"status\":1}"
```

无效 JSON 时为：

```json
"Data Passed: null"
```

该字符串只证明 WebApp 已解析并尝试转发，不能证明 WebAPI 或存储过程处理成功。

### 2.4 WebApp 到 WebAPI 的内部 envelope

WebApp 调 WebAPI 时，逻辑明文结构为：

```json
{
  "user": {
    "login_id": "BFE_LOGIN",
    "client_code": null
  },
  "ip_address": "10.10.30.212",
  "data": {
    "orders": [
      {
        "order_no": "OD260701100000000001"
      }
    ],
    "action": "R",
    "reason": "Rejected by client",
    "password": "<hashed-password>"
  }
}
```

该明文会被 AES/Base64 加密。WebAPI 解密后，`getPostJson()` 只返回 `data`。

逻辑成功响应解密后为：

```json
{
  "status": 0,
  "data": []
}
```

常见错误码：

| status | 含义 |
| ---: | --- |
| `0` | Success |
| `3` | Incorrect format / validation failure |
| `7` | Invalid credential |

### 2.5 创建时 `TrnOrder` JSON 的阅读口径

后续各业务节中的“`TrnOrder` 创建快照”是把 V1 `INSERT INTO TrnOrder` 的数据库列表示成 JSON，便于与送往 OP 的 JSON 对比；它不是一个额外存在的 HTTP request。

统一约定：

- JSON 使用数据库列名，不使用 PHP 临时数组中的 `order_id/group/code/workflow` 别名；
- `submission_date/confirmation_date/settlement_date/cooling_off_date/contract_no/rsp_no/updated_*/payment_no/order_remark/cob_subm_id/op_order_no` 不在创建 INSERT 的 38 个字段内；快照按创建时状态列为 `null`；
- `op_order_no` 在 OP 接单成功后才回写，成交回调还会继续更新 `unit/nav/amount/workflow_code/updated_*` 等列；
- 示例统一使用 Non-Wrap `A00001WWN`、MYR 对 MYR 汇率 `1`、BFE `testadvisor`、开放式基金和无 Portfolio；
- 非 Deposit 由普通 BFE 创建时初始状态为 `WF00000002`；Intern/BFE4 创建时改为 `WF00000001`；
- 普通 BFE 创建 Deposit 时初始状态由付款方式决定，Cheque/Online Banking 为 `WF00000023`，FPX 为 `WF00000024`；Intern/BFE4 创建 Deposit 仍先进入 `WF00000001`；
- `order_date` 与 `created_at` 分别生成，生产数据中可能有毫秒差异；示例为便于阅读使用相同时间；
- `order_grouping` 与 `order_no` 也是两次独立取微秒时间生成，不是互换前缀得到；示例刻意使用不同后缀；
- `null` 表示 V1 创建代码明确传入空值或没有计算该字段，不应改读为数值 `0`。

字段落库顺序及审计字段来源：`mdl_order.php:2139-2205`。
`op/json/order_v1.md` 展示的是 OP 已处理后的真实最终行，不能直接当作创建时快照；例如 Sell 的 `amount/nav`、Buy 的 `unit/nav` 和 `updated_*` 都是在后续 callback 后才出现。

### 2.6 URL 归属与调用方向

本文中的 URL 分为三种，不能只看路径名称判断调用方：

| 类型 | 调用方向 | URL 由谁提供 | 说明 |
| --- | --- | --- | --- |
| UWealth 页面/WebAPI | Browser -> WebApp -> WebAPI | UWealth | 创建、审批等 UWealth 内部接口，不是 OP 接口 |
| UW 向 OP 出站 | UWealth WebAPI -> OP | OP | UWealth 将转换后的业务 JSON POST 到 OP 配置地址 |
| OP 回调 UWealth | OP -> UWealth WebApp -> UWealth WebAPI | UWealth | OP 调用 UWealth 的 `/OP/update_*`；WebApp wrapper 再转发 WebAPI 同名 route |
| `TrnOrder` 创建快照 | 无 HTTP 调用 | 无 | 是数据库 INSERT 后的展示，不是 request body，也没有独立 URL |

V1 当前配置中的 OP 出站 URL：

| 业务 | 调用方 -> 接收方 | OP 提供的当前配置 URL |
| --- | --- | --- |
| Buy、PRS Buy、EPF Buy、Sell、PRS Sell、EPF Sell | UWealth WebAPI -> OP | `POST http://10.10.20.100:8080/api/IntegrationExt/TransactionUnitTrust` |
| Switch | UWealth WebAPI -> OP | `POST http://10.10.20.100:8080/api/IntegrationExt/TransactionSwitch` |
| Deposit（非 FPX） | UWealth WebAPI -> OP | `POST http://10.10.20.100:8080/api/IntegrationExt/TransactionCashDeposit` |
| Withdrawal | UWealth WebAPI -> OP | `POST http://10.10.20.100:8080/api/IntegrationExt/TransactionWithdrawalRequest` |

OP 回调使用 UWealth 提供的 WebApp URL。下表只写相对路径，实际完整地址为部署环境的 UWealth WebApp base URL 加该路径：

| 业务事件 | 调用方 -> 接收方 | UWealth 提供的 URL |
| --- | --- | --- |
| 普通 Buy 成交/拒绝 | OP -> UWealth WebApp | `POST /OP/update_buy_transaction` |
| PRS Buy A/B 成交/拒绝 | OP -> UWealth WebApp | `POST /OP/update_buy_prs_transaction` |
| EPF Buy 成交/拒绝 | OP -> UWealth WebApp | `POST /OP/update_buy_epf_transaction` |
| 普通 Sell 成交/拒绝 | OP -> UWealth WebApp | `POST /OP/update_sell_transaction` |
| PRS Sell 成交/拒绝 | OP -> UWealth WebApp | `POST /OP/update_sell_prs_transaction` |
| EPF Sell 成交/拒绝 | OP -> UWealth WebApp | `POST /OP/update_sell_epf_transaction` |
| Switch 成交/拒绝 | OP -> UWealth WebApp | `POST /OP/update_switch` |
| Deposit 成交/拒绝 | OP -> UWealth WebApp | `POST /OP/update_cash_deposit` |
| Withdrawal 成交/拒绝 | OP -> UWealth WebApp | `POST /OP/update_cash_withdrawal` |
| 通用 workflow 推进 | OP -> UWealth WebApp | `POST /OP/update_workflow` |

OP 调用 WebApp 后，WebApp model 使用 `API_HOST + OP/update_*` 转发至 UWealth WebAPI。这是 UWealth 内部第二跳，不是 OP 再调用一次 WebAPI。

## 3. 角色、Action 与通用拒绝 JSON

### 3.1 V1 角色不能只按页面名称推断

| 代码身份 | 已确认行为 |
| --- | --- |
| `fa_type=b4` | 页面明确标为 Intern；创建的订单通常先进入 `WF00000001` |
| `fa_type=b` | BFE/FA；可在 `WF00000001` 执行 Supervisor Approve/Reject；自己创建的常规订单通常直接进入 `WF00000002` |
| Client | 仅能对有 approval right 的 `WF00000002` 订单执行 Approve/Reject |
| Backoffice 代 IFA | 部分常规订单可直接创建到 `WF00000004` |

因此：

- “Supervisor Reject” 是 `fa_type=b` 对 Intern 创建订单的拒绝；
- V1 没有另一个独立的 “Advisor Reject” event；
- Advisor/BFE 自己创建、等待 Client 确认的订单，如需终止，使用 Cancel，不使用 Reject；
- Client 没有 Cancel/Revoke action。

### 3.2 Action 字典

| action | 含义 | reason |
| --- | --- | --- |
| `A` | Approve | 不要求 |
| `R` | Reject | 必填 |
| `RS` | Resubmit | 必填 |
| `C` | Cancel | 不要求 |

### 3.3 Supervisor Reject

入口：

```text
WebApp POST /transaction/approval/bfe/_action
  -> WebAPI POST /order/flow/update
```

逻辑 JSON：

```json
{
  "password": "<hashed-password>",
  "orders": [
    {
      "order_no": "OD260701100000000001"
    }
  ],
  "action": "R",
  "reason": "Supervisor rejected the transaction"
}
```

规则：

| Actor | 前置状态 | 目标状态 |
| --- | --- | --- |
| `fa_type=b` | `WF00000001` | `WF00000011` Supervisor Reject |

不会送 OP，因为订单尚未到 Client Approve。

### 3.4 Client Reject

入口：

```text
WebApp POST /transaction/approval/client/_action
  -> WebAPI POST /order/flow/update
```

逻辑 JSON：

```json
{
  "password": "<hashed-password>",
  "orders": [
    {
      "order_no": "OD260701100000000001"
    }
  ],
  "action": "R",
  "reason": "Client declined the transaction"
}
```

规则：

| Actor | 前置状态 | 目标状态 | 额外条件 |
| --- | --- | --- | --- |
| Client | `WF00000002` | `WF00000012` Client Reject | 必须具有本人或联名账户 approval right |

拒绝发生在 OP 送单之前，不通知 OP。

### 3.5 BFE Cancel

入口页面：`/transaction/amendment`，页面名称为 Transaction Cancellation。

```json
{
  "password": "<hashed-password>",
  "orders": [
    {
      "order_no": "OD260701100000000001"
    }
  ],
  "action": "C",
  "reason": ""
}
```

`fa_type=b` 可在以下状态 Cancel：

| 前置状态 | 目标状态 |
| --- | --- |
| `WF00000002` | `WF00000020` Client Cancellation |
| `WF00000023` | `WF00000020` Client Cancellation |
| `WF00000024` | `WF00000020` Client Cancellation |

这里的 `WF00000020` 名称虽然是 Client Cancellation，但该页面/API 的实际操作者是 BFE，不是 Client。

`fa_type=b4` 的校验层也允许部分状态发送 `C`，但 `generate_update_workflow()` 的 BFE4 分支没有为 `C` 赋目标 workflow。这是现行 V1 代码缺口，不能写成已确认成功路径。

### 3.6 Client Cancel/Revoke

不适用：

- Client 在 `WF00000002` 只允许 `A` 或 `R`；
- Client 页面只有 Approve/Reject；
- Action 常量中没有独立 Revoke；
- `C` 是 BFE 侧的 Transaction Cancellation。

### 3.7 人工拒绝的通用落库

`update_complete_order()` 对 `R` 的通用处理包括：

1. 写 `TrnRejectReason`；
2. 写 `TrnWorkFlowHistory`；
3. 更新 `TrnOrder.workflow_code`；
4. 生成拒绝通知。

对 Buy 和 Withdrawal，`R` 或 `C` 还会：

1. 按原 `TrnOrderPayment` 回补 `TrnTrustItemCart`；
2. 将付款分摊复制到 `TrnRejectOrderPayment`；
3. 删除原 `TrnOrderPayment`。

Sell 没有这段显式的 Cash Account cart/payment 回补分支。

### 3.8 OP 拒绝的两种入口

标准业务拒绝由交易结果 callback 的 `status=0` 表达：

```json
{
  "UW_order_no": "OD260701100000000001",
  "status": 0
}
```

对应 `usp_UpdateProcessed*` 的失败分支，已核验结果为 `WF00000015`。回调没有通用 `reason` 或 `remark` 字段。

此外 OP 也能调用通用 workflow callback。调用方向是 `OP -> UWealth WebApp`，该 URL 由 UWealth 提供；WebApp 再内部转发至 WebAPI：

```http
POST /OP/update_workflow
```

```json
{
  "UW_order_no": "OD260701100000000001",
  "client_code": "A00001WWN",
  "workflow_code": "WF00000015",
  "ip_address": "169.254.1.2"
}
```

PHP 层没有校验当前 workflow，也没有限制目标 workflow；最终限制取决于 `usp_UpdateWorkflow_OP`。因此本文将 `status=0` 作为标准 OP Reject 路径，将直接传 `WF15` 记录为低层通用能力。

## 4. 普通 Buy

### 4.1 页面和接口

| 环节 | 调用方 -> 接收方 | URL 归属 | Route/URL |
| --- | --- | --- | --- |
| Buy 页面 | Browser -> UWealth WebApp | UWealth 提供 | `GET /transaction/buy` |
| 页面提交 | Browser -> UWealth WebApp | UWealth 提供 | `POST /transaction/_buy_order` |
| 创建订单 | UWealth WebApp -> UWealth WebAPI | UWealth 内部 | `POST /transaction/order/buy` |
| UW 向 OP 送单 | UWealth WebAPI -> OP | OP 提供 | `POST http://10.10.20.100:8080/api/IntegrationExt/TransactionUnitTrust` |
| OP 成交回调 | OP -> UWealth WebApp | UWealth 提供 | `POST /OP/update_buy_transaction` |
| OP workflow 回调 | OP -> UWealth WebApp | UWealth 提供 | `POST /OP/update_workflow` |

### 4.2 创建时 `TrnOrder` JSON

**URL 与方向：**该 JSON 是 `TrnOrder` 数据库创建快照，`HTTP URL：无`，不会将这份数据库列 JSON 原样发送给 OP。产生它的调用链为：

```text
Browser -> UWealth WebApp: POST /transaction/_buy_order
UWealth WebApp -> UWealth WebAPI: POST /transaction/order/buy
UWealth WebAPI -> UnitTrust.dbo.TrnOrder: INSERT
```

普通 BFE 创建时通常先等待审批，不在本快照步骤调用 OP；订单达到送 OP 条件后，才由 4.3 的 OP JSON 调用 OP 提供的 `TransactionUnitTrust` URL。管理员直接创建是例外，完成本地 INSERT 后可以立即送 OP。

以下示例对应申购金额 MYR 1,000、销售费率 1.5%、SST 8% of sales charge、汇率 1：

```json
{
  "order_no": "OD260701100000000001",
  "order_grouping": "OG260701100000000000",
  "fund_id": "FN000000001",
  "client_code": "A00001WWN",
  "branch": "S51",
  "BFECode": "BFE0001",
  "BFESubCode": null,
  "order_type": "B",
  "order_date": "2026-07-01 10:00:00.000",
  "submission_date": null,
  "portfolio_code": null,
  "payment_mode_code": "PM00000001",
  "payment_curr_code": "MYR",
  "fund_curr_code": "MYR",
  "unit": null,
  "amount": 1000.00,
  "nav": null,
  "total_charges": 15.94,
  "net_amount": 984.06,
  "curr_rate": 1,
  "m_curr_rate": 1,
  "f_amount": 1000.00,
  "f_nav": null,
  "f_total_charges": 15.94,
  "f_net_amount": 984.06,
  "m_amount": 1000.00,
  "m_nav": null,
  "m_total_charges": 15.94,
  "m_net_amount": 984.06,
  "bank_code": null,
  "bank_subcode": null,
  "cheque_no": null,
  "cheque_type": null,
  "cheque_date": null,
  "dividend_instruction": "R",
  "workflow_code": "WF00000002",
  "confirmation_date": null,
  "settlement_date": null,
  "cooling_off_date": null,
  "contract_no": null,
  "rsp_no": null,
  "created_by": "testadvisor",
  "created_at": "2026-07-01 10:00:00.000",
  "created_ip": "169.254.1.2",
  "updated_by": null,
  "updated_at": null,
  "updated_ip": null,
  "payment_no": null,
  "order_remark": null,
  "cob_subm_id": null,
  "op_order_no": null
}
```

销售费率和 SST 明细不在 `TrnOrder`，而在同次创建的 `TrnOrdCharges`。OP 字段来源如下：

| OP 字段 | V1 来源/计算 |
| --- | --- |
| `amount` | `abs(TrnOrder.amount)`，Non-Wrap Buy 为 1,000.00 |
| `OrderCurr` | `TrnOrder.payment_curr_code` |
| `OrderExRate` | `TrnOrder.curr_rate` |
| `AmountSC` | `TrnOrder.f_amount` |
| `salesChargeRate` | `TrnOrdCharges.percentage` |
| `salesChargeAmount` | `TrnOrder.f_total_charges - TrnOrdCharges.f_sst_amount`，示例为 14.76 |
| `taxAmount` | `TrnOrdCharges.f_sst_amount`，示例为 1.18 |

当前无日期后缀代码的费用公式为：`amount - amount / (1 + rate + rate * 8%)`，所有金额经 `round(..., 2)`。依据：`mdl_order.php:1040-1110,1189-1215,1306-1342`。

### 4.3 UW 向 OP 的 Buy JSON

**URL 与方向：**`UWealth WebAPI -> OP`。调用方是 UWealth，接收 URL 由 OP 提供；当前配置为：

```http
POST http://10.10.20.100:8080/api/IntegrationExt/TransactionUnitTrust
```

下面才是实际发送给 OP 的 request body：

```json
{
  "accountCode": "A00001WWN",
  "tradeDate": "2026-07-01 10:00:00.000",
  "trnCode": "UP",
  "stockCode": "F000000001",
  "amount": 1000.00,
  "unit": "0",
  "salesChargeRate": 1.5,
  "salesChargeAmount": 14.76,
  "otherFee": "0",
  "orderNo": "OD260701100000000001",
  "OrderCurr": "MYR",
  "OrderExRate": 1,
  "AmountSC": 1000.00,
  "mode": "ONLINE",
  "remark": "",
  "taxAmount": 1.18
}
```

关键规则：

- `trnCode=UP`；
- `stockCode` 使用 OP/datafeed fund code；
- Buy 初始 `unit=0`；
- `mode` 根据发起用户决定 `ONLINE/OFFLINE`；
- OP 接单文本中的 OP 单号写入 `TrnOrder.op_order_no`。

依据：`mdl_order.php:4276-4328,4366-4452,4537-4565`。

### 4.4 OP Buy 成功回调

**URL 与方向：**`OP -> UWealth WebApp`。调用方是 OP，URL 由 UWealth 提供；WebApp 随后内部转发至 UWealth WebAPI 同名 route。

```http
POST /OP/update_buy_transaction
```

```json
{
  "OP_PK_ID": "UTF*260700001",
  "UW_order_no": "OD260701100000000001",
  "client_code": "A00001WWN",
  "unit": 800.00,
  "nav": 1.25,
  "branch": "S51",
  "net_amount": -984.06,
  "gross_amount": -1000.00,
  "m_net_amount": -984.06,
  "m_gross_amount": -1000.00,
  "currency": "MYR",
  "currency_rate": 1,
  "fund_id": "F000000001",
  "fund_amount": -1000.00,
  "fund_m_amount": -1000.00,
  "ip_address": "169.254.1.2",
  "status": 1
}
```

V1 model 对主要金额字段取 `abs()` 后传入 `usp_UpdateProcessedBuyTransaction`。已从 MSSQL 取得的该存储过程定义确认，成功回调会更新：

```sql
unit   = @unit
nav    = @nav
f_nav  = @nav
m_nav  = ROUND(@m_gross_amount / @unit, 4)
```

其中 `@m_gross_amount` 是 callback `m_gross_amount` 经 PHP `abs()` 后的值；因此 `m_nav` 不使用 `currency_rate`，也不使用订单创建时保存的 `m_curr_rate`。当 `unit = 0` 时，该 SQL 会触发除零异常并被存储过程 `CATCH` 记录，不会在 PHP 层预先拦截。

成功结果：`WF00000016`，随后 OP 再调用 `/OP/update_workflow` 传 `WF00000010` 完成。

### 4.5 非 MYR 且付款币种与基金币种不同的 Buy 成功回调（实际 USD -> SGD 数据）

**URL 与方向：**`OP -> UWealth WebApp`。与 4.4 使用相同的 UWealth callback URL：

```http
POST /OP/update_buy_transaction
```

以下为 MSSQL `dbo.MstOPRawData` 的实际 `OP_API - B` 回调记录（ID `140799`）。订单号为 `OD250131101731165271`，`TrnOrder.payment_curr_code="USD"`、`TrnOrder.fund_curr_code="SGD"`，是付款币种与基金币种不同的非 MYR Buy。对应出站 `TRANSACTION - B` raw（ID `137739`）的实际字段为 `OrderCurr="USD"`、`OrderExRate="1.34966"`、`amount=100000`、`AmountSC="134966.44"`。

```json
{
  "OP_PK_ID": "UTF*250105929",
  "UW_order_no": "OD250131101731165271",
  "client_code": "J02006WWN",
  "unit": 91167.73,
  "nav": 1.4373,
  "branch": "013",
  "gross_amount": -100000.33,
  "net_amount": -97087.7,
  "m_gross_amount": -594797.1,
  "m_net_amount": -577472.92,
  "sale_charge_amount": 2912.63,
  "sale_charge_rate": 0.03,
  "currency": "USD",
  "currency_rate": 0,
  "fund_id": "F000010RLC",
  "fund_amount": -100000.33,
  "fund_m_amount": -438236.03,
  "type": null,
  "status": 1,
  "ip_address": "169.254.1.2"
}
```

该回调后实际 `TrnOrder` 为 `payment_curr_code="USD"`、`fund_curr_code="SGD"`、`curr_rate=1.34966`、`m_curr_rate=4.42600`、`nav=1.4373`、`f_nav=1.4373`、`m_nav=6.5242`，workflow 已进入 `WF00000010`。其中：

```text
m_nav = ROUND(ABS(m_gross_amount) / unit, 4)
      = ROUND(594797.1 / 91167.73, 4)
      = 6.5242
```

这验证了 4.4 的存储过程规则：即使付款币种 USD 与基金币种 SGD 不同，`f_nav` 仍直接等于 callback `nav`，`m_nav` 仍来自 OP callback 的 `m_gross_amount / unit`，不是使用订单内的 `m_curr_rate` 重新换算。该样本的 callback `currency_rate=0`，同样未参与这两个 NAV 字段的计算。

#### 跨币种实际数据复核

另抽取 4 笔“付款币种与基金币种不同”的成功 Buy，并将 OP callback 与最终 `TrnOrder` 对照，结果一致：

| Order No | Payment -> Fund | Callback `currency` / `currency_rate` | `nav` = `f_nav` | `abs(m_gross_amount) / unit` | `m_nav` |
| --- | --- | --- | ---: | ---: | ---: |
| `OD250818104617790723` | AUD -> USD | AUD / 0 | 0.2628 | 0.7130 | 0.7130 |
| `OD250225131724977538` | AUD -> GBP | AUD / 0 | 1.3063 | 3.6166 | 3.6166 |
| `OD250204140815231297` | GBP -> AUD | GBP / 0 | 0.9766 | 5.3418 | 5.3418 |
| `OD250131101731165271` | USD -> SGD | USD / 0 | 1.4373 | 6.5242 | 6.5242 |
| `OD250128120651273607` | CNY -> CNH | CNY / 0 | 0.9105 | 0.5423 | 0.5423 |

结论：`m_nav` 的写法不是单笔异常，而是 V1 存储过程的固定行为；callback `currency` 在这些样本中均为付款币种，不能据此判断基金币种。

但 `currency_rate=0` 是需要记录的数据质量风险，不是可以忽略的字段：`usp_UpdateProcessedBuyTransaction` 将 callback 的 `currency` 与 `currency_rate` 直接写入 `TrnTrustItem.currency`、`TrnTrustItem.curr_rate`。以上 5 笔对应的 `TrnTrustItem.curr_rate` 实际均为 `0.00000`，同时 `currency` 分别为 CNY、USD、GBP、AUD、AUD。若后续报表、信托余额或汇兑逻辑依赖该 `curr_rate`，跨币种 Buy 会取得零汇率；是否影响现有功能需按其读取链路另行核查。

### 4.6 OP Buy 拒绝

OP 仍调用同一个 endpoint，只把 `status` 设为 `0`：

```json
{
  "OP_PK_ID": "UTF*260700001",
  "UW_order_no": "OD260701100000000001",
  "client_code": "A00001WWN",
  "unit": 0,
  "nav": 0,
  "branch": "S51",
  "net_amount": 0,
  "gross_amount": 0,
  "m_net_amount": 0,
  "m_gross_amount": 0,
  "currency": "MYR",
  "currency_rate": 1,
  "fund_id": "F000000001",
  "fund_amount": 0,
  "fund_m_amount": 0,
  "ip_address": "169.254.1.2",
  "status": 0
}
```

结果：`WF00000015`。PHP 记录 `MstOPRawData(raw_data_type='OP_API - B')` 后调用存储过程；拒绝分支的精确 SQL 顺序未在代码仓库中提供。

### 4.7 普通 Buy 场景矩阵

| 场景 | Actor | 前置 | 目标 | 资金/持仓 | OP |
| --- | --- | --- | --- | --- | --- |
| Supervisor Reject | BFE | WF01 | WF11 | 回补 Cash Account 预留；付款分摊转 Reject 表 | 未送 OP |
| Client Reject | Client | WF02 | WF12 | 同上 | 未送 OP |
| Advisor Reject | 无独立事件 | - | 不适用 | - | - |
| BFE Cancel | BFE | WF02 | WF20 | 回补预留；不写 RejectReason | 未送 OP |
| Client Cancel/Revoke | Client | WF02 | 不适用 | Client 只能 A/R | 未送 OP |
| OP Reject | OP | 通常 WF04/WF05 | WF15 | 存储过程失败分支；精确 DML 未确认 | `status=0` callback |
| OP 成功 | OP | WF04/WF05 | WF16 -> WF10 | 确认 unit/nav 并处理 trust/holding | callback + workflow |

## 5. PRS Buy

### 5.1 V1 的订单和账户结构

- 主订单仍是 `TrnOrder.order_type=B`；
- 支付方式是 Cash Account；
- A/B 金额和单位保存在 `TrnPRSOrder`；
- 内部产品账户通常使用 `WWN`；
- OP 账户后缀使用 `WP7/WP3`；
- 人工审批、拒绝和取消都针对主 `order_no`，没有 PRS 子单独立拒绝 route。

### 5.2 创建时 `TrnOrder` JSON

**URL 与方向：**该 JSON 是数据库快照，`HTTP URL：无`，不直接调用 OP。对应的 UWealth 创建链路是：

```text
Browser -> UWealth WebApp: POST /transaction/_buy_order
UWealth WebApp -> UWealth WebAPI: POST /transaction/order/prs/buy
UWealth WebAPI -> UnitTrust.dbo.TrnOrder + TrnPRSOrder: INSERT
```

达到送 OP 条件后，UWealth 才使用 5.3 的 WP7 JSON 调用 OP 提供的 `TransactionUnitTrust` URL。

PRS Buy 的主表行仍是普通 `order_type=B`。以下示例对应 MYR 3,000、销售费率 1.5%、汇率 1：

```json
{
  "order_no": "OD260701101000000002",
  "order_grouping": "OG260701101000000001",
  "fund_id": "FN000000001",
  "client_code": "A00001WWN",
  "branch": "S51",
  "BFECode": "BFE0001",
  "BFESubCode": null,
  "order_type": "B",
  "order_date": "2026-07-01 10:10:00.000",
  "submission_date": null,
  "portfolio_code": null,
  "payment_mode_code": "PM00000001",
  "payment_curr_code": "MYR",
  "fund_curr_code": "MYR",
  "unit": null,
  "amount": 3000.00,
  "nav": null,
  "total_charges": 47.83,
  "net_amount": 2952.17,
  "curr_rate": 1,
  "m_curr_rate": 1,
  "f_amount": 3000.00,
  "f_nav": null,
  "f_total_charges": 47.83,
  "f_net_amount": 2952.17,
  "m_amount": 3000.00,
  "m_nav": null,
  "m_total_charges": 47.83,
  "m_net_amount": 2952.17,
  "bank_code": null,
  "bank_subcode": null,
  "cheque_no": null,
  "cheque_type": null,
  "cheque_date": null,
  "dividend_instruction": "R",
  "workflow_code": "WF00000002",
  "confirmation_date": null,
  "settlement_date": null,
  "cooling_off_date": null,
  "contract_no": null,
  "rsp_no": null,
  "created_by": "testadvisor",
  "created_at": "2026-07-01 10:10:00.000",
  "created_ip": "169.254.1.2",
  "updated_by": null,
  "updated_at": null,
  "updated_ip": null,
  "payment_no": null,
  "order_remark": null,
  "cob_subm_id": null,
  "op_order_no": null
}
```

仅看 `TrnOrder` 无法区分普通 Buy 与 PRS Buy；V1 通过同一 `order_no` 是否存在 `TrnPRSOrder` A/B 子记录识别 PRS。`TrnPRSOrder.amount/total_charges/net_amount/f_*` 以及 `m_total_charges/m_net_amount` 按运行时参数 `PrsAccAValue` 拆分，因此文档不把某个环境参数值伪装成固定比例。

必须保留一个 Legacy 特例：A、B 子记录的 `m_amount` 都错误/历史性地以主单 `f_net_amount` 为拆分基数，而不是主单 `m_amount`。按本节 MYR 示例，两个子记录的 `m_amount` 合计会是 `2952.17`，不等于主 `TrnOrder.m_amount=3000.00`。这是现行 V1 映射，不应在参考文档中自行改正。依据：`mdl_order.php:833-834,1217-1273`；`mdl_prs_order.php:6-51`。

### 5.3 PRS Buy 送 OP 的现行代码路径

**URL 与方向：**`UWealth WebAPI -> OP`。调用方是 UWealth，接收 URL 由 OP 提供：

```http
POST http://10.10.20.100:8080/api/IntegrationExt/TransactionUnitTrust
```

Client Approve 时：

1. `get_prsB_orders(order_no)` 只查询 `fund_sub_acc='B'`；
2. 对查询结果循环调用 `riskk_OP_transaction()`；
3. Buy 分支不按 `prs_sub_acc` 选择后缀，而是固定把 `WWN` 转成 `WP7`；
4. Buy JSON 使用主订单 amount，不使用 PRS 子记录 amount；
5. 查询通常应只有一条 B 记录，因此正常可观察结果是一笔 WP7 出站。

依据：`mdl_order.php:4219-4227,4386-4390`；`ctrl_order.php:813-839`。

出站 JSON 与普通 Buy 相同，差异是：

```json
{
  "accountCode": "A00001WP7",
  "tradeDate": "2026-07-01 10:10:00.000",
  "trnCode": "UP",
  "stockCode": "F000000001",
  "amount": 3000.00,
  "unit": "0",
  "salesChargeRate": 1.5,
  "salesChargeAmount": 44.29,
  "otherFee": "0",
  "orderNo": "OD260701101000000002",
  "OrderCurr": "MYR",
  "OrderExRate": 1,
  "AmountSC": 3000.00,
  "mode": "ONLINE",
  "remark": "",
  "taxAmount": 3.54
}
```

### 5.4 PRS Buy 的三段 OP 回调

**URL 与方向：**本节表内的 `/OP/update_workflow`、`/OP/update_buy_prs_transaction` 都是 UWealth 提供给 OP 的 WebApp URL，调用方向均为 `OP -> UWealth WebApp`；WebApp 再内部转发至 UWealth WebAPI。

真实订单 `OD260313133554290121` 证明，PRS Buy 成功生命周期包含三个**回调阶段**，不是只有 A/B 两个成交 JSON：

| 阶段 | Endpoint | OP 传入内容 | 主订单状态 |
| --- | --- | --- | --- |
| 1. OP 接单确认 | `POST /OP/update_workflow` | `workflow_code=WF00000005` | WF04 -> WF05 |
| 2. A/B 成交确认 | `POST /OP/update_buy_prs_transaction` | A、B 各传一次，`type=1/2` | 第一条成功报文写 WF16；第二条不重复写历史 |
| 3. OP 完成确认 | `POST /OP/update_workflow` | A、B 产品账户分别传 `WF00000010` | 第一条报文写 WF10；第二条不重复写历史 |

这里的“三段”不等于“只有三次 HTTP 请求”。该订单在 `MstOPRawData` 中共有 6 条入站 callback raw：WF05 两条（第二条与第一条内容完全相同，按重复重送口径）、A/B 成交两条、WF10 两条。排除重复 WF05 后，仍有 5 个有效业务 JSON。`TrnWorkFlowHistory` 最终只有三条 OP 状态，是因为两个存储过程都会防止重复插入同一 workflow。

#### 5.4.1 第一段：OP 接单确认到 WF05

2026-03-19 15:31:09.987 的真实报文：

```http
POST /OP/update_workflow
```

```json
{
  "UW_order_no": "OD260313133554290121",
  "client_code": "D02032WP7",
  "workflow_code": "WF00000005",
  "ip_address": "169.254.1.2"
}
```

OP 在 2026-04-02 12:08:56.040 又发送了一次完全相同的 WF05 报文。`update_workflow()` 会把两次 raw 都保存为 `OP_API - WF`，但 `usp_UpdateWorkflow_OP` 通过 `IF NOT EXISTS` 只保留一条 WF05 历史。

#### 5.4.2 第二段：PRS A/B 成交确认到 WF16

```http
POST /OP/update_buy_prs_transaction
```

Account A，2026-04-06 17:21:44.807：

```json
{
  "OP_PK_ID": "UTF*260303623A",
  "UW_order_no": "OD260313133554290121",
  "client_code": "D02032WP7",
  "branch": "S51",
  "unit": 1656.1,
  "nav": 1.2443,
  "net_amount": -2060.68,
  "gross_amount": -2100.11,
  "m_net_amount": -2060.68,
  "m_gross_amount": -2100.11,
  "sale_charge_amount": 33.38,
  "sale_charge_rate": 0.015,
  "type": 1,
  "currency": "MYR",
  "currency_rate": 1,
  "fund_id": "F00000Q3RJ",
  "fund_amount": -2100.11,
  "fund_m_amount": -2100.11,
  "status": 1,
  "ip_address": "169.254.1.2"
}
```

Account B，2026-04-06 17:21:46.167：

```json
{
  "OP_PK_ID": "UTF*260303623B",
  "UW_order_no": "OD260313133554290121",
  "client_code": "D02032WP3",
  "branch": "S51",
  "unit": 709.76,
  "nav": 1.2443,
  "net_amount": -883.15,
  "gross_amount": -900.05,
  "m_net_amount": -883.15,
  "m_gross_amount": -900.05,
  "sale_charge_amount": 14.31,
  "sale_charge_rate": 0.015,
  "type": 2,
  "currency": "MYR",
  "currency_rate": 1,
  "fund_id": "F00000Q3RJ",
  "fund_amount": -900.05,
  "fund_m_amount": -900.05,
  "status": 1,
  "ip_address": "169.254.1.2"
}
```

| type | OP 后缀 | PRS 子账户 | 实际落库 unit |
| ---: | --- | --- | ---: |
| `1` | `WP7` | A | 1,656.10 |
| `2` | `WP3` | B | 709.76 |

V1 的 B.PRS callback 防重键包含 `UW_order_no + client_code + type`。`usp_UpdateProcessedBuyPRSTransaction` 在第一条成功 callback 时插入 WF16；第二条仍会累加主订单 unit、更新对应 `TrnPRSOrder` 和持仓，但因 WF16 已存在而不再插入 workflow history。V1 没有等待 A+B 全部成功后才进入 WF16 的完整性门禁。

#### 5.4.3 第三段：OP 完成确认到 WF10

2026-04-07 12:17:22.647，OP 先以 PRS B 账户完成：

```http
POST /OP/update_workflow
```

```json
{
  "UW_order_no": "OD260313133554290121",
  "client_code": "D02032WP3",
  "workflow_code": "WF00000010",
  "ip_address": "169.254.1.2"
}
```

2026-04-07 12:17:22.740，OP 再以 PRS A 账户完成：

```json
{
  "UW_order_no": "OD260313133554290121",
  "client_code": "D02032WP7",
  "workflow_code": "WF00000010",
  "ip_address": "169.254.1.2"
}
```

两条报文都保存为 `OP_API - WF`；`usp_UpdateWorkflow_OP` 只插入第一条 WF10 历史。因此截图中的 OP 历史准确表现为 `WF05 -> WF16 -> WF10`，但不能据此反推只有三次 HTTP callback。

核验依据：`MstOPRawData`、`TrnWorkFlowHistory`、`TrnPRSOrder` 的真实订单数据，以及数据库中的 `dbo.usp_UpdateProcessedBuyPRSTransaction`、`dbo.usp_UpdateWorkflow_OP` 定义。

### 5.5 PRS Buy 拒绝场景

| 场景 | 作用对象 | 结果 |
| --- | --- | --- |
| Supervisor Reject | 主 `TrnOrder` | WF01 -> WF11；记录 reason；回补主订单 Cash Account 预留 |
| Client Reject | 主 `TrnOrder` | WF02 -> WF12；记录 reason；回补主订单 Cash Account 预留 |
| BFE Cancel | 主 `TrnOrder` | WF02 -> WF20；不写 RejectReason；回补预留 |
| Client Cancel/Revoke | - | 不适用 |
| OP Reject | callback `type=1/2` | `status=0` 进入 WF15；无独立 PRS reject JSON |

`TrnPRSOrder` 没有独立人工拒绝/取消 endpoint。主订单进入拒绝终态后，PRS 子记录的精确清理方式未在 PHP 代码中展开。

## 6. EPF Buy

### 6.1 V1 EPF 特征

- 主订单 `order_type=B`；
- `payment_mode_code=PM00000006`；
- 内部 `WWN` 账户送 OP 时转换为 `WE`；
- callback 再把 `WE` 还原为内部 `WWN`；
- EPF 不使用 Cash Account FIFO 资金预留；
- Non-Wrap、Personal account 和退休年龄规则只在创建时校验，拒绝时不重新校验。

### 6.2 创建时 `TrnOrder` JSON

**URL 与方向：**该 JSON 是数据库快照，`HTTP URL：无`，不直接发送 OP。创建链路为：

```text
Browser -> UWealth WebApp: POST /transaction/_buy_order
UWealth WebApp -> UWealth WebAPI: POST /transaction/order/epf/buy
UWealth WebAPI -> UnitTrust.dbo.TrnOrder: INSERT
```

达到送 OP 条件后，UWealth 才使用 6.3 的 WE JSON 调用 OP 提供的 `TransactionUnitTrust` URL。

以下示例对应 EPF Buy MYR 30,000、销售费率 3%、汇率 1：

```json
{
  "order_no": "OD260701102000000003",
  "order_grouping": "OG260701102000000002",
  "fund_id": "FN000000001",
  "client_code": "A00001WWN",
  "branch": "S51",
  "BFECode": "BFE0001",
  "BFESubCode": null,
  "order_type": "B",
  "order_date": "2026-07-01 10:20:00.000",
  "submission_date": null,
  "portfolio_code": null,
  "payment_mode_code": "PM00000006",
  "payment_curr_code": "MYR",
  "fund_curr_code": "MYR",
  "unit": null,
  "amount": 30000.00,
  "nav": null,
  "total_charges": 941.50,
  "net_amount": 29058.50,
  "curr_rate": 1,
  "m_curr_rate": 1,
  "f_amount": 30000.00,
  "f_nav": null,
  "f_total_charges": 941.50,
  "f_net_amount": 29058.50,
  "m_amount": 30000.00,
  "m_nav": null,
  "m_total_charges": 941.50,
  "m_net_amount": 29058.50,
  "bank_code": null,
  "bank_subcode": null,
  "cheque_no": null,
  "cheque_type": null,
  "cheque_date": null,
  "dividend_instruction": "R",
  "workflow_code": "WF00000002",
  "confirmation_date": null,
  "settlement_date": null,
  "cooling_off_date": null,
  "contract_no": null,
  "rsp_no": null,
  "created_by": "testadvisor",
  "created_at": "2026-07-01 10:20:00.000",
  "created_ip": "169.254.1.2",
  "updated_by": null,
  "updated_at": null,
  "updated_ip": null,
  "payment_no": null,
  "order_remark": null,
  "cob_subm_id": null,
  "op_order_no": null
}
```

与普通/PRS Buy 对比，`TrnOrder` 中可直接识别 EPF 的字段是 `payment_mode_code=PM00000006`。内部客户代码仍是 `WWN`，`WE` 只在送 OP 时转换。EPF 不创建 Cash Account 的 `TrnOrderPayment` FIFO 预占记录。

### 6.3 出站 JSON

**URL 与方向：**`UWealth WebAPI -> OP`。调用方是 UWealth，URL 由 OP 提供：

```http
POST http://10.10.20.100:8080/api/IntegrationExt/TransactionUnitTrust
```

```json
{
  "accountCode": "A00001WE",
  "tradeDate": "2026-07-01 10:20:00.000",
  "trnCode": "UP",
  "stockCode": "F000000001",
  "amount": 30000.00,
  "unit": "0",
  "salesChargeRate": 3,
  "salesChargeAmount": 871.76,
  "otherFee": "0",
  "orderNo": "OD260701102000000003",
  "OrderCurr": "MYR",
  "OrderExRate": 1,
  "AmountSC": 30000.00,
  "mode": "ONLINE",
  "remark": "",
  "taxAmount": 69.74
}
```

### 6.4 OP EPF Buy 回调

**URL 与方向：**`OP -> UWealth WebApp`。调用方是 OP，URL 由 UWealth 提供；WebApp 再内部转发至 WebAPI。

```http
POST /OP/update_buy_epf_transaction
```

```json
{
  "OP_PK_ID": "UTF*260700003",
  "UW_order_no": "OD260701102000000003",
  "client_code": "A00001WE",
  "unit": 24000.00,
  "nav": 1.25,
  "branch": "S51",
  "net_amount": -29058.50,
  "gross_amount": -30000.00,
  "m_net_amount": -29058.50,
  "m_gross_amount": -30000.00,
  "currency": "MYR",
  "currency_rate": 1,
  "fund_id": "F000000001",
  "fund_amount": -30000.00,
  "fund_m_amount": -30000.00,
  "ip_address": "169.254.1.2",
  "status": 1
}
```

当前 model 不消费 `sale_charge_amount`、`sale_charge_rate`、`reason` 或 `remark`。

### 6.5 EPF Buy 场景矩阵

| 场景 | 前置 | 目标 | 副作用 |
| --- | --- | --- | --- |
| Supervisor Reject | WF01 | WF11 | 记录 reason；无 Cash Account 余额预留需要回补 |
| Client Reject | WF02 | WF12 | 记录 reason；不改持仓 |
| Advisor Reject | - | 不适用 | Advisor 取消，不存在独立 Reject |
| BFE Cancel | WF02 | WF20 | 不写 RejectReason；不改持仓 |
| Client Cancel/Revoke | WF02 | 不适用 | Client 只能 A/R |
| OP Reject | WF04/WF05 | WF15 | `/OP/update_buy_epf_transaction` 使用 `status=0`；精确 SP DML 未确认 |
| OP 成功 | WF04/WF05 | WF16 -> WF10 | 成交 SP 更新 EPF unit/holding |

## 7. Deposit

### 7.1 Deposit WebAPI 创建请求 JSON

**URL 与方向：**这是 UWealth 内部创建接口，不是 OP 接口。完整调用链为 `Browser -> UWealth WebApp -> UWealth WebAPI`：

```text
Browser -> UWealth WebApp: POST /cash_deposit/_add
UWealth WebApp -> UWealth WebAPI: POST /cash_deposit/create
```

WebAPI route：

```http
POST /cash_deposit/create
```

Cheque 示例：

```json
{
  "password": "<hashed-password>",
  "client_code": "A00001WWN",
  "ifa_code": "",
  "currency": "MYR",
  "amount": 5000.00,
  "sales_charge": 0,
  "payment_method": "PM00000003",
  "bank": "BANK01",
  "bank_branch": "001",
  "cheque_number": "CHQ000001",
  "cheque_date": "2026-07-01"
}
```

| payment_method | V1 场景 | 初始/后续 workflow | OP Cash Deposit |
| --- | --- | --- | --- |
| `PM00000002` | FPX | WF24，支付网关路径 | 不调用 |
| `PM00000003` | Cheque | WF23，上传 supporting document 后送 OP | 调用 |
| `PM00000005` | Online Banking | WF23，上传 supporting document 后送 OP | 调用 |
| `PM00000007` | DDA/RSP | 不在手工 DP 可选列表 | 不套用本节手工路径 |

`receipt` 不是 payment mode；`WF00000023` 表示等待上传 supporting document。

### 7.2 创建时 `TrnOrder` JSON

**URL 与方向：**该 JSON 是 `/cash_deposit/create` 处理后形成的数据库快照，`HTTP URL：无`，不会作为 request body 直接发给 OP。非 FPX Deposit 真正送 OP 的 URL 和 JSON 见 7.3。

以下快照对应前面的 MYR 5,000 Cheque Deposit：

```json
{
  "order_no": "OD260701103000000004",
  "order_grouping": "OG260701103000000003",
  "fund_id": null,
  "client_code": "A00001WWN",
  "branch": "S51",
  "BFECode": "BFE0001",
  "BFESubCode": null,
  "order_type": "DP",
  "order_date": "2026-07-01 10:30:00.000",
  "submission_date": null,
  "portfolio_code": null,
  "payment_mode_code": "PM00000003",
  "payment_curr_code": "MYR",
  "fund_curr_code": null,
  "unit": null,
  "amount": -5000.00,
  "nav": null,
  "total_charges": null,
  "net_amount": -5000.00,
  "curr_rate": null,
  "m_curr_rate": 1,
  "f_amount": 0.00,
  "f_nav": null,
  "f_total_charges": null,
  "f_net_amount": 0.00,
  "m_amount": -5000.00,
  "m_nav": null,
  "m_total_charges": null,
  "m_net_amount": -5000.00,
  "bank_code": "BANK01",
  "bank_subcode": "001",
  "cheque_no": "CHQ000001",
  "cheque_type": null,
  "cheque_date": "2026-07-01",
  "dividend_instruction": null,
  "workflow_code": "WF00000023",
  "confirmation_date": null,
  "settlement_date": null,
  "cooling_off_date": null,
  "contract_no": null,
  "rsp_no": null,
  "created_by": "testadvisor",
  "created_at": "2026-07-01 10:30:00.000",
  "created_ip": "169.254.1.2",
  "updated_by": null,
  "updated_at": null,
  "updated_ip": null,
  "payment_no": null,
  "order_remark": null,
  "cob_subm_id": null,
  "op_order_no": null
}
```

创建代码对 DP 设置负号，所以 OP 出站使用 `abs(TrnOrder.amount)` 后恢复为正 5,000。`cheque_type` 来自付款方式对应的运行时参数，参数不存在时为 `null`。当前 DP controller 将 `curr_rate` 的 Buy/SellRate 都设为 `null`，因此创建代码的 fund-currency 金额运算得到 `0`，MYR 金额仍按 `m_curr_rate` 保存。

其他付款方式只改以下关键列：

| 场景 | `payment_mode_code` | 银行/支票列 | `workflow_code` | 创建后送 OP |
| --- | --- | --- | --- | --- |
| Cheque | `PM00000003` | bank/branch、cheque number/date 必填；`cheque_type` 取运行时参数 | `WF00000023` | 普通 BFE 上传凭证后送；管理员直建会立即送 |
| Online Banking | `PM00000005` | bank/branch 必填；cheque number/date 为空；`cheque_type` 取运行时参数 | `WF00000023` | 普通 BFE 上传凭证后送；管理员直建会立即送 |
| FPX | `PM00000002` | 输入 bank/branch/cheque 字段必须为空；派生 `cheque_type` 仍可能有值 | `WF00000024` | 不走 OP DP 接口 |

依据：`ctrl_cash_deposit.php:29-130,158-200,257-333,390-455`；`mdl_order.php:943-958,997-1017,1189-1215,1306-1342`。

这里的“上传凭证后送 OP”只描述普通 BFE 路径。具有 admin 身份的创建者会在 `create_order_transaction()` 完成本地 INSERT 后立即调用 OP，成功后直接回写 `op_order_no`，不等待 supporting document。依据：`mdl_order.php:1453-1552`；普通凭证上传路径见 `mdl_order_supp_doc.php:224-420`。

### 7.3 UW 向 OP 的 DP JSON

**URL 与方向：**`UWealth WebAPI -> OP`。调用方是 UWealth，URL 由 OP 提供；只适用于非 FPX DP：

```http
POST http://10.10.20.100:8080/api/IntegrationExt/TransactionCashDeposit
```

非 FPX DP：

```json
{
  "accountCode": "A00001WWN",
  "depositDate": "2026-07-01 10:30:00.000",
  "depositMethod": "103",
  "bankAccount": "BANK01",
  "currency": "MYR",
  "amount": 5000.00,
  "salesChargeRate": 0,
  "salesChargeAmount": "0",
  "otherFee": "0",
  "orderNo": "OD260701103000000004",
  "taxAmount": "0"
}
```

| Deposit 类型 | depositMethod |
| --- | --- |
| Cheque | `103` |
| Online Banking | `105` |

### 7.4 OP DP 成功/拒绝 callback

**URL 与方向：**`OP -> UWealth WebApp`。调用方是 OP，URL 由 UWealth 提供；WebApp 再内部转发至 WebAPI。

```http
POST /OP/update_cash_deposit
```

```json
{
  "OP_PK_ID": "UTD*260700004",
  "UW_order_no": "OD260701103000000004",
  "client_code": "A00001WWN",
  "branch": "S51",
  "net_amount": 5000.00,
  "gross_amount": 5000.00,
  "m_net_amount": 5000.00,
  "m_gross_amount": 5000.00,
  "currency": "MYR",
  "currency_rate": 1,
  "ip_address": "169.254.1.2",
  "status": 1
}
```

`status=1` 成功到 `WF00000010`；OP 拒绝使用完全相同 JSON，将 `status` 改为 `0`，结果为 `WF00000015`。

PHP 调用 `usp_UpdateProcessedCashDeposit`，但成功/失败分支对 `TrnTrust`、`TrnTrustItem`、`TrnTrustItemCart` 和付款表的精确 SQL 顺序未确认。

### 7.5 Deposit 的多角色场景

| 场景 | Actor | 前置 | 目标 | 说明 |
| --- | --- | --- | --- | --- |
| BFE 创建非 FPX | BFE | 无 | WF23 | 等待上传 supporting document，不经过 WF02 |
| BFE 创建 FPX | BFE | 无 | WF24 | 等待 FPX，不走 OP Cash Deposit |
| Intern 创建 | BFE4 | 无 | WF01 | 等待 BFE Supervisor |
| Admin 创建非 FPX | Backoffice/Admin | 无 | 按创建 workflow | 本地 INSERT 后立即送 OP 并回写 `op_order_no`，不等待凭证 |
| Supervisor Approve 非 FPX | BFE | WF01 | WF23 | 按 payment mode 进入 receipt 流程 |
| Supervisor Approve FPX | BFE | WF01 | WF24 | 进入支付网关流程 |
| Supervisor Reject | BFE | WF01 | WF11 | reason 必填；尚未送 OP |
| Client Reject | Client | - | 不适用标准 DP | 标准 DP 不进入 WF02 |
| BFE Cancel | BFE | WF23/WF24 | WF20 | 不要求 reason；停止后续 OP/FPX 流程 |
| Client Cancel/Revoke | Client | - | 不适用 | Client 没有 C/Revoke |
| OP Reject | OP | 非 FPX 已送 OP | WF15 | `/OP/update_cash_deposit`, `status=0` |
| FPX 失败/取消 | 支付网关/BFE | WF24 | 支付链或 WF20 | 不使用 `/OP/update_cash_deposit` |

编辑 DP 不是原单原地修改：`/cash_deposit/edit` 会先用 `C` 取消旧订单，再创建新订单。

## 8. Sell

### 8.1 Sell 创建入口

Browser 先调用 UWealth WebApp 提供的 `POST /transaction/_sell_order`。WebApp 再根据 Sell 类型调用以下 UWealth WebAPI 内部 route；这些都不是 OP URL：

| Sell 类型 | 调用方 -> 接收方 | UWealth WebAPI route |
| --- | --- | --- |
| 普通 Sell | UWealth WebApp -> UWealth WebAPI | `POST /transaction/order/sell` |
| PRS Sell | UWealth WebApp -> UWealth WebAPI | `POST /transaction/order/prs/sell` |
| EPF Sell | UWealth WebApp -> UWealth WebAPI | `POST /transaction/order/epf/sell` |

创建 JSON：

```json
{
  "password": "<hashed-password>",
  "client_code": "A00001WWN",
  "ifa_code": "",
  "funds": [
    {
      "fund_id": "FN000000001",
      "unit": 1000.00,
      "portfolio_code": null
    }
  ]
}
```

### 8.2 创建时 `TrnOrder` JSON

**URL 与方向：**该 JSON 是上述 WebAPI 创建 route 处理后的数据库快照，`HTTP URL：无`，不直接发送给 OP。达到送 OP 条件后，UWealth 才使用 8.3 的交易 JSON 调用 OP。

以下快照对应普通 Sell 1,000 units：

```json
{
  "order_no": "OD260701104000000005",
  "order_grouping": "OG260701104000000004",
  "fund_id": "FN000000001",
  "client_code": "A00001WWN",
  "branch": "S51",
  "BFECode": "BFE0001",
  "BFESubCode": null,
  "order_type": "S",
  "order_date": "2026-07-01 10:40:00.000",
  "submission_date": null,
  "portfolio_code": "",
  "payment_mode_code": "PM00000001",
  "payment_curr_code": "MYR",
  "fund_curr_code": "MYR",
  "unit": 1000.00,
  "amount": null,
  "nav": null,
  "total_charges": null,
  "net_amount": null,
  "curr_rate": null,
  "m_curr_rate": null,
  "f_amount": null,
  "f_nav": null,
  "f_total_charges": null,
  "f_net_amount": null,
  "m_amount": null,
  "m_nav": null,
  "m_total_charges": null,
  "m_net_amount": null,
  "bank_code": null,
  "bank_subcode": null,
  "cheque_no": null,
  "cheque_type": null,
  "cheque_date": null,
  "dividend_instruction": "R",
  "workflow_code": "WF00000002",
  "confirmation_date": null,
  "settlement_date": null,
  "cooling_off_date": null,
  "contract_no": null,
  "rsp_no": null,
  "created_by": "testadvisor",
  "created_at": "2026-07-01 10:40:00.000",
  "created_ip": "169.254.1.2",
  "updated_by": null,
  "updated_at": null,
  "updated_ip": null,
  "payment_no": null,
  "order_remark": null,
  "cob_subm_id": null,
  "op_order_no": null
}
```

V1 Sell 创建时只确定 `unit`，不预估 `amount/nav/net_amount`；这些成交金额由 OP callback 回写。普通 Sell 的汇率计算发生在 controller 补齐 Sell 付款币种之前，且基金从 `holding_funds` 而不是 `check_list.funds` 取得，所以示例创建态的 `curr_rate/m_curr_rate` 都是 `null`；OP 出站仍把 Sell 的 `OrderExRate` 硬编码为 `1`。送 OP 时 `unit` 直接来自主表，`amount` 在 PHP 出站结构中表现为 `0`。

Sell 变体的主表差异：

| Sell 类型 | `TrnOrder.order_type` | `payment_mode_code` | 主表能否独立识别 |
| --- | --- | --- | --- |
| 普通 | `S` | `PM00000001` | 不能；还需确认不存在同 `order_no` 的 `TrnPRSOrder` |
| PRS | `S` | `PM00000001` | 不能；需检查同一 `order_no` 的 `TrnPRSOrder` |
| EPF | `S` | `PM00000006` | 可由 EPF payment mode 识别 |

PRS Sell 的主表 `unit` 是总卖出份额，`TrnPRSOrder` 再按 B 可用份额优先、剩余进入 A 的方式拆子账户；送 OP 时改用每条 PRS 子记录的 `unit`。普通 Sell 缺少 Portfolio 时 controller 写入空字符串 `""`，不是 `null`。依据：`ctrl_order.php:1082-1086,1177-1262,1605-1607`；`mdl_order.php:1217-1273,1306-1342,4419-4432`。

### 8.3 UW 向 OP 的普通 Sell JSON

**URL 与方向：**`UWealth WebAPI -> OP`。调用方是 UWealth，URL 由 OP 提供；普通、PRS、EPF Sell 共用该 URL：

```http
POST http://10.10.20.100:8080/api/IntegrationExt/TransactionUnitTrust
```

```json
{
  "accountCode": "A00001WWN",
  "tradeDate": "2026-07-01 10:40:00.000",
  "trnCode": "US",
  "stockCode": "F000000001",
  "amount": 0,
  "unit": 1000.00,
  "salesChargeRate": 0,
  "salesChargeAmount": "0",
  "otherFee": "0",
  "orderNo": "OD260701104000000005",
  "OrderCurr": 0,
  "OrderExRate": 1,
  "AmountSC": 0,
  "mode": "ONLINE",
  "remark": "",
  "taxAmount": "0"
}
```

这里的 `trnCode=US` 表示 Unit Sell，不是 UWealth `order_type=US`。

### 8.4 OP 普通 Sell callback

**URL 与方向：**`OP -> UWealth WebApp`。调用方是 OP，URL 由 UWealth 提供；WebApp 再内部转发至 WebAPI。

```http
POST /OP/update_sell_transaction
```

```json
{
  "OP_PK_ID": "UTS*260700005",
  "UW_order_no": "OD260701104000000005",
  "client_code": "A00001WWN",
  "unit": 1000.00,
  "nav": 1.20,
  "branch": "S51",
  "net_amount": 1190.00,
  "gross_amount": 1200.00,
  "m_net_amount": 1190.00,
  "m_gross_amount": 1200.00,
  "currency": "MYR",
  "currency_rate": 1,
  "fund_id": "F000000001",
  "ip_address": "169.254.1.2",
  "type": "S",
  "status": 1
}
```

`status=1` 进入 `WF00000016`，随后 `/OP/update_workflow` 进入 `WF00000010`；`status=0` 进入 `WF00000015`。

### 8.5 Sell PRS/EPF 差异

下表 callback 均为 UWealth 提供给 OP 的 WebApp URL，调用方向是 `OP -> UWealth WebApp`：

| 类型 | 出站 accountCode | UWealth callback URL | 特有字段 |
| --- | --- | --- | --- |
| 普通 | `WW/WWN` | `POST /OP/update_sell_transaction` | `type=S/FS` |
| PRS A | `WP7` | `POST /OP/update_sell_prs_transaction` | `type=1` |
| PRS B | `WP3` | `POST /OP/update_sell_prs_transaction` | `type=2` |
| EPF | `WE` | `POST /OP/update_sell_epf_transaction` | 不读取 `type` |

PRS Sell 出站按实际 `fund_sub_acc` 选择 WP7/WP3，并使用对应 PRS unit。未达到退休年龄时页面规则通常只允许卖 PRS B；达到退休年龄后可按总 PRS 持仓卖出。

### 8.6 Sell 的拒绝和持仓副作用

| 场景 | 前置 | 目标 | 持仓/资金 |
| --- | --- | --- | --- |
| Supervisor Reject | WF01 | WF11 | 只更新订单、history、reason；未送 OP |
| Client Reject | WF02 | WF12 | 同上；未送 OP |
| Advisor Reject | - | 不适用 | Advisor 使用 Cancel |
| BFE Cancel | WF02 | WF20 | 不写 RejectReason |
| Client Cancel/Revoke | WF02 | 不适用 | Client 只能 A/R |
| OP Reject | WF04/WF05 | WF15 | callback `status=0`；精确 proceeds DML 未确认 |
| OP workflow 拒绝 | 任意 PHP 可接收状态 | 请求指定 WF15 | PHP 不校验前置；SP 限制未确认 |

V1 Sell 创建没有写独立 reservation 表，也没有直接扣减实际 holding。可卖份额通过 `fn_UtGetPendingRdptTrans(1)` 汇总 pending unit 后动态计算。因此拒绝/取消时 PHP 没有 Buy/WD 那种显式 cart/payment release；终态订单何时从 pending unit 中排除取决于数据库函数的 workflow 过滤。

## 9. Switch

### 9.1 创建入口与订单结构

Switch 的主订单 `TrnOrder.order_type` 为 `SW`，同一主订单下在 `TrnSwitchOrder` 维护 Switch Out（`trans_type=SS`）和 Switch In（`trans_type=SB`）明细；OP 的 `OrderGrpNo` 始终使用主订单号，不使用任一明细 `switch_order_no`。

| Switch 类型 | Browser -> WebApp | WebApp -> WebAPI |
| --- | --- | --- |
| Inter Switch | `POST /transaction/_inter_switch` | `POST /transaction/order/interswitch` |
| Intra Switch | `POST /transaction/_intra_switch` | `POST /transaction/order/intraswitch` |
| PRS Intra Switch | `POST /transaction/_intra_switch_prs` | `POST /transaction/order/prs/intraswitch` |
| EPF Intra Switch | `POST /transaction/_intra_switch_epf` | `POST /transaction/order/epf/intraswitch` |

`Inter Switch` 在 V1 常量中为 `ES`，`Intra Switch` 为 `AS`；送 OP 时分别映射为 `SwitchType="2"` 和 `SwitchType="1"`。一笔 Switch 至少须同时包含一条 `SS` 与一条 `SB` 明细。

### 9.2 UW 向 OP 的 Switch JSON

**URL 与方向：**`UWealth WebAPI -> OP`。调用方是 UWealth，URL 由 OP 提供：

```http
POST http://10.10.20.100:8080/api/IntegrationExt/TransactionSwitch
```

以下示例为一笔 Intra Switch：卖出 `F000000001` 的 1,000 units，100% 转入 `F000000002`。`SellDetail` 和 `BuyDetail` 均允许以 `|` 连接多条明细。

```json
{
  "accountCode": "A00001WWN",
  "tradeDate": "2026-07-01 10:45:00.000",
  "SwitchType": "1",
  "SellDetail": "F000000001,1000.00,SO260701104500000001",
  "BuyDetail": "F000000002,100,SO260701104500000002",
  "OrderGrpNo": "OD260701104500000007",
  "mode": "ONLINE"
}
```

| 字段 | V1 来源/规则 |
| --- | --- |
| `accountCode` | 普通账户使用 WW/WWN client code；EPF Switch 将 `WWN` 替换为 `WE`。 |
| `SwitchType` | `AS -> "1"`，`ES -> "2"`。 |
| `SellDetail` | 每条为 `datafeed fund_id,unit,switch_order_no`。 |
| `BuyDetail` | 每条为 `datafeed fund_id,percentage,switch_order_no`；示例的 `100` 表示全部分配。 |
| `OrderGrpNo` | `TrnOrder.order_no`，即 Switch 主订单号。 |

### 9.3 OP 接单响应

Switch 与普通 Buy/Sell 不同：V1 按 JSON 数组读取 OP 响应。主订单的 `OP_Id` 以 `UTG` 识别并写回 `TrnOrder.op_order_no`；其余明细 ID 写回相应 `TrnSwitchOrder.op_switch_order_no`。

```json
[
  {
    "OriginalID": "OD260701104500000007",
    "OP_Id": "UTG260700007"
  },
  {
    "OriginalID": "SO260701104500000001",
    "OP_Id": "UTF260700007"
  },
  {
    "OriginalID": "SO260701104500000002",
    "OP_Id": "UTF260700008"
  }
]
```

该出站请求及 OP 响应会以 `MstOPRawData.raw_data_type = TRANSACTION - SW` 审计；不能把普通交易的 `OD...|OP_ID` 文本响应格式套用于 Switch。

### 9.4 OP Switch 成功/拒绝 callback

**URL 与方向：**`OP -> UWealth WebApp`，由 UWealth 提供：

```http
POST /OP/update_switch
```

```json
{
  "OP_PK_ID": "UTSW260700007",
  "UW_group_order_no": "OD260701104500000007",
  "UW_order_no": "SO260701104500000001",
  "client_code": "A00001WWN",
  "branch": "S51",
  "unit": 1000.00,
  "amount": 1200.00,
  "m_net_amount": 1200.00,
  "nav": 1.20,
  "switch_in_fund_id": "F000000002",
  "switch_out_fund_id": "F000000001",
  "ip_address": "169.254.1.2",
  "status": 1
}
```

`UW_group_order_no` 是主订单号，`UW_order_no` 是本次回写的 Switch 明细号。V1 会记录 `OP_API - SW` 审计后调用 `usp_UpdateProcessedSwitchTransaction`。拒绝时沿用完全相同的 JSON，将 `status` 改为 `0`；按本文 3.8 的标准 OP Reject 路径，结果为 `WF00000015`。PHP callback 本身不校验当前 workflow，最终状态约束仍由存储过程负责。

Switch 的完成推进可通过通用 callback 一次传入多个订单号，例如：

```http
POST /OP/update_workflow
```

```json
{
  "UW_order_no": "OD260701104500000007|SO260701104500000001",
  "client_code": "A00001WWN",
  "workflow_code": "WF00000010",
  "ip_address": "169.254.1.2"
}
```

### 9.5 Switch 的多角色拒绝场景

| 场景 | Actor | 前置 | 目标 | 说明 |
| --- | --- | --- | --- | --- |
| Supervisor Reject | BFE | WF01 | WF11 | Intern/BFE4 创建的 Switch 尚未送 OP；`reason` 必填。 |
| Client Reject | Client | WF02 | WF12 | 尚未送 OP；Client 须具有该账户 approval right。 |
| Advisor Reject | - | - | 不适用 | Advisor/BFE 自己创建并等待 Client 的订单如需终止，使用 Cancel。 |
| BFE Cancel | BFE | WF02 | WF20 | 不写 RejectReason；Client 没有 Cancel/Revoke action。 |
| OP Reject | OP | 已送 OP | WF15 | 调用 `/OP/update_switch`，`status=0`。 |
| OP 完成推进 | OP | Switch 明细已处理 | 指定 workflow | 使用 `/OP/update_workflow`；可用 `|` 一次传入主订单和 Switch 明细号。 |

`A/R/C` 的通用入参、角色校验和 Reject/Cancel 的本地落库规则与第 3 节相同；Switch 的区别在于审批/回写同时更新主订单和 Switch 明细，而不是将它拆成独立的普通 Sell 与 Buy 订单。

## 10. Withdrawal

### 10.1 创建 JSON

**URL 与方向：**这是 UWealth 内部创建接口，不是 OP URL：

```text
Browser -> UWealth WebApp: POST /cash_withdrawal/_add
UWealth WebApp -> UWealth WebAPI: POST /cash_withdrawal/create
```

```http
POST /cash_withdrawal/create
```

```json
{
  "password": "<hashed-password>",
  "client_code": "A00001WWN",
  "ifa_code": "",
  "currency": "MYR",
  "receive_currency": "MYR",
  "amount": 2000.00
}
```

WD 创建时按 FIFO 预占 Cash Account：

- 创建 `TrnOrder`；
- 写 `TrnWorkFlowHistory`；
- 创建 `TrnOrderPayment`；
- 减少对应 `TrnTrustItemCart.os_*` 可用金额。

### 10.2 创建时 `TrnOrder` JSON

**URL 与方向：**该 JSON 是 `/cash_withdrawal/create` 处理后的数据库快照，`HTTP URL：无`，不直接发送给 OP。真正发送给 OP 的 request body 和 URL 见 9.3。

以下快照对应从 MYR Cash Account 提取 MYR 2,000，并以 MYR 收款：

```json
{
  "order_no": "OD260701105000000006",
  "order_grouping": "OG260701105000000005",
  "fund_id": null,
  "client_code": "A00001WWN",
  "branch": "S51",
  "BFECode": "BFE0001",
  "BFESubCode": null,
  "order_type": "WD",
  "order_date": "2026-07-01 10:50:00.000",
  "submission_date": null,
  "portfolio_code": null,
  "payment_mode_code": "PM00000001",
  "payment_curr_code": "MYR",
  "fund_curr_code": "MYR",
  "unit": null,
  "amount": 2000.00,
  "nav": null,
  "total_charges": null,
  "net_amount": 2000.00,
  "curr_rate": null,
  "m_curr_rate": 1,
  "f_amount": null,
  "f_nav": null,
  "f_total_charges": null,
  "f_net_amount": null,
  "m_amount": 2000.00,
  "m_nav": null,
  "m_total_charges": null,
  "m_net_amount": 2000.00,
  "bank_code": null,
  "bank_subcode": null,
  "cheque_no": null,
  "cheque_type": null,
  "cheque_date": null,
  "dividend_instruction": null,
  "workflow_code": "WF00000002",
  "confirmation_date": null,
  "settlement_date": null,
  "cooling_off_date": null,
  "contract_no": null,
  "rsp_no": null,
  "created_by": "testadvisor",
  "created_at": "2026-07-01 10:50:00.000",
  "created_ip": "169.254.1.2",
  "updated_by": null,
  "updated_at": null,
  "updated_ip": null,
  "payment_no": null,
  "order_remark": null,
  "cob_subm_id": null,
  "op_order_no": null
}
```

WD 的字段命名容易误读：`payment_curr_code` 保存 API 的 `receive_currency`，`fund_curr_code` 保存 API 的 `currency`（实际被提取的 Cash Account currency）。因此 OP JSON 的 `Currency` 来自 `payment_curr_code`，`WithdrawCurrency` 来自 `fund_curr_code`，`amount` 来自 `TrnOrder.net_amount`。

依据：`ctrl_cash_withdrawal.php:27-106`；`mdl_order.php:850-873,1115-1215,1301-1349,3149-3280,4454-4466`。

### 10.3 UW 向 OP 的 WD JSON

**URL 与方向：**`UWealth WebAPI -> OP`。调用方是 UWealth，URL 由 OP 提供：

```http
POST http://10.10.20.100:8080/api/IntegrationExt/TransactionWithdrawalRequest
```

```json
{
  "notificationDate": "2026-07-01 10:50:00.000",
  "accountCode": "A00001WWN",
  "wdlType": "P",
  "WithdrawCurrency": "MYR",
  "Currency": "MYR",
  "amount": 2000.00,
  "orderNo": "OD260701105000000006"
}
```

### 10.4 OP WD callback

**URL 与方向：**`OP -> UWealth WebApp`。调用方是 OP，URL 由 UWealth 提供；WebApp 再内部转发至 WebAPI。

```http
POST /OP/update_cash_withdrawal
```

```json
{
  "OP_PK_ID": "UTW*260700006",
  "UW_order_no": "OD260701105000000006",
  "client_code": "A00001WWN",
  "net_amount": 2000.00,
  "gross_amount": 2000.00,
  "currency": "MYR",
  "currency_rate": 1,
  "ip_address": "169.254.1.2",
  "status": 1
}
```

`status=1` 成功到 `WF00000010`；`status=0` 进入 `WF00000015`。PHP 调用 `usp_UpdateProcessedCashWithdrawal`，精确 trust/付款 DML 未在仓库中提供。

### 10.5 Withdrawal 场景矩阵

| 场景 | Actor | 前置 | 目标 | 资金副作用 |
| --- | --- | --- | --- | --- |
| Supervisor Reject | BFE | WF01 | WF11 | 回补 FIFO cart；付款分摊转 Reject 表并删除原分摊 |
| Client Reject | Client | WF02 | WF12 | 同上 |
| Advisor Reject | - | - | 不适用 | Advisor 使用 Cancel |
| BFE Cancel | BFE | WF02 | WF20 | 回补 FIFO；不写 RejectReason |
| Client Cancel/Revoke | Client | WF02 | 不适用 | Client 只能 A/R |
| OP Reject | OP | 已送 OP | WF15 | `/OP/update_cash_withdrawal`, `status=0`；精确 SP DML 未确认 |
| OP 成功 | OP | 已送 OP | WF10 | 结算预占的 withdrawal |

编辑 WD 同样会先用 `C` 取消旧订单，再创建新订单。

## 11. 场景总表

| 业务 | Supervisor Reject | Client Reject | BFE Cancel | Client Cancel/Revoke | OP Reject |
| --- | --- | --- | --- | --- | --- |
| 普通 Buy | WF01 -> WF11；回补现金预留 | WF02 -> WF12；回补现金预留 | WF02 -> WF20 | 不支持 | Buy callback `status=0` -> WF15 |
| PRS Buy | 主订单 WF01 -> WF11 | 主订单 WF02 -> WF12 | 主订单 WF02 -> WF20 | 不支持 | PRS callback `type=1/2,status=0` -> WF15 |
| EPF Buy | WF01 -> WF11 | WF02 -> WF12 | WF02 -> WF20 | 不支持 | EPF callback `status=0` -> WF15 |
| DP 非 FPX | WF01 -> WF11，仅 Intern 创建路径 | 标准流不经过 WF02 | WF23 -> WF20 | 不支持 | DP callback `status=0` -> WF15 |
| DP FPX | WF01 -> WF11，仅 Intern 创建路径 | 标准流不经过 WF02 | WF24 -> WF20 | 不支持 | 不走 OP DP callback |
| Sell | WF01 -> WF11 | WF02 -> WF12 | WF02 -> WF20 | 不支持 | Sell callback `status=0` -> WF15 |
| WD | WF01 -> WF11；回补 FIFO | WF02 -> WF12；回补 FIFO | WF02 -> WF20 | 不支持 | WD callback `status=0` -> WF15 |

## 12. 已确认的实现边界

### 12.1 BFE4 Cancel 校验与状态映射不一致

`valid_workflow_action()` 允许 `fa_type=b4` 在部分 pending 状态执行 `C`，但 `generate_update_workflow()` 的 BFE4 分支只处理 `RS`，没有处理 `C`。因此不能把 BFE4 Cancel 写成可靠的 `WF20` 路径。

### 12.2 OP callback PHP 不检查前置 workflow

`mdl_OP` 根据 JSON 直接记录 raw data 并调用存储过程。当前状态是否允许 callback，主要由存储过程或数据库数据保证，不是 PHP controller 保证。

### 12.3 OP workflow callback 可以传任意 workflow

`/OP/update_workflow` 的 PHP model 直接把 `workflow_code` 传给 `usp_UpdateWorkflow_OP`。PHP 不限制只能传 WF05/WF10，也没有 `reason` 字段。

### 12.4 OP wrapper 响应不代表业务成功

`"Data Passed: ..."` 在 WebApp 调用 WebAPI 后直接返回，没有读取或解释 WebAPI 的业务响应。OP 不能仅凭该字符串判断存储过程已经成功提交。

### 12.5 精确存储过程 DML 部分未确认

这些存储过程的完整 SQL 定义都不在当前代码仓库。本次已直接读取当前 V1 数据库中的 `dbo.usp_UpdateProcessedBuyPRSTransaction` 和 `dbo.usp_UpdateWorkflow_OP` 定义，因此 5.4 节涉及的 PRS A/B 更新、主订单 unit 累加、WF16/WF10 插入及防重复条件已经确认。

以下其余存储过程尚未完成同等级的数据库定义核验：

- `usp_UpdateProcessedCashDeposit`
- `usp_UpdateProcessedBuyTransaction`
- `usp_UpdateProcessedBuyEPFTransaction`
- `usp_UpdateProcessedSellTransaction`
- `usp_UpdateProcessedSellPRSTransaction`
- `usp_UpdateProcessedSellEPFTransaction`
- `usp_UpdateProcessedCashWithdrawal`

对于这些尚未核验定义的存储过程，本文只确认：

- PHP 传入的参数；
- `MstOPRawData` 审计写入；
- 已核验 lifecycle 中的目标 workflow；
- 人工 Reject/Cancel 在 PHP model 中明确可见的资金回补。

这些过程内部每张表的插入、更新、删除顺序，以及 OP `status=0` 的精确金额回滚公式，均标记为未确认。
