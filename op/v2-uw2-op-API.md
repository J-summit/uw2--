| **Date** | **Author** | **Change Description** | **Version** |
| --- | --- | --- | --- |
| 2026-07-29 | majie | Corrected the Buy and Sell entry confirmation section titles and command type from `BOOKING_TO_FUND_HOUSE` to `ORDER_ENTRY_CONFIRM` | V2.0 |
| 2026-07-29 | majie | Corrected the cash deposit confirmation command type from `CASH_DEPOSIT_CONFIRM` to `ORDER_ENTRY_CONFIRM` | V2.0 |
| 2026-07-30 | majie | add switch （op json demo） | V2.0 |
| 2026-08-07 | majie | add Buy ,Sell  BOOKING_TO_FUND_HOUSE,  uw  op entry confirm don't update workflowCode | V2.0 |

## Table of Contents

[TOC]

### 1.orderType（B） normal

#### 1.OP Pull

dev

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
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
        "uwOrderNo": "OD260728222511198007",
        "orderType": "B",
        "workflowCode": "WF00000004",
        "accountCode": "J00572WWN",
        "clientCode": "J00572WWN",
        "tradeDate": "2026-07-28 22:25:11.198",
        "trnCode": "UP",
        "stockCode": "F00000ZV4P",
        "fundId": "FN00000009",
        "prsOrders": [],
        "amount": 100000,
        "unit": 0,
        "salesChargeRate": 0,
        "salesChargeAmount": 0,
        "otherFee": 0,
        "orderNo": "OD260728222511198007",
        "orderCurr": "MYR",
        "orderExRate": 1,
        "amountSC": 100000,
        "mode": "ONLINE",
        "remark": "",
        "taxAmount": 0
      }
   }
}
```

#### 2.Buy entry confirm

no update workflowCode

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

request

```json
{
  "type": "ORDER_ENTRY_CONFIRM",
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

#### 3. BOOKING_TO_FUND_HOUSE

update workflow  WF05

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

request
```json
{
  "type": "BOOKING_TO_FUND_HOUSE",
  "version": "1.0",
  "requestId": "c9dde5fc-aa6b-4c2e-bb96-8ba6b3dbdebb",
  "timestamp": 1786090747229,
  "request": [
    {
      "uwOrderNo": "OD260807155307985004",
      "orderType": "B",
      "opOrderNo": "OP260807155307985004",
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
      "uwOrderNo": "OD260807155307985004",
      "opOrderNo": "OP260807155307985004",
      "workflowCode": "WF00000005",
      "success": true,
      "code": null,
      "error": null
    }
  ]
}
```




#### 4.Booking confirmation

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

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

#### 5.Settlement

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```



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

#### 6.OP Rejects Orders -todo

same with  Booking confirmation ( status =0  ) refer uw v1

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

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
      "status": 0,
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

### 2.OrderType（DP）cheque/OB

#### 1.OP Pull

dev

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
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
        "uwOrderNo": "OD260703153407074006",
        "orderType": "DP",
        "workflowCode": "WF00000004",
        "accountCode": "A00001WW",
        "depositDate": "2026-07-03 15:34:07.075",
        "depositMethod": "105",
        "bankAccount": "-",
        "currency": "CNY",
        "amount": 10000,
        "salesChargeRate": 0,
        "salesChargeAmount": 0,
        "otherFee": 0,
        "orderNo": "OD260703153407074006",
        "taxAmount": 0,
        "supDoc": [
          {
            "url": "\\\\10.10.20.100\\storage\\osd\\RECEIPT\\2026\\07\\ff8cc1cd7ad44bd097a1c16a16539071.png",
            "originalFileName": "Snipaste_2026-06-04_18-17-04.png"
          }
   }
}
```

#### 2.cash_deposit_confirm

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

request

```json
{
  "type": "ORDER_ENTRY_CONFIRM",
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

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

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

#### 2.Sell entry confirm

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

request

```json
{
  "type": "ORDER_ENTRY_CONFIRM",
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

#### 3.BOOKING_TO_FUND_HOUSE

update workflow  WF05

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

request

```json
{
  "type": "ORDER_ENTRY_CONFIRM",
  "version": "1.0",
  "requestId": "90b9f853-6cbb-4940-939a-98fab7ca4658",
  "timestamp": 1786094930097,
  "request": [
    {
      "uwOrderNo": "OD260721015459682002",
      "orderType": "S",
      "opOrderNo": "OP260721015459682002",
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
      "uwOrderNo": "OD260721015459682002",
      "opOrderNo": "OP260721015459682002",
      "workflowCode": "WF00000004",
      "success": true,
      "code": null,
      "error": null
    }
  ]
}
```



#### 4.Unit confirmation

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

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

#### 5.Settlement

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

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

#### 6.OP Rejects Orders

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

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

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

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

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

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

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

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

### 5.OrderType（SW） switch

#### 1.OP pull

dev

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

request

```json
{
  "type": "ORDER_PENDING_QUERY",
  "version": "1.0",
  "requestId": "aa10aef4-cebf-4cdc-947e-2b74f53ae8e8",
  "timestamp": 1785735229787,
  "request": {
    "orderTypes": [
      "SW"
    ],
    "workflowCode": "WF00000004",
    "pageNo": 1,
    "pageSize": 1000
  }
}
```

response:

```json
{
  "code": "0",
  "error": null,
  "success": true,
  "data": {
    "totalCount": 1,
    "page": [
      {
        "uwOrderNo": "OD260803103631160003",
        "orderType": "SW",
        "workflowCode": "WF00000004",
        "accountCode": "C00375WWN",
        "clientCode": "C00375WWN",
        "branch": "S51       ",
        "tradeDate": "2026-08-03 10:36:31.133",
        "SwitchType": "1",
        "SellDetail": "F00000PYG2,675.36,SO260803103631185005",
        "BuyDetail": "F00000PYG1,100.00,SO260803103631188006",
        "OrderGrpNo": "OD260803103631160003",
        "mode": "ONLINE"
      }
    ]
  }
}
```

#### 2.Switch entry confirm

dev

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

request

```json
{
  "type": "ORDER_ENTRY_CONFIRM",
  "version": "1.0",
  "requestId": "8afc56fc-cca7-4beb-a61b-38e47570c6f8",
  "timestamp": 1785735234639,
  "request": [
    {
      "uwOrderNo": "OD260803103631160003",
      "legs": [
        {
          "switchOrderNo": "SO260803103631185005",
          "opSwitchOrderNo": "OP260803103631185005"
        },
        {
          "switchOrderNo": "SO260803103631188006",
          "opSwitchOrderNo": "OP260803103631188006"
        }
      ],
      "success": true,
      "opOrderNo": "OP260803103631160003",
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
      "uwOrderNo": "OD260803103631160003",
      "opOrderNo": "OP260803103631160003",
      "workflowCode": "WF00000006",
      "success": true,
      "code": null,
      "error": null,
      "legs": [
        {
          "switchOrderNo": "SO260803103631185005",
          "opSwitchOrderNo": "OP260803103631185005",
          "workflowCode": "WF00000006",
          "code": null,
          "error": null,
          "success": true
        },
        {
          "switchOrderNo": "SO260803103631188006",
          "opSwitchOrderNo": "OP260803103631188006",
          "workflowCode": "WF00000008",
          "code": null,
          "error": null,
          "success": true
        }
      ]
    }
  ]
}
```

#### 3.SW UPDATE_WORKFLOW

dev

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

request

```json
{
  "type": "UPDATE_WORKFLOW",
  "version": "1.0",
  "requestId": "a745a59e-e285-4744-b08f-8fb09d50274b",
  "timestamp": 1785735238044,
  "request": [
    {
      "workflowCode": "WF00000007",
      "uwOrderNo": "SO260803103631185005",
      "orderType": "SW",
      "operator": "OP001",
      "uwOrderGrpNo": "OD260803103631160003",
      "opOrderNo": "OP260803103631185005"
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
      "uwOrderNo": "SO260803103631185005",
      "opOrderNo": "OP260803103631185005",
      "uwOrderGrpNo": "OD260803103631160003",
      "opOrderGrpNo": "OP260803103631160003",
      "workflowCode": "WF00000007",
      "success": true,
      "code": null,
      "error": null
    }
  ]
}
```



#### 4.SW_ORDER_UNIT_CONFIRM -sell

dev

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

request

```json
{
  "type": "SW_ORDER_UNIT_CONFIRM",
  "version": "1.0",
  "requestId": "84aa6ed7-4883-4b8a-a75e-95e78cb2e97f",
  "timestamp": 1785735243092,
  "request": [
    {
      "nav": 1.3139,
      "unit": 675.36,
      "grossAmount": 887.36,
      "netAmount": 887.36,
      "amount": 887.36,
      "uwOrderNo": "SO260803103631185005",
      "orderType": "SW",
      "operator": "OP001",
      "uwOrderGrpNo": "OD260803103631160003",
      "opPkId": "OP260803103631185005",
      "clientCode": "C00375WWN",
      "branch": "S51       ",
      "switchOutFundId": "F00000PYG2",
      "type": "1",
      "status": 1
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
      "uwOrderNo": "SO260803103631185005",
      "opOrderNo": "OP260803103631185005",
      "uwOrderGrpNo": "OD260803103631160003",
      "opOrderGrpNo": "OP260803103631160003",
      "workflowCode": "WF00000017",
      "success": true,
      "code": null,
      "error": null
    }
  ]
}
```



#### 5.SW_AMOUNT_CONFIRM- buy

```json
{
  "type": "SW_AMOUNT_CONFIRM",
  "version": "1.0",
  "requestId": "c1fab7b9-331d-401a-bef7-59c9e9912d06",
  "timestamp": 1785735248818,
  "request": [
    {
      "nav": 1.3747,
      "unit": 645.493562,
      "grossAmount": 887.36,
      "netAmount": 887.36,
      "amount": 887.36,
      "uwOrderNo": "SO260803103631188006",
      "orderType": "SW",
      "operator": "OP001",
      "uwOrderGrpNo": "OD260803103631160003",
      "opPkId": "OP260803103631188006",
      "clientCode": "C00375WWN",
      "branch": "S51       ",
      "switchInFundId": "FN00000167",
      "type": 1,
      "status": 1,
      "ip_address": "169.254.1.2"
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
      "uwOrderNo": "SO260803103631188006",
      "opOrderNo": "OP260803103631188006",
      "uwOrderGrpNo": "OD260803103631160003",
      "opOrderGrpNo": "OP260803103631160003",
      "workflowCode": "WF00000018",
      "success": true,
      "code": null,
      "error": null
    }
  ]
}
```



#### 7.SETTLEMENT

dev

```http
POST http://113.31.110.251:42157/openapi/fund/op/commands
```

request

```json
{
  "type": "SETTLEMENT",
  "version": "1.0",
  "requestId": "e009089b-7434-4960-ad78-b845d24aba49",
  "timestamp": 1785735245744,
  "request": [
    {
      "uwOrderNo": "SO260803103631185005",
      "orderType": "SW",
      "operator": "OP001",
      "uwOrderGrpNo": "OD260803103631160003",
      "opOrderNo": "OP260803103631185005"
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
      "uwOrderNo": "SO260803103631185005",
      "opOrderNo": "OP260803103631185005",
      "uwOrderGrpNo": "OD260803103631160003",
      "opOrderGrpNo": "OP260803103631160003",
      "workflowCode": "WF00000010",
      "success": true,
      "code": null,
      "error": null
    }
  ]
}
```

