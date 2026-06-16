## Table of Contents

[TOC]

### 1.orderType（B） normal

#### 1.OP Pull

dev

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

uat
```http
POST http://xxxx/openapi/fund/op/commands
```

request

```json
{
  "type": "ORDER_PENDING_QUERY",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440001",
  "timestamp": 1778121000000,
  "request": {
    "orderTypes": ["B"],
    "pageSize": 1000
  }
}
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": {
    "totalCount": 4,
    "page": [
      {
        "uwOrderNo": "OD260406102449381037",
        "orderType": "B",
        "workflowCode": "WF00000004",
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
        "remark": "",
        "taxAmount": 0
      }
   }
}
```

#### 2.Booking to fund house

url  same op pull

request

```json
{
  "type": "BOOKING_TO_FUND_HOUSE",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440002",
  "timestamp": 1778121300000,
  "request": [
    {
      "uwOrderNo": "OD260406102449381037",
      "opOrderNo": "OP260406102449381037",
      "operator": "OP001",
      "confirmedAt": "2026-05-07T10:35:00+08:00",
      "success": "true"
    }
  ]
}
```


response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": [
    {
      "uwOrderNo": "OD260406102449381037",
      "opOrderNo": "OP260406102449381037",
      "success": "true"
    }
  ]
}
```

#### 3.Booking confirmation

url  same op pull

request

```json
{
  "type": "BOOKING_CONFIRMATION",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440003",
  "timestamp": 1778139000000,
  "request": [
    {
      "opPkId": "UTF*260400402",
      "uwOrderNo": "OD260406102449381037",
      "clientCode": "S02005WW",
      "unit": 21346.24,
      "nav": 0.7027,
      "branch": "S51",
      "grossAmount": -15000,
      "netAmount": -15000,
      "mGrossAmount": -15000,
      "mNetAmount": -15000,
      "saleChargeAmount": 0,
      "saleChargeRate": 0,
      "currency": "MYR",
      "currencyRate": 1,
      "fundId": "F0000170SY",
      "fundAmount": -15000,
      "fundMAmount": -15000,
      "type": null,
      "status": 1,
      "ipAddress": "169.254.1.2"
    }
  ]
}
```

response

```
{
  "code": "0",
  "error": null,
  "success": true,
  "data": [
    {
      "uwOrderNo": "OD260406102449381037",
      "opOrderNo": "UTF*260400402",
      "success": "true"
    }
  ]
}
```

#### 4.Settlement

url  same op pull



requset

```json
{
  "type": "SETTLEMENT",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440005",
  "timestamp": 1778126400000,
  "request": [
    {
      "orderType": "B",
      "uwOrderNo": "OD260406102449381037",
      "clientCode": "S02005WW",
      "workflowCode": "WF00000010",
      "ipAddress": "169.254.1.2"
    }
    ]
 }
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": [
    {
      "uwOrderNo": "OD260406102449381037",
      "opOrderNo": "UTF*260400402",
      "success": "true"
    }
  ]
}
```

#### 5.OP Rejects Orders

url  same op pull

request

```json
{
  "type": "ORDER_REJECT",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440006",
  "timestamp": 1778122800000,
  "request": [
    {
      "uwOrderNo": "OD251230150042173191",
      "opOrderNo": "OPORD202605070001",
      "reason": "Invalid fund account",
      "operator": "OP001"
    }
  ]
}
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": [
    {
      "uwOrderNo": "OD251230150042173191",
      "opOrderNo": "OPORD202605070001",
      "success": "true"
    }
  ]
}
```

### 2.OrderType（DP）cheque/OB

#### 1.OP Pull

dev

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

uat

```http
POST http://xxxx/openapi/fund/op/commands
```

request

```json
{
  "type": "ORDER_PENDING_QUERY",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440001",
  "timestamp": 1778121000000,
  "request": {
    "orderTypes": ["DP"],
    "pageSize": 1000
  }
}
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": {
    "totalCount": 4,
    "page": [
      {
        "uwOrderNo": "OD260410125537104695",
        "orderType": "DP",
        "workflowCode": "WF00000004",
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
   }
}
```

#### 2.cash_deposit_confirm

url  same op pull

request

```json
{
  "type": "CASH_DEPOSIT_CONFIRM",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440002",
  "timestamp": 1778121300000,
  "request": [
    {
      "uwOrderNo": "OD260406102449381037",
      "opOrderNo": "OP260406102449381037",
      "operator": "OP001",
      "confirmedAt": "2026-05-07T10:35:00+08:00",
      "success": "true"
    }
  ]
}
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": [
    {
      "uwOrderNo": "OD260406102449381037",
      "opOrderNo": "OP260406102449381037",
      "success": "true"
    }
  ]
}
```

#### 3.settle

url  same op pull

request

```json
{
  "type": "COMPLETED",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440005",
  "timestamp": 1778126400000,
  "request": [
    {
      "orderType": "DP",
      "opPkId": "CSH*260400251",
      "uwOrderNo": "OD260410125537104695",
      "clientCode": "C02806WW",
      "branch": "004",
      "netAmount": 29365.7,
      "grossAmount": 30000,
      "mNetAmount": 29365.7,
      "mGrossAmount": 30000,
      "currency": "MYR",
      "currencyRate": "1",
      "status": 1,
      "ipAddress": "169.254.1.2"
    }
  ]
}
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": [
    {
      "uwOrderNo": "OD260406102449381037",
      "opOrderNo": "UTF*260400402",
      "success": "true"
    }
  ]
}
```

### 3.OrderType(S)sell

#### 1.OP Pull

dev

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

uat

```http
POST http://xxxx/openapi/fund/op/commands
```

request

```json
{
  "type": "ORDER_PENDING_QUERY",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440011",
  "timestamp": 1778121000000,
  "request": {
    "orderTypes": ["S"],
    "pageSize": 1000
  }
}
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": {
    "totalCount": 1,
    "page": [
      {
        "uwOrderNo": "OD260408105203588491",
        "orderType": "S",
        "workflowCode": "WF00000004",
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
        "orderCurr": 0,
        "orderExRate": 1,
        "amountSC": 0,
        "mode": "ONLINE",
        "remark": "",
        "taxAmount": "0"
      }
    ]
  }
}
```

#### 2.Booking to fund house

url  same op pull

request

```json
{
  "type": "BOOKING_TO_FUND_HOUSE",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440012",
  "timestamp": 1778121300000,
  "request": [
    {
      "uwOrderNo": "OD260408105203588491",
      "opOrderNo": "OP260408105203588491",
      "operator": "OP001",
      "confirmedAt": "2026-05-07T10:35:00+08:00",
      "success": "true"
    }
  ]
}
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": [
    {
      "uwOrderNo": "OD260408105203588491",
      "opOrderNo": "OP260408105203588491",
      "success": "true"
    }
  ]
}
```

#### 3.Unit confirmation

url  same op pull

request

```json
{
  "type": "ORDER_UNIT_CONFIRM",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440013",
  "timestamp": 1778139000000,
  "request": [
    {
      "opPkId": "UTF*260400904",
      "uwOrderNo": "OD260408105203588491",
      "clientCode": "L01129WWN",
      "unit": 24925.39,
      "nav": 0.7842,
      "branch": "002",
      "grossAmount": 19546.49,
      "netAmount": 19546.49,
      "mGrossAmount": 19546.49,
      "mNetAmount": 19546.49,
      "saleChargeAmount": 0,
      "saleChargeRate": 0,
      "currency": "MYR",
      "currencyRate": 1,
      "fundId": "F00001J6AB",
      "fundAmount": 0,
      "fundMAmount": 0,
      "type": "S",
      "status": 1,
      "ipAddress": "169.254.1.2"
    }
  ]
}
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": [
    {
      "uwOrderNo": "OD260408105203588491",
      "opOrderNo": "UTF*260400904",
      "success": "true"
    }
  ]
}
```

#### 4.Settlement

url  same op pull

request

```json
{
  "type": "SETTLEMENT",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440014",
  "timestamp": 1778126400000,
  "request": [
    {
      "orderType": "S",
      "uwOrderNo": "OD260408105203588491",
      "clientCode": "L01129WWN",
      "workflowCode": "WF00000010",
      "ipAddress": "169.254.1.2"
    }
  ]
}
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": [
    {
      "uwOrderNo": "OD260408105203588491",
      "opOrderNo": "UTF*260400904",
      "success": "true"
    }
  ]
}
```

#### 5.OP Rejects Orders

url  same op pull

request

```json
{
  "type": "ORDER_REJECT",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440015",
  "timestamp": 1778122800000,
  "request": [
    {
      "uwOrderNo": "OD260408105203588491",
      "opOrderNo": "OP260408105203588491",
      "reason": "Invalid redemption request",
      "operator": "OP001"
    }
  ]
}
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": [
    {
      "uwOrderNo": "OD260408105203588491",
      "opOrderNo": "OP260408105203588491",
      "success": "true"
    }
  ]
}
```

### 4.OrderType(WD)withdraw

#### 1.OP Pull

dev

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

uat

```http
POST http://xxxx/openapi/fund/op/commands
```

request

```json
{
  "type": "ORDER_PENDING_QUERY",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440021",
  "timestamp": 1778121000000,
  "request": {
    "orderTypes": ["WD"],
    "pageSize": 1000
  }
}
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": {
    "totalCount": 1,
    "page": [
      {
        "uwOrderNo": "OD260410130307112334",
        "orderType": "WD",
        "workflowCode": "WF00000004",
        "accountCode": "K02028WWN",
        "notificationDate": "2026-04-10 13:03:07.113",
        "wdlType": "P",
        "withdrawCurrency": "MYR",
        "currency": "MYR",
        "amount": 20000,
        "orderNo": "OD260410130307112334"
      }
    ]
  }
}
```

#### 2.Withdraw entry confirm

url  same op pull

request

```json
{
  "type": "ORDER_ENTRY_CONFIRM",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440022",
  "timestamp": 1778121300000,
  "request": [
    {
      "uwOrderNo": "OD260410130307112334",
      "opOrderNo": "OP260410130307112334",
      "operator": "OP001",
      "confirmedAt": "2026-05-07T10:35:00+08:00",
      "success": "true"
    }
  ]
}
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": [
    {
      "uwOrderNo": "OD260410130307112334",
      "opOrderNo": "OP260410130307112334",
      "success": "true"
    }
  ]
}
```

#### 3.settle

url  same op pull

request

```json
{
  "type": "COMPLETED",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440023",
  "timestamp": 1778126400000,
  "request": [
    {
      "orderType": "WD",
      "opPkId": "SEC*260400108",
      "uwOrderNo": "OD260410130307112334",
      "clientCode": "K02028WWN",
      "branch": "S51",
      "netAmount": -20000,
      "grossAmount": -20000,
      "mNetAmount": -20000,
      "mGrossAmount": 0,
      "currency": "MYR",
      "currencyRate": "1",
      "status": 1,
      "ipAddress": "169.254.1.2"
    }
  ]
}
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": [
    {
      "uwOrderNo": "OD260410130307112334",
      "opOrderNo": "SEC*260400108",
      "success": "true"
    }
  ]
}
```

#### 4.OP Rejects Orders

url  same op pull

request

```json
{
  "type": "ORDER_REJECT",
  "version": "1.0",
  "requestId": "550e8400-e29b-41d4-a716-446655440024",
  "timestamp": 1778122800000,
  "request": [
    {
      "uwOrderNo": "OD260410130307112334",
      "opOrderNo": "OP260410130307112334",
      "reason": "Invalid withdrawal request",
      "operator": "OP001"
    }
  ]
}
```

response

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": [
    {
      "uwOrderNo": "OD260410130307112334",
      "opOrderNo": "OP260410130307112334",
      "success": "true"
    }
  ]
}
```
