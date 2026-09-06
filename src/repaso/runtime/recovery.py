"""Retry preserved work at daily close, including work that outlived SQS retries."""


async def recover_pending(services, max_attempts=20):
    from repaso.runtime.entrypoint import invoke_async

    attempted = recovered = 0
    for family in services.store.list_families():
        records = services.store.list_records(family.id, "pending#")
        pending = sorted(
            (r for r in records if r.payload.get("state") == "pending"),
            key=lambda r: r.payload["created_at"],
        )
        for record in pending:
            if attempted >= max_attempts:
                return {"attempted": attempted, "recovered": recovered}
            attempted += 1
            result = await invoke_async(record.payload["request"], services)
            if not result.get("ok"):
                break  # Keep a family's work in order; retry at the next close.
            recovered += 1
    return {"attempted": attempted, "recovered": recovered}
