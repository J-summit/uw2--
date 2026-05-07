# OP 系统对接 UWealth 统一接口文档 Demo

## 1. 文档说明

本文档用于说明 OP 系统与 UWealth 系统之间的交易、客户资料等业务对接方式。

OP 系统通过一个固定 HTTP URL 调用 UWealth。不同业务动作通过请求体中的 `type` 字段区分，业务参数统一放在 `request` 字段中。

本文档为 Demo 版本，字段、错误码、特殊业务规则仍需根据 OP 实际报文继续补充。

## 2. 接口地址

### 测试环境

```http
POST http://gateway-test.tongyu.tech/openapi/fund/op/commands
```

### 生产环境

```http
POST http://gateway.tongyu.tech/openapi/fund/op/commands
```

## 3. 鉴权方式

接口通过 UWealth OpenAPI 网关进行 HMAC-SHA256 签名认证。

### 3.1 请求头

| Header | 必填 | 说明 |
| --- | --- | --- |
| `X-App-Id` | 是 | 分配给 OP 系统的应用 ID |
| `X-Timestamp` | 是 | 请求时间戳，毫秒 |
| `X-Sign` | 是 | HMAC-SHA256 签名 |
| `Content-Type` | 是 | 固定为 `application/json` |

### 3.2 签名内容

```text
signContent = timestamp + method + path + queryString + body
```

字段说明：

| 字段 | 说明 | 示例 |
| --- | --- | --- |
| `timestamp` | 请求时间戳，取 `X-Timestamp` | `1744705238000` |
| `method` | HTTP 方法 | `POST` |
| `path` | 请求路径，不含域名 | `/openapi/fund/op/commands` |
| `queryString` | 查询字符串，不含 `?`，无参数时为空字符串 | `page=1&pageSize=50` |
| `body` | 原始请求体 JSON 字符串 | `{"type":"ORDER_PENDING_QUERY",...}` |

签名结果：

```text
sign = Base64(HMAC-SHA256(secret, signContent))
```

## 4. 统一请求格式

```json
{
  "type": "ORDER_ENTRY_CONFIRM",
  "version": "1.0",
  "requestId": "OP202605070001",
  "timestamp": 1778121000000,
  "request": {}
}
```

### 4.1 公共字段说明

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `type` | string | 是 | 业务动作类型 |
| `version` | string | 是 | 接口版本，默认 `1.0` |
| `requestId` | string | 是 | OP 请求唯一流水号，必须全局唯一，用于幂等和追踪 |
| `timestamp` | number | 是 | OP 请求时间戳，毫秒 |
| `request` | object | 是 | 业务参数，根据 `type` 不同而不同 |

## 5. 统一响应格式

UWealth 统一使用 `WealthResult<T>` 返回。

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": {}
}
```

### 5.1 响应字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | string | 返回码，`0` 表示成功，非 `0` 表示失败 |
| `error` | string | 错误信息，成功时为 `null` |
| `success` | boolean | 是否成功 |
| `data` | object | 业务响应数据。非分页接口直接返回业务对象；分页接口返回分页对象 |

### 5.2 非分页成功响应示例

非分页接口中，`data` 直接为业务返回值，不额外包装 `type`、`requestId`、`result`。

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": {
    "uwOrderNo": "OD251230150042173191",
    "opOrderNo": "OPORD202605070001",
    "workflowCode": "WF00000005"
  }
}
```

### 5.3 分页成功响应示例

