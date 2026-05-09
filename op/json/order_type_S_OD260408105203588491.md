# V1 与 OP 通信数据说明

## Order Type = S - Sell Order

### 1. TrnOrder 原始订单 JSON

```json
{
  "order_no": "OD260408105203588491",
  "order_grouping": "OG260408105203566998",
  "fund_id": "FN00002471",
  "client_code": "L01129WWN",
  "branch": "002",
  "BFECode": "A13AA",
  "BFESubCode": null,
  "order_type": "S",
  "order_date": "2026-04-08T10:52:03.593Z",
  "submission_date": null,
  "portfolio_code": "",
  "payment_mode_code": "PM00000001",
  "payment_curr_code": "MYR",
  "fund_curr_code": "MYR",
  "unit": 24925.39,
  "amount": -19546.49,
  "nav": 0.7842,
  "total_charges": null,
  "net_amount": -19546.49,
  "curr_rate": null,
  "f_amount": -19546.49,
  "f_nav": 0.7842,
  "f_total_charges": null,
  "f_net_amount": -19546.49,
  "m_curr_rate": 1,
  "m_amount": -19546.49,
  "m_nav": 0.7842,
  "m_total_charges": null,
  "m_net_amount": -19546.49,
  "bank_code": null,
  "bank_subcode": null,
  "cheque_no": null,
  "cheque_type": null,
  "cheque_date": null,
  "dividend_instruction": "R",
  "workflow_code": "WF00000010",
  "confirmation_date": null,
  "settlement_date": null,
  "cooling_off_date": null,
  "contract_no": null,
  "rsp_no": null,
  "created_by": "irenekhaw",
  "created_at": "2026-04-08T10:52:03.603Z",
  "created_ip": "113.211.131.210",
  "updated_by": "OP",
  "updated_at": "2026-04-10T17:16:03.150Z",
  "updated_ip": "169.254.1.2",
  "payment_no": null,
  "order_remark": null,
  "cob_subm_id": null,
  "op_order_no": "UTF*260400904"
}
```

### 2. Workflow Code 变化

`WF00000002 -> WF00000004 -> WF00000005 -> WF00000016 -> WF00000010`

| 时间 | Workflow Code | Created By | Created IP |
|---|---|---|---|
| 2026-04-08T10:52:03.630Z | WF00000002 | irenekhaw | 113.211.131.210 |
| 2026-04-08T10:55:52.137Z | WF00000004 | L01129 | 113.211.131.210 |
| 2026-04-08T15:20:23.800Z | WF00000005 | OP | 169.254.1.2 |
| 2026-04-10T15:40:43.053Z | WF00000016 | OP | 169.254.1.2 |
| 2026-04-10T17:16:03.150Z | WF00000010 | OP | 169.254.1.2 |

### 3. V1 与 OP 通信 Raw Data

#### TRANSACTION - S

```json
{
  "accountCode": "L01129WWN",
  "tradeDate": "2026-04-08 10:52:03.593",
  "trnCode": "US",
  "stockCode": "F00001J6AB",
  "amount": 0,
  "unit": "24925.39",
  "salesChargeRate": 0,
  "salesChargeAmount": "0",
  "otherFee": "0",
  "orderNo": "OD260408105203588491",
  "OrderCurr": 0,
  "OrderExRate": 1,
  "AmountSC": 0,
  "mode": "ONLINE",
  "remark": "",
  "taxAmount": "0"
}
```

```text
RESPONES FROM OP: OD260408105203588491|UTF*260400904
```

#### OP_API - WF

```json
{
  "UW_order_no": "OD260408105203588491",
  "client_code": "L01129WWN",
  "workflow_code": "WF00000005",
  "ip_address": "169.254.1.2"
}
```

#### OP_API - S

