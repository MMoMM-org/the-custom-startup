# Event-Driven Patterns Reference

## Event Schema Design

Every event must be a self-contained, immutable fact.

### Minimum Required Fields

```typescript
interface BaseEvent {
  eventId: string;       // UUID v4 — unique per event instance
  correlationId: string; // traces a business transaction across services
  causationId: string;   // eventId of the event that caused this one
  aggregateId: string;   // ID of the entity this event belongs to
  aggregateType: string; // e.g. "Order", "User"
  eventType: string;     // past-tense name e.g. "OrderPlaced"
  occurredAt: string;    // ISO 8601 UTC
  version: number;       // schema version for forward compatibility
  payload: unknown;      // event-specific data
}
```

### Naming Conventions

| Type | Pattern | Examples |
|------|---------|---------|
| Event | `{Aggregate}{PastTense}` | `OrderPlaced`, `PaymentFailed`, `UserDeleted` |
| Command | `{Imperative}{Aggregate}` | `PlaceOrder`, `CancelPayment`, `DeleteUser` |
| Query | `Get{Aggregate}By{Field}` | `GetOrderById`, `GetUserByEmail` |

Commands may be rejected. Events cannot — they are facts that have already occurred.

---

## Command/Event Separation

```typescript
// WRONG — command disguised as event
type OrderEvent = { type: "PlaceOrder"; items: Item[] };  // imperative = command

// CORRECT — separate command and event
type PlaceOrderCommand = { type: "PlaceOrder"; items: Item[] };
type OrderPlacedEvent  = { type: "OrderPlaced"; orderId: string; items: Item[] };
```

Command handler pattern:
```typescript
async function handlePlaceOrder(cmd: PlaceOrderCommand): Promise<OrderPlacedEvent> {
  // Validate, decide, emit
  const order = Order.place(cmd.items);  // may throw if invalid
  return {
    eventId: uuid(),
    correlationId: cmd.correlationId,
    causationId: cmd.commandId,
    aggregateId: order.id,
    aggregateType: "Order",
    eventType: "OrderPlaced",
    occurredAt: new Date().toISOString(),
    version: 1,
    payload: { orderId: order.id, items: order.items, total: order.total },
  };
}
```

---

## Idempotent Handlers

Every handler must be safe to run multiple times with the same event.

### Pattern 1 — Idempotency Key in DB

```typescript
async function handleOrderPlaced(event: OrderPlacedEvent): Promise<void> {
  const exists = await db.query(
    "SELECT 1 FROM processed_events WHERE event_id = $1",
    [event.eventId]
  );
  if (exists.rowCount > 0) return; // already processed

  await db.transaction(async (tx) => {
    await tx.query("INSERT INTO orders ...");
    await tx.query(
      "INSERT INTO processed_events (event_id, processed_at) VALUES ($1, NOW())",
      [event.eventId]
    );
  });
}
```

### Pattern 2 — Conditional Update (upsert)

```typescript
await db.query(`
  INSERT INTO inventory (product_id, reserved)
  VALUES ($1, $2)
  ON CONFLICT (product_id) DO UPDATE
    SET reserved = inventory.reserved + EXCLUDED.reserved
    WHERE NOT EXISTS (
      SELECT 1 FROM processed_events WHERE event_id = $3
    )
`, [productId, quantity, event.eventId]);
```

---

## Event Sourcing

An aggregate's state is rebuilt by replaying its event history.

```typescript
class Order {
  id!: string;
  status!: "pending" | "paid" | "shipped" | "cancelled";
  total!: number;

  static rehydrate(events: BaseEvent[]): Order {
    const order = new Order();
    for (const event of events) {
      order.apply(event);
    }
    return order;
  }

  private apply(event: BaseEvent): void {
    switch (event.eventType) {
      case "OrderPlaced":
        this.id = event.aggregateId;
        this.status = "pending";
        this.total = (event.payload as any).total;
        break;
      case "PaymentReceived":
        this.status = "paid";
        break;
      case "OrderShipped":
        this.status = "shipped";
        break;
      case "OrderCancelled":
        this.status = "cancelled";
        break;
    }
  }
}
```

### Event Store Pattern

```typescript
interface EventStore {
  append(
    aggregateId: string,
    expectedVersion: number,  // optimistic concurrency control
    events: BaseEvent[]
  ): Promise<void>;
  load(aggregateId: string, fromVersion?: number): Promise<BaseEvent[]>;
}
```

