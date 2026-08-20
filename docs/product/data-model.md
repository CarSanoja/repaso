# Data model

Every aggregate lives in one DynamoDB table (`REPASO_DDB_TABLE`, default `repaso`) with a single
overloaded key pair `pk` / `sk` and one global secondary index `gsi1` (`gsi1pk` / `gsi1sk`). The
model itself is stored under the attribute `doc` as its `model_dump(mode="json")` payload; the key
attributes exist only for access paths, never as the source of truth.

## Key map

| Entity | pk | sk | gsi1 |
| --- | --- | --- | --- |
| Family | `FAMILY#<family_id>` | `PROFILE` | — |
| Family chat lookup | `CHAT#<channel>#<chat_ref>` | `FAMILY` | — |
| Student (family view) | `FAMILY#<family_id>` | `STUDENT#<student_id>` | — |
| Student (profile) | `STUDENT#<student_id>` | `PROFILE` | — |
| Mastery state | `STUDENT#<student_id>` | `MASTERY#<competency_id>` | — |
| Spaced item state | `STUDENT#<student_id>` | `SPACED#<item_id>` | — |
| Item | `ITEM#<item_id>` | `PROFILE` | `COMP#<competency_id>` / `ITEM#<item_id>` |
| Material | `MATERIAL#<material_id>` | `PROFILE` | — |
| Session (student view) | `STUDENT#<student_id>` | `SESSION#<session_date>` | — |
| Session (profile) | `SESSION#<session_id>` | `PROFILE` | — |
| Escalation (family view) | `FAMILY#<family_id>` | `ESC#<escalation_id>` | `ESCPENDING#<family_id>` / `ESC#<escalation_id>` when pending |
| Escalation (profile) | `ESC#<escalation_id>` | `PROFILE` | — |
| Quarantine item | `FAMILY#<family_id>` | `QUAR#<quarantine_id>` | — |
| Claim | `CLAIM#<key>` | `CLAIM` | — |

The lookup and profile rows are duplicates written in the same call as the primary row: they buy a
`GetItem` where the primary key alone would force a scan. A resolved escalation is rewritten
without its `gsi1` attributes, which drops it out of the pending index.

## Local mode

With `REPASO_LOCAL_MODE=1` the same `StateStore` protocol is served by `LocalStateStore`, one JSON
file per aggregate under `<REPASO_LOCAL_DATA_DIR>/state/` (`families.json`, `students.json`,
`mastery.json`, `spaced.json`, `items.json`, `materials.json`, `sessions.json`,
`escalations.json`, `quarantine.json`, `claims.json`), each keyed by the same identifiers the
DynamoDB rows use. A write is read-modify-write under a process lock and lands through a temporary
file plus `os.replace`, so a reader never sees a half-written file and a crash mid-write leaves the
previous revision intact. Queries that DynamoDB serves from the index or a `begins_with` on the
sort key are plain filters over the file, which is fine at the size a single developer machine
holds.

## Claims

`claim(key, owner)` is the exactly-once gate shared by both implementations: it returns `True` only
for the first owner that ever claimed that key. DynamoDB enforces it with a conditional
`PutItem` on `attribute_not_exists(pk)`, treating `ConditionalCheckFailedException` as a lost race
rather than an error; locally the same guarantee comes from a `threading.Lock` around a checked-then
-written `claims.json`. Callers therefore never need a lock of their own — a duplicate Telegram
update or a re-fired schedule simply loses the claim and stops.