```json
{
  "OP_PK_ID": "UTF*260400904",
  "UW_order_no": "OD260408105203588491",
  "client_code": "L01129WWN",
  "unit": 24925.39,
  "nav": 0.7842,
  "branch": "002",
  "gross_amount": 19546.49,
  "net_amount": 19546.49,
  "m_gross_amount": 19546.49,
  "m_net_amount": 19546.49,
  "sale_charge_amount": 0,
  "sale_charge_rate": 0,
  "currency": "MYR",
  "currency_rate": 1,
  "fund_id": "F00001J6AB",
  "fund_amount": 0,
  "fund_m_amount": 0,
  "type": "S",
  "status": 1,
  "ip_address": "169.254.1.2"
}
```

#### OP_API - WF

```json
{
  "UW_order_no": "OD260408105203588491",
  "client_code": "L01129WWN",
  "workflow_code": "WF00000010",
  "ip_address": "169.254.1.2"
}
```

## Order Type = B - Buy Order

### 1. TrnOrder 原始订单 JSON

```json
{
  "order_no": "OD260406102449381037",
  "order_grouping": "OG260406102449250226",
  "fund_id": "FN00001816",
  "client_code": "S02005WW",
  "branch": "S51",
  "BFECode": "BPC062",
  "BFESubCode": null,
  "order_type": "B",
  "order_date": "2026-04-06T10:24:49.387Z",
  "submission_date": null,
  "portfolio_code": null,
  "payment_mode_code": "PM00000001",
  "payment_curr_code": "MYR",
  "fund_curr_code": "MYR",
  "unit": 21346.24,
  "amount": 15132.5,
  "nav": 0.7027,
  "total_charges": 132.5,
  "net_amount": 15000,
  "curr_rate": 1,
  "f_amount": 15132.5,
  "f_nav": 0.7027,
  "f_total_charges": 132.5,
  "f_net_amount": 15000,
  "m_curr_rate": 1,
  "m_amount": 15132.5,
  "m_nav": 0.7027,
  "m_total_charges": 132.5,
  "m_net_amount": 15000,
  "bank_code": null,
  "bank_subcode": null,
  "cheque_no": null,
  "cheque_type": null,
  "cheque_date": null,
  "dividend_instruction": "R",
  "workflow_code": "WF00000010",
  "confirmation_date": null,
  "settlement_date": null,
  "cooling_off_date": null,
  "contract_no": null,
  "rsp_no": null,
  "created_by": "BPC062",
  "created_at": "2026-04-06T10:24:49.387Z",
  "created_ip": "113.211.133.35",
  "updated_by": "OP",
  "updated_at": "2026-04-10T17:16:02.163Z",
  "updated_ip": "169.254.1.2",
  "payment_no": null,
  "order_remark": null,
  "cob_subm_id": null,
  "op_order_no": "UTF*260400402"
}
```

### 2. Workflow Code 变化

`WF00000002 -> WF00000004 -> WF00000005 -> WF00000016 -> WF00000010`

| 时间 | Workflow Code | Created By | Created IP |
|---|---|---|---|
| 2026-04-06T10:24:49.403Z | WF00000002 | BPC062 | 113.211.133.35 |
| 2026-04-06T10:27:45.387Z | WF00000004 | S02005 | 161.142.153.13 |
| 2026-04-06T15:33:42.467Z | WF00000005 | OP | 169.254.1.2 |
| 2026-04-10T16:43:54.630Z | WF00000016 | OP | 169.254.1.2 |
| 2026-04-10T17:16:02.163Z | WF00000010 | OP | 169.254.1.2 |

### 3. V1 与 OP 通信 Raw Data

#### TRANSACTION - B

```json
{
  "accountCode": "S02005WW",
  "tradeDate": "2026-04-06 10:24:49.387",
  "trnCode": "UP",
  "stockCode": "F0000170SY",
  "amount": 15000,
  "unit": 0,
  "salesChargeRate": 0,
  "salesChargeAmount": 0,
  "otherFee": 0,
  "orderNo": "OD260406102449381037",
  "orderCurr": "MYR",
  "orderExRate": 1,
  "amountSC": 15000,
  "mode": "ONLINE",
  "Remark": "",
  "taxAmount": 0
}
```

