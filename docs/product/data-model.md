# State and ownership

DynamoDB stores typed documents with `pk`, `sk` and a JSON-compatible `doc`. Family, student, material, item, session and escalation records have explicit ownership. Primary records and access mirrors are deleted together; erasure scans the primary table consistently to include interrupted dual writes and legacy copies.

| Record | Purpose |
| --- | --- |
| Family / student | Channel, timezone, practice settings, alias and invitation-scoped cohort |
| Item / material | Family and material provenance; only explicit system/simulated items enter the common production bank |
| Session | Planned IDs, capsule, outgoing delivery snapshot, actual acknowledgment time and progress |
| Grade | Stable ID, origin, provisional/human final outcome, superseded ID and original response time |
| Answer text | The words the student wrote, on their own row beside the grade, expiring after seven days |
| Mastery / spaced state | Learning heuristics, updated together with a unique outcome marker |
| Operation | Scoped pending request, invocation result, enrollment/response/ingest journal, outbox receipts or notice |
| Adaptation | Student and competency, requested action, difficulty/type/load limits, source and expiry |
| Erasure receipt | Temporary opaque callback hash allowing deletion/acknowledgment recovery; completed record has no family/chat ID |
| Lease / budget | Expiring owner lease and atomically reserved family/global daily call counters |

A grade row carries the attempt and not the words: what the student wrote is written beside it on a row that expires, so the outcome stays readable after the sentence behind it is gone. Reads join the two while both exist.

Human final grades supersede provisional grades in signal and quality calculations. Correct and incorrect reviews both count; unresolved answers stay out of final-only quality statistics. Student grade reads merge primary copies with legacy index entries and deduplicate.

The local adapter uses locked JSON tables, atomic file replacement and a write-ahead transaction journal. It is intended for small demos and tests; rewriting tables becomes slow in cohort simulations. DynamoDB conditionally commits learning updates and their marker in one transaction. A conditional claim alone is not proof that a downstream effect completed.

A family deletion pauses schedules first, removes media versions and grades, clears dependent records, and removes ownership roots last. This order supports retry after a partial error. Local private event/outbox/telemetry rows are purged as well. Managed logs and backups have the retention limits described in the product consent; Telegram history is outside this database.