分页接口中，`data` 为分页对象，包含 `totalCount` 和 `page`。

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": {
    "totalCount": 9224,
    "page": [
      {
        "uwOrderNo": "OD251230150042173191",
        "orderType": "B",
        "workflowCode": "WF00000004",
        "clientCode": "C0001",
        "fundCode": "FUND001",
        "currency": "MYR",
        "amount": 1000.00
      }
    ]
  }
}
```

### 5.4 失败响应示例

失败时 `data` 通常为空，具体是否返回业务上下文由接口实现决定。

```json
{
  "code": "0200203",
  "error": "OP order number mismatch",
  "success": false,
  "data": null
}
```

## 6. type 类型清单

| type | 方向 | 说明 |
| --- | --- | --- |
| `ORDER_PENDING_QUERY` | OP -> UWealth | OP 拉取待处理订单 |
| `ORDER_ENTRY_CONFIRM` | OP -> UWealth | OP 录入确认 |
| `ORDER_NAV_CONFIRM` | OP -> UWealth | OP NAV / unit 确认 |
| `ORDER_EXECUTION_RESULT` | OP -> UWealth | OP 执行结果回写 |
| `ORDER_REJECT` | OP -> UWealth | OP 拒绝订单 |
| `TRUST_DIRECT_BOOKING` | OP -> UWealth | OP 直接入账类交易，例如 dividend、unit split、interest |
| `CLIENT_ONBOARDING` | OP -> UWealth | 客户开户资料同步 |
| `CLIENT_UPDATE` | OP -> UWealth | 客户资料更新 |

## 7. 订单类型 orderType

| orderType | 说明 | 典型流程 |
| --- | --- | --- |
| `B` | Buy 买入 | WF02 -> WF04 -> WF05 -> WF16 -> WF10 |
| `S` | Sell 卖出 | WF02 -> WF04 -> WF05 -> WF16 -> WF10 |
| `SW` | Switch 基金转换 | WF02 -> WF06 -> WF28 -> WF17 -> WF18 -> WF10 |
| `TI` | Transfer In 单位转入 | WF04 -> WF05 -> WF10 |
| `TO` | Transfer Out 单位转出 | WF04 -> WF05 -> WF10 |
| `DP` | Deposit 入金 | FPX / Cheque / Online Banking |
| `WD` | Withdrawal 出金 | WF02 -> WF04 -> WF05 -> WF10 |
| `DV` | Dividend 分红 | OP 直接写入，完成 WF10 |
| `US` | Unit Split 拆分 | OP 直接写入，完成 WF10 |
| `DN` | Debit Note 扣款 | WF19 -> WF10 |
| `CN` | Credit Note 退款 / 调整 | OP 直接写入，完成 WF10 |
| `FS` | Force Sell 强制卖出 | WF04 -> WF05 -> WF16 -> WF10 |
| `IN` | Interest 利息入账 | OP 直接写入，完成 WF10 |
| `RSP` | 定投计划 | 建立与执行分不同流程 |

## 8. 工作流状态码

| workflowCode | 说明 |
| --- | --- |
| `WF00000002` | Pending Client Approval，等待客户确认 |
| `WF00000004` | Pending Processing，等待 OP 处理 |
| `WF00000005` | Pending Confirmation，等待确认 |
| `WF00000016` | Pending Execution，等待执行 |
| `WF00000010` | Complete Transaction，交易完成 |
| `WF00000015` | Admin Reject，管理员拒绝 |
| `WF00000019` | Partially Paid，部分付款，Debit Note 使用 |

## 9. 逻辑接口一：OP 拉取待处理订单

### 9.1 type

`ORDER_PENDING_QUERY`

### 9.2 说明

OP 系统拉取 UWealth 中等待 OP 处理的订单。UWealth 默认返回所有待 OP 拉取的订单。

`orderTypes` 为可选过滤条件；如果不传、传 `null` 或传空数组，则表示拉取所有待 OP 拉取的订单。

注意：入金 `orderType=DP` 且支付方式为 `FPX` 的订单需要排除，具体筛选字段待补充。

### 9.3 请求示例

```json
{
  "type": "ORDER_PENDING_QUERY",
  "version": "1.0",
  "requestId": "OP202605070001",
  "timestamp": 1778121000000,
  "request": {
    "orderTypes": ["B", "S", "SW", "TI", "TO", "WD", "FS"]
  }
}
```

### 9.4 响应示例

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": {
    "totalCount": 1,
    "page": [
      {
        "uwOrderNo": "OD251230150042173191",
        "orderType": "B",
        "workflowCode": "WF00000004",
        "clientCode": "C0001",
        "fundCode": "FUND001",
        "currency": "MYR",
        "amount": 1000.00
      }
    ]
  }
}
```

## 10. 逻辑接口二：OP 录入确认

### 10.1 type

`ORDER_ENTRY_CONFIRM`

### 10.2 说明

OP 完成内部录入后，回写 OP 订单号。UWealth 将订单从 `WF00000004` 推进到 `WF00000005`。

### 10.3 请求示例

```json
{
  "type": "ORDER_ENTRY_CONFIRM",
  "version": "1.0",
  "requestId": "OP202605070002",
  "timestamp": 1778121300000,
  "request": {
    "uwOrderNo": "OD251230150042173191",
    "opOrderNo": "OPORD202605070001",
    "operator": "OP001",
    "confirmedAt": "2026-05-07T10:35:00+08:00"
  }
}
```

### 10.4 成功后状态

`WF00000005`

## 11. 逻辑接口三：OP NAV 确认

### 11.1 type

`ORDER_NAV_CONFIRM`

### 11.2 说明

OP 回写 NAV、unit、成交金额等信息。UWealth 写入交易明细，并将订单推进到 `WF00000016`。

### 11.3 请求示例

```json
{
  "type": "ORDER_NAV_CONFIRM",
  "version": "1.0",
  "requestId": "OP202605070003",
  "timestamp": 1778139000000,
  "request": {
    "uwOrderNo": "OD251230150042173191",
    "opOrderNo": "OPORD202605070001",
    "nav": 1.2345,
    "unit": 810.0446,
    "grossAmount": 1000.00,
    "netAmount": 1000.00,
    "priceDate": "2026-05-07",
    "currency": "MYR"
  }
}
```