```text
RESPONSE FROM OP: [OD260406102449381037|UTF*260400402]
```

#### OP_API - WF

```json
{
  "UW_order_no": "OD260406102449381037",
  "client_code": "S02005WW",
  "workflow_code": "WF00000005",
  "ip_address": "169.254.1.2"
}
```

#### OP_API - B

```json
{
  "OP_PK_ID": "UTF*260400402",
  "UW_order_no": "OD260406102449381037",
  "client_code": "S02005WW",
  "unit": 21346.24,
  "nav": 0.7027,
  "branch": "S51",
  "gross_amount": -15000,
  "net_amount": -15000,
  "m_gross_amount": -15000,
  "m_net_amount": -15000,
  "sale_charge_amount": 0,
  "sale_charge_rate": 0,
  "currency": "MYR",
  "currency_rate": 1,
  "fund_id": "F0000170SY",
  "fund_amount": -15000,
  "fund_m_amount": -15000,
  "type": null,
  "status": 1,
  "ip_address": "169.254.1.2"
}
```

#### OP_API - WF

```json
{
  "UW_order_no": "OD260406102449381037",
  "client_code": "S02005WW",
  "workflow_code": "WF00000010",
  "ip_address": "169.254.1.2"
}
```

## Order Type = DP - Deposit Order

### 1. TrnOrder 原始订单 JSON

```json
{
  "order_no": "OD260410125537104695",
  "order_grouping": "OG260410125537103852",
  "fund_id": null,
  "client_code": "C02806WW",
  "branch": "004",
  "BFECode": "AWAAE",
  "BFESubCode": null,
  "order_type": "DP",
  "order_date": "2026-04-10T12:55:37.107Z",
  "submission_date": null,
  "portfolio_code": null,
  "payment_mode_code": "PM00000005",
  "payment_curr_code": "MYR",
  "fund_curr_code": null,
  "unit": null,
  "amount": -30000,
  "nav": null,
  "total_charges": 634.3,
  "net_amount": -29365.7,
  "curr_rate": null,
  "f_amount": -29365.7,
  "f_nav": null,
  "f_total_charges": 634.3,
  "f_net_amount": 0,
  "m_curr_rate": 1,
  "m_amount": -30000,
  "m_nav": null,
  "m_total_charges": 634.3,
  "m_net_amount": -29365.7,
  "bank_code": "27",
  "bank_subcode": "IB_04_MYR",
  "cheque_no": null,
  "cheque_type": "IB",
  "cheque_date": null,
  "dividend_instruction": null,
  "workflow_code": "WF00000010",
  "confirmation_date": null,
  "settlement_date": null,
  "cooling_off_date": null,
  "contract_no": null,
  "rsp_no": null,
  "created_by": "AWAAE",
  "created_at": "2026-04-10T12:55:37.107Z",
  "created_ip": "192.228.238.117",
  "updated_by": "OP",
  "updated_at": "2026-04-10T15:34:00.433Z",
  "updated_ip": "169.254.1.2",
  "payment_no": null,
  "order_remark": null,
  "cob_subm_id": null,
  "op_order_no": "CSH*260400251"
}
```

### 2. Workflow Code 变化

`WF00000023 -> WF00000003 -> WF00000010`

| 时间 | Workflow Code | Created By | Created IP |
|---|---|---|---|
| 2026-04-10T12:55:37.110Z | WF00000023 | AWAAE | 192.228.238.117 |
| 2026-04-10T12:58:55.480Z | WF00000003 | AWAAE | 192.228.238.117 |
| 2026-04-10T15:34:00.433Z | WF00000010 | OP | 169.254.1.2 |

### 3. V1 与 OP 通信 Raw Data

#### TRANSACTION - DP

```json
{
  "accountCode": "C02806WW",
  "depositDate": "2026-04-10 12:55:37.107",
  "depositMethod": "105",
  "bankAccount": "27",
  "currency": "MYR",
  "amount": 30000,
  "salesChargeRate": "2.00",
  "salesChargeAmount": 587.31,
  "otherFee": "0",
  "orderNo": "OD260410125537104695",
  "taxAmount": "46.99"
}
```