Optimistic concurrency: if current stream version ≠ `expectedVersion`, reject the append — another writer modified the aggregate concurrently.

---

## CQRS (Command Query Responsibility Segregation)

Separate the write model (commands → events) from the read model (projections).

```
Write side:                      Read side:
  Command                          Event
    │                                │
    ▼                                ▼
  CommandHandler               EventHandler (projector)
    │                                │
    ▼                                ▼
  AggregateRoot                Read Model (DB view)
    │                                │
    ▼                                ▼
  EventStore ──────────────────────►QueryHandler
```

### Projection Example

```typescript
// Projector keeps read model in sync
async function projectOrderSummary(event: BaseEvent): Promise<void> {
  switch (event.eventType) {
    case "OrderPlaced":
      await db.query(
        "INSERT INTO order_summaries (id, status, total, created_at) VALUES ($1, 'pending', $2, $3)",
        [event.aggregateId, event.payload.total, event.occurredAt]
      );
      break;
    case "PaymentReceived":
      await db.query(
        "UPDATE order_summaries SET status = 'paid' WHERE id = $1",
        [event.aggregateId]
      );
      break;
  }
}
```

---

## Saga Pattern (Process Manager)

Coordinates multi-step workflows across service boundaries without distributed transactions.

```typescript
// Choreography saga — each service reacts to events
// OrderService emits OrderPlaced
// PaymentService listens → emits PaymentProcessed or PaymentFailed
// InventoryService listens → emits InventoryReserved or InventoryUnavailable
// On failure: compensating events roll back previous steps

// Orchestration saga — central coordinator
class OrderFulfillmentSaga {
  async handle(event: BaseEvent): Promise<BaseEvent[]> {
    switch (this.state.step) {
      case "awaiting_payment":
        if (event.eventType === "PaymentProcessed") {
          this.state.step = "awaiting_inventory";
          return [new ReserveInventoryCommand(...)];
        }
        if (event.eventType === "PaymentFailed") {
          return [new CancelOrderCommand(...)];  // compensate
        }
    }
    return [];
  }
}
```

**Compensating events** (not commands — they record what happened):
- `OrderCancelled` (compensates `OrderPlaced`)
- `PaymentRefunded` (compensates `PaymentProcessed`)
- `InventoryReleased` (compensates `InventoryReserved`)

---

## Ordering and Partitioning

### What is Guaranteed

| Guarantee | When |
|-----------|------|
| Order within a partition | Same partition key (e.g. `aggregateId`) |
| No global order | Across partitions |
| At-least-once delivery | Most brokers (Kafka, SQS, EventBridge) |
| Exactly-once | Requires idempotent handlers + transactional outbox |

### Transactional Outbox Pattern

Prevents the dual-write problem (DB write succeeds but event publish fails):

```typescript
await db.transaction(async (tx) => {
  // 1. Write domain state
  await tx.query("UPDATE orders SET status = 'paid' WHERE id = $1", [orderId]);

  // 2. Write event to outbox in SAME transaction
  await tx.query(
    "INSERT INTO outbox (event_id, event_type, payload, created_at) VALUES ($1, $2, $3, NOW())",
    [event.eventId, event.eventType, JSON.stringify(event)]
  );
});
// Separate process (relay) reads outbox and publishes to broker
```

---

## Dead Letter Queue (DLQ)

Events that fail after N retries must not be lost.

```typescript
async function processWithRetry(event: BaseEvent, handler: Handler): Promise<void> {
  const maxAttempts = 3;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      await handler(event);
      return;
    } catch (err) {
      if (attempt === maxAttempts) {
        await dlq.publish({ event, error: String(err), attempts: maxAttempts });
        return;
      }
      await sleep(attempt * 1000);  // exponential backoff
    }
  }
}
```

---

## Anti-Patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| Event carries mutable object reference | Handler mutates shared state | Serialize to plain object at emit time |
| Query inside event handler | Creates ordering dependency on read model | Project event → query projection |
| Fat event (entire aggregate state) | Tight coupling, large payload | Emit only what changed |
| Event as command (`PlaceOrder` event) | Recipient can't reject it | Use a command type with explicit handler |
| Polling instead of projecting | Misses events, eventual consistency violated | Subscribe to event stream, update projection |
| Ignoring DLQ | Silent data loss | Monitor DLQ size; alert on any items |