### 11.4 成功后状态

`WF00000016`

## 12. 逻辑接口四：OP 执行结果

### 12.1 type

`ORDER_EXECUTION_RESULT`

### 12.2 说明

OP 完成结算或执行后，回写最终执行结果。成功时 UWealth 将订单推进到 `WF00000010`。

### 12.3 请求示例

```json
{
  "type": "ORDER_EXECUTION_RESULT",
  "version": "1.0",
  "requestId": "OP202605070004",
  "timestamp": 1778205600000,
  "request": {
    "uwOrderNo": "OD251230150042173191",
    "opOrderNo": "OPORD202605070001",
    "executionStatus": "SUCCESS",
    "settlementDate": "2026-05-08",
    "remark": "Completed"
  }
}
```

### 12.4 成功后状态

`WF00000010`

## 13. 逻辑接口五：OP 拒绝订单

### 13.1 type

`ORDER_REJECT`

### 13.2 说明

OP 拒绝订单，UWealth 根据业务规则将订单更新为拒绝状态。

### 13.3 请求示例

```json
{
  "type": "ORDER_REJECT",
  "version": "1.0",
  "requestId": "OP202605070005",
  "timestamp": 1778122800000,
  "request": {
    "uwOrderNo": "OD251230150042173191",
    "opOrderNo": "OPORD202605070001",
    "reason": "Invalid fund account",
    "operator": "OP001"
  }
}
```

## 14. 逻辑接口六：OP 直接入账类交易

### 14.1 type

`TRUST_DIRECT_BOOKING`

### 14.2 说明

用于 OP 主动写入 UWealth 的直接入账类交易，例如：

| orderType | 说明 |
| --- | --- |
| `DV` | Dividend 分红 |
| `US` | Unit Split 拆分 |
| `CN` | Credit Note 退款 / 调整 |
| `IN` | Interest 利息入账 |

具体 request 字段待补充。

### 14.3 请求示例

```json
{
  "type": "TRUST_DIRECT_BOOKING",
  "version": "1.0",
  "requestId": "OP202605070006",
  "timestamp": 1778126400000,
  "request": {
    "orderType": "DV",
    "clientCode": "C0001",
    "fundCode": "FUND001",
    "currency": "MYR",
    "amount": 100.00,
    "bookingDate": "2026-05-07",
    "remark": "Dividend booking"
  }
}
```

## 15. 幂等规则

UWealth 根据以下字段进行幂等判断：

| 字段 | 说明 |
| --- | --- |
| `requestId` | OP 请求唯一流水号 |
| `type` | 业务动作 |
| `uwOrderNo` | UWealth 订单号，存在时参与校验 |
| `opOrderNo` | OP 订单号，存在时参与校验 |

同一个 `requestId` 重复提交时，UWealth 应返回第一次处理结果。

## 16. 错误码 Demo

| code | error | 说明 |
| --- | --- | --- |
| `0` | `null` | 成功 |
| `openapi.sign.verify.fail` | Signature verification failed | 签名验证失败 |
| `0200203` | OP order number mismatch | OP 订单号不匹配 |
| `0200204` | Invalid workflow status | 当前工作流状态不允许执行该操作 |
| `0200205` | Order not found | 订单不存在 |
| `0200206` | Duplicate request | 重复请求 |
| `0200207` | Unsupported command type | 不支持的 `type` |

## 17. 注意事项

1. OP 对接只有一个固定 URL，但每个 `type` 视为一个独立逻辑接口。
2. `request` 字段必须根据 `type` 使用不同的字段规则。
3. `type`、`version`、`requestId` 必须必填。
4. 交易状态变更后，UWealth 需要通知 client，具体通知方式待补充。
5. OP 拉取待处理订单时，需排除入金 FPX 类型订单，具体筛选字段待补充。
6. `B`、`S`、`SW`、`FS` 等订单通常走 OP pull `WF00000004` 模式。
7. `DV`、`US`、`CN`、`IN` 等 OP 直接入账类交易需要单独补充字段定义。
8. `DP`、`DN`、`RSP` 属于特殊流程，建议后续独立补充章节。

## 18. 待补充清单

| 项目 | 说明 |
| --- | --- |
| OP 真实字段 | 每个 `type` 的真实 request 字段 |
| OP 错误码 | OP 返回或 UWealth 需要暴露给 OP 的错误码 |
| DP 入金规则 | FPX、Cheque、Online Banking 的差异 |
| DN 扣款规则 | Debit Note 部分付款、扣款日期、状态推进规则 |
| RSP 定投规则 | 建立、授权、执行三段流程 |
| 通知规则 | 状态变更后通知 client / advisor 的规则 |
| 幂等落表规则 | requestId、type、orderNo 的唯一约束 |