```text
RESPONES FROM OP: OD260410125537104695|CSH*260400251
```

#### OP_API - DP

```json
{
  "OP_PK_ID": "CSH*260400251",
  "UW_order_no": "OD260410125537104695",
  "client_code": "C02806WW",
  "branch": "004",
  "net_amount": 29365.7,
  "gross_amount": 30000,
  "m_net_amount": 29365.7,
  "m_gross_amount": 30000,
  "currency": "MYR",
  "currency_rate": "1",
  "status": 1,
  "ip_address": "169.254.1.2"
}
```

## Order Type = WD - Withdrawal Order

### 1. TrnOrder 原始订单 JSON

```json
{
  "order_no": "OD260410130307112334",
  "order_grouping": "OG260410130306985663",
  "fund_id": null,
  "client_code": "K02028WWN",
  "branch": "S51",
  "BFECode": "AT007",
  "BFESubCode": null,
  "order_type": "WD",
  "order_date": "2026-04-10T13:03:07.113Z",
  "submission_date": null,
  "portfolio_code": null,
  "payment_mode_code": "PM00000001",
  "payment_curr_code": "MYR",
  "fund_curr_code": "MYR",
  "unit": null,
  "amount": 20000,
  "nav": null,
  "total_charges": null,
  "net_amount": 20000,
  "curr_rate": null,
  "f_amount": null,
  "f_nav": null,
  "f_total_charges": null,
  "f_net_amount": null,
  "m_curr_rate": 1,
  "m_amount": 20000,
  "m_nav": null,
  "m_total_charges": null,
  "m_net_amount": 20000,
  "bank_code": null,
  "bank_subcode": null,
  "cheque_no": null,
  "cheque_type": null,
  "cheque_date": null,
  "dividend_instruction": null,
  "workflow_code": "WF00000010",
  "confirmation_date": null,
  "settlement_date": null,
  "cooling_off_date": null,
  "contract_no": null,
  "rsp_no": null,
  "created_by": "AT007",
  "created_at": "2026-04-10T13:03:07.113Z",
  "created_ip": "175.141.6.204",
  "updated_by": "OP",
  "updated_at": "2026-04-10T15:13:32.977Z",
  "updated_ip": "169.254.1.2",
  "payment_no": null,
  "order_remark": null,
  "cob_subm_id": null,
  "op_order_no": "SEC*260400108"
}
```

### 2. Workflow Code 变化

`WF00000002 -> WF00000004 -> WF00000010`

| 时间 | Workflow Code | Created By | Created IP |
|---|---|---|---|
| 2026-04-10T13:03:07.117Z | WF00000002 | AT007 | 175.141.6.204 |
| 2026-04-10T13:05:51.203Z | WF00000004 | K02028 | 182.62.233.219 |
| 2026-04-10T15:13:32.977Z | WF00000010 | OP | 169.254.1.2 |

### 3. V1 与 OP 通信 Raw Data

#### TRANSACTION - WD

```json
{
  "accountCode": "K02028WWN",
  "notificationDate": "2026-04-10 13:03:07.113",
  "wdlType": "P",
  "WithdrawCurrency": "MYR",
  "currency": "MYR",
  "amount": 20000,
  "orderNo": "OD260410130307112334"
}
```

```text
RESPONSE FROM OP: [OD260410130307112334|SEC*260400108]
```

#### OP_API - WD

```json
{
  "OP_PK_ID": "SEC*260400108",
  "UW_order_no": "OD260410130307112334",
  "client_code": "K02028WWN",
  "branch": "S51",
  "net_amount": -20000,
  "gross_amount": -20000,
  "m_net_amount": -20000,
  "m_gross_amount": 0,
  "currency": "MYR",
  "currency_rate": "1",
  "status": 1,
  "ip_address": "169.254.1.2"
}
```
