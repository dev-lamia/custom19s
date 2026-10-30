## v0.53 — Single-click Security PUSH command dependencies

The new default `transfer_mode=full` on the pre-created transient queues a complete, validated user transfer from one approved `acc` device to another. Input access IDs default to Group 1, Time Period 1, Door 1 but the manager must confirm them on submission. There is one confirmation checkbox; the old two-stage profile/biometric selections are not offered in the wizard. Legacy helper stages remain callable for compatibility. The dependency chain is: new normal user profile when needed; userauthorize; targeted user query; fingerprint Type 1 then face Type 9 templates; source cached userpic if available. Existing normal users with matching PIN, name and employee are not recreated. The wizard requires fresh target user inventory for collision safety. Before queueing, it checks source data integrity, algorithm compatibility and JPEG limits. Missing photo/template means the corresponding stage is skipped. A failed ACK cancels later dependent commands. An ACK is not physical verification. `Update Device User` on `acc` now uses a name-only `DATA UPDATE user` command with PIN and Name; review terminal response for firmware partial-update compatibility. No device mode, historical attendance or UTC timestamp changes.

## v0.52 Security PUSH transfer repair

Existing profiles can receive a dedicated face (Type 9) template-only update or separate Security PUSH userpic JPEG update without resending fingerprints/access permissions. Both require fresh target inventory and exact matching PIN/name, with source/target photo and face cache indicators in the wizard. See `TRANSFER_FACE_AND_PHOTOS.md`. No migration/schema change. Device-reported command ACK is not physical-verification proof.

## v0.51 — Classic USERPIC, command refresh, and HR warning classification

- `controllers/zk_push.py`: `_classic_trans_flag()` advertises `1111000001` automatically only on approved `att` devices. `classic_userpic_upload` model/UI Boolean from v0.50 has been removed. The tenth digit is `UserPic`. No photo change to Security PUSH (`acc`). Device refresh via documented queued `CHECK`, new-data transmission via queued `LOG`; **not** a historical user-photo query.
- `OPERLOG USERPIC` is a separate JPEG record, not a face biometric template. The v0.50 savepoint, JPEG validation, and no-sensitive-content logging remain intact. A PIN-specific `DATA QUERY USERINFO` can only complete from the matching USER PIN.
- `controllers/zk_push.py`: routine accepted ATTLOG/RTLOG and command-delivery messages use INFO (unmapped counts remain WARNING). HR reconciliation conflicts log once in HR and do not emit a duplicate WARNING from the controller. Expected `ValidationError` in HR sync is logged as manual-review WARNING without a full exception traceback, preserving raw punches; unexpected exceptions still use `_logger.exception`.
- `models/zk_hardening.py`: existing proven biometric attendance conflict is classified as INFO, but actual unverified/manual history collision is still WARNING. Never auto-close unknown-provenance HR attendance.
- PostgreSQL 990-second backend timeout remains a separate lock/performance investigation; no claim of repair here.

# Technical Documentation

## v0.48 userpic upload handler

- `controllers/security_push_codec.py`: `SUPPORTED_TABLES` now includes `userpic` (user profile JPEG, **not** biometric `biophoto`); `parse_tabledata` allows permitted line wraps for `Content=` only on `userpic`; `decode_userpic_record` validates PIN, JPG filename, exact encoded length, 2 MiB decoded photo cap, JPEG integrity and 8-million-pixel cap. Pillow re-encodes the JPEG without EXIF metadata.
- `controllers/zk_push.py`: both unsolicited `/iclock/cdata?table=tabledata` and supported query packets use the same atomic tabledata path, returning `userpic=<stored records>` only after persistence. The existing 8 MiB package cap and `count` check apply. A photo preceding its USER profile may create an **unmapped device-user cache stub** solely on that same approved `acc` device. It cannot create or map an employee, transfer privileges, change attendance, or overwrite another device's identical PIN.
- `zk.device.user.image_1920` is reused; no schema migration/new stored fields needed. Images stay on Kanban/form, not the Device Users list. Do not print images, filenames or raw base64 to diagnostics. Invalid payloads get 400; storage failures get 500 for retry. Package processing stays atomic under an ORM savepoint.
- Biometric capabilities advertised in `/iclock/push` are unchanged. `userpic` is not a `biodata` or `biophoto` template; adding user photos does not implement comparison/attendance photo uploads.

## v0.47 safe device metadata parsing

Classic `GET /iclock/cdata?options=all&pushver=X&DeviceType=att` saves `adms_protocol_version=X` and leaves installed `push_version` unchanged. The new `controllers/device_metadata.py` recognizes only FWVersion/FirmVer/FirmwareVersion and PushVersion from approved device OPTIONS, Security registry or the completion of an explicit INFO/GET OPTION command correlated with its sent command ID. It accepts a strict printable release-identifier format; command response summary and device metadata never retain arbitrary `Content`, biometric data, credentials or other configuration fields. Multi-line INFO replies are interpreted only when exactly one valid command ID exists in the request. Classic handshake missing fields do not clear stored metadata. `metadata_source` and `last_metadata_at` record an actual version observation, not a mere successful command ACK. `push_version` represents only an installed PushVersion when positively reported after upgrade.

RTLOG event 22/23 is not an attendance punch. On a denied event, the controller logs sanitized event counts and estimates timezone/terminal clock drift only for near-current events; it never stores a fake attendance or logs a full rejected payload.

Security PUSH transfer stages: profile (explicitly chosen destination group; no StartTime=0/EndTime=0 validity assumptions) → destination-selected `DATA UPDATE userauthorize Pin=...\tAuthorizeTimezoneId=...\tAuthorizeDoorId=...` → user verification query. Authorization-only requires a previously pulled matching normal target user. The module intentionally does not synchronize door/time-rule tables or assume that time period 1 is permissive. A successful ACK is not proof of effective access; terminal policy, calendar/holiday settings and the physical clock remain authoritative.

## Current module structure

```text
tam_hr_zk_attendance/
├── controllers/
│   ├── zk_push.py                    # Public ADMS/PUSH endpoints and punch ingestion
│   └── security_push_codec.py       # Strict Security PUSH user/biometric parsing
├── models/
│   ├── hr_employee.py                # Deprecated employee-PIN compatibility fields only
│   ├── zk_device.py                  # Core device protocol/command behavior
│   ├── zk_hardening.py               # Company, chatter, serial, provenance extensions
│   ├── zk_adms_sync.py               # Device-user/template/command persistence and transfer verification
│   ├── zk_machine_attendance.py      # Raw punch evidence and idempotency key
│   ├── zk_actions.py                 # Device/user operational actions
│   ├── zk_mapping_actions.py         # Opens controlled mapping/correction workflows
│   ├── security_push_transfer.py    # Validated single-click Security PUSH transfer
│   └── zk_dashboard.py               # Company/timezone-aware dashboard metrics/actions
├── wizard/
│   ├── attendance_pull_wizard.py
│   ├── attendance_mapping_wizard.py
│   ├── device_user_transfer_wizard.py
│   └── device_user_sync_wizard.py    # Compatibility-only retired employee-centric model
├── views/
│   ├── dashboard_views.xml
│   ├── zk_device_views.xml
│   ├── device_user_views.xml
│   ├── machine_attendance_views.xml
│   ├── attendance_pull_wizard_views.xml
│   ├── attendance_mapping_wizard_views.xml
│   ├── device_user_transfer_wizard_views.xml
│   ├── hr_employee_views.xml
│   └── biometric_device_attendance_menus.xml
├── security/
├── migrations/
├── static/
├── tests/
└── docs/
```

`hr_employee_views.xml` has an **active** inherited employee form view that displays the editable compatibility `Employee ID` field (`device_user_id`, related to legacy `device_id_num`) after Job Title. It does **not** add the removed biometric action button. This employee identifier is not used for matching biometric punches; device/PIN mapping is managed from Device Users.

## HTTP endpoints

| Endpoint | Methods | Purpose |
| --- | --- | --- |
| `/iclock/cdata` | GET, POST | Handshake and device data (`ATTLOG`, `RTLOG`, `OPERLOG`, etc.). |
| `/iclock/registry` | GET, POST | Security PUSH device registration/capabilities. |
| `/iclock/push` | GET, POST | Security PUSH configuration after registry. |
| `/iclock/getrequest` | GET, POST | Device command polling and queued-command delivery. |
| `/iclock/devicecmd` | GET, POST | Command acknowledgement/result state; positive Security PUSH query return values are record counts. |
| `/iclock/querydata` | POST | Security PUSH query packages, scoped to an approved device and matching command/table. |

## Core models

### `zk.device`

Stores the friendly device name, immutable `serial_number`, company, location, physical timezone, approval/attendance gates, diagnostics, chatter, and ADMS command sequence/status.

The serial number is the protocol identity. The editable `name` is for human-readable display.

### `zk.device.user`

Caches one user for one exact physical device and PIN. Its optional `employee_id` is the authoritative employee mapping for biometric attendance.

The database constraint is:

```text
UNIQUE(device_id, pin)
```

A user cannot be moved to another device and its PIN cannot be changed after creation.

### Private biometric caches

- `zk.device.fingerprint`: verified legacy fingerprint (`FP`) cache used by supported transfer code.
- `zk.device.biometric.template`: extensible typed private cache (`fingerprint`, `face`, `palm`, `other`). Only fingerprint protocol ingestion/transfer is currently verified.

These template models are not exposed through ordinary Odoo menus/views.

### `zk.device.command`

Stores asynchronous ADMS work for one device, including a per-device numeric command ID, safe business operation label, lifecycle state, acknowledgement/result, and attendance-import counters.

Normal UI views intentionally omit the raw `command` text because it can contain sensitive template data.

### `zk.machine.attendance`

Raw biometric punch evidence. Important behavior:

- `employee_id` is optional and derived from exact device + PIN mapping;
- unknown PINs are preserved without creating employees;
- `device_id_num` stores the PIN received from the device;
- `punching_time` is stored in UTC;
- new rows receive a deterministic `source_event_key`;
- historical rows may intentionally have no event key.

### `hr.attendance` biometric provenance

Biometric-derived attendance is marked with:

- `biometric_generated`;
- `biometric_device_id`;
- `biometric_pin`.

This provenance allows controlled correction to replace only attendance that can be proven to come from the selected device/PIN. Manual or uncertain historical attendance is not automatically deleted.

## Device identity and employee resolution

Incoming PIN resolution is strictly:

```text
ADMS serial
    ↓
zk.device
    ↓ exact device + PIN
zk.device.user
    ↓
employee_id
```

There is no employee-wide PIN fallback. The legacy `hr.employee.device_id_num` column is compatibility data only.

## ATTLOG parsing

Classic positional rows are supported:

```text
PIN<TAB>YYYY-MM-DD HH:MM:SS<TAB>Status<TAB>VerifyMode...
```

Key/value ATTLOG rows from newer firmware are also accepted when PIN and time are present.

The device-local timestamp is localized using `zk.device.tz` and converted to UTC for storage.

## Security PUSH RTLOG parsing

Typical input:

```text
time=2026-10-06 08:30:00<TAB>pin=1001<TAB>event=0<TAB>inoutstatus=0<TAB>verifytype=15...
```

The parser requires a non-zero PIN and timestamp, rejects unsupported alarm/error events, stores `inoutstatus` as the raw punch value, and stores `verifytype` as the verification method where known.

## Transaction boundaries

The controller does **not** manually commit raw punches or open a second registry cursor.

Current behavior:

1. Parse each payload row.
2. Check the historical event columns for an existing exact event.
3. Create each new raw punch inside a savepoint.
4. Collect the mapped employee/local-day combinations touched by successfully accepted events.
5. Rebuild/update only those biometric-derived attendance days inside separate savepoints.
6. Catch/log derived attendance failures so one employee/day failure does not abort processing of other touched days.
7. Let the normal Odoo HTTP request transaction commit or roll back as a whole.

This avoids independent commits that can conflict with the request transaction.

## Duplicate/idempotency protection

New rows use:

```text
source_event_key = SHA256(device_id | PIN | exact UTC timestamp | punch_type)
```

A nullable unique constraint on `source_event_key` protects new concurrent/retried events. Before create, the controller also checks:

```text
device_id + device_id_num + punching_time + punch_type
```

so a retransmission does not recreate an older historical row whose event key is intentionally null.

The module does not globally deduplicate/rewrite existing historical rows during current upgrades. Incoming matches can be enriched only where mapping or verification information is missing; a previously mapped employee is never silently changed by a repeated pull. Unique constraints on event hashes guard concurrent workers.

## Daily biometric attendance derivation

For the exact mapped employee + device + PIN + local date:

- the earliest raw punch is used as `check_in`;
- an explicit final OUT punch or a final punch at least five minutes after the earliest becomes/extends `check_out`; repeated IN scans within five minutes are not an OUT;
- single IN scans on a **completed** local day are finalized with `check_out=check_in` for zero hours, while the current local day remains open;
- an already existing unrelated HR attendance on that local date blocks automatic creation/update and is preserved for review;
- derived records are tagged with biometric provenance.

The raw punch label remains evidence/analysis; derivation uses the first punch and a sufficiently separated final punch or explicit checkout. For shifts crossing midnight or overlapping manual attendance, an HR operator must review the evidence; imported raw punches are never discarded.

## ADMS command lifecycle

```text
Odoo queues command
       ↓
Device polls /iclock/getrequest
       ↓
Odoo returns C:<id>:<command>
       ↓
Device executes command
       ↓
Device posts acknowledgement to /iclock/devicecmd
       ↓
Query payload may arrive separately through OPERLOG/ATTLOG
```

Commands are asynchronous. Query success should be validated against returned user/template/attendance payload, not only an acknowledgement code.

## User/template synchronization

`USER` records are upserted into `zk.device.user` by exact device + PIN and preserve an existing explicit employee mapping.

Known `FP` records are cached privately by device + PIN + finger slot and can be queued to another approved device. The generic typed cache exists for future protocol-backed biometric types, but face/palm/other command generation is intentionally not enabled without observed payloads and physical-device verification.

## Historical mapping and correction

`attendance_mapping_wizard.py` supports two separate concepts:

- mapping previously unmapped raw punches to the Device User's mapped employee;
- correcting an already-wrong device/PIN assignment for a selected local-device date range.

The wizard view loads `device_user_id` invisibly, allowing Odoo to initialize the related Device, PIN and Company fields from `default_device_user_id` when the transient form opens. Correction selects **existing** `hr.employee.public` records via a permitted-companies-filtered, creation-disabled Many2one field, so Biometric Managers do not need broad private `hr.employee` ACLs. On submission the service re-checks device-user write access, device-company membership, and public employee visibility for the employee's **own allowed company** before resolving the private employee with scoped server-side elevation. On the Device User form, `employee_public_id` is a computed/inverse public employee selector backed by the unchanged private `employee_id` mapping; `eligible_employee_company_ids` drives its domain and picker context; server-side `create`/`write` guards check both companies and public-directory visibility. Odoo's implicit employee `check_company` is disabled only on `zk.device.user.employee_id` and `zk.machine.attendance.employee_id`: device ownership and model record rules remain unchanged. No `hr.employee` is created. Missing employee, same target, unauthorized company, bad dates, and zero matching punches raise validation errors before writes.

Correction updates the Odoo Device User's mapping and only the raw punches from the exact selected device/PIN/date range. The physical device is unchanged. When attendance correction is selected, only biometric-derived `hr.attendance` carrying matching provenance is automatically removed/rebuilt; unproven attendance stays for manual review.

## Views and maintainability

XML views are formatted across multiple lines and include maintenance comments around major records/actions. Keep future changes in that style; do not compress entire `record` or `arch` definitions onto a single line.


### Missed biometric checkout / native checkout-mode compatibility (v19.0.0.0.35)

`hr.attendance._zk_close_previous_open_attendance(employee_id, next_check_in_utc, device_timezone)` is called by a shared `hr.attendance._zk_sync_local_day` method used in live PUSH and the historical mapping wizard **before** another day's attendance is inserted. Only an older local-day open record marked `biometric_generated` with a source device and PIN is eligible. For an eligible record, checkout is set to its own check-in; Odoo computes zero worked hours. The scan is employee-scoped across devices, since the next day can start at a different terminal. Manual and unidentified records are never auto-closed; they produce an actionable validation message on rebuild and a logged, savepoint-isolated failure in live synchronization while retaining the raw punch.

The existing `out_mode` selection is inspected dynamically using `get_values(env)`. Select `auto_check_out` if supported, otherwise `manual`, otherwise do not set `out_mode`. No custom Odoo fields, historical cleanup or upgrade-time mutation. Day batches and rebuild dates are sorted ascending; device-local day boundaries are converted to UTC for the search.

Explicit device OUT punches (`1`, `5`) are not triggers for the missed-checkout rule; code `3` is **Break In**, not Check Out. The current first/last-day algorithm still uses elapsed time when determining whether a final punch is a valid checkout. For genuine additional punches on an earlier day, the existing derived record's checkout is updated and its native `out_mode` is set to `manual` when that value is supported. Unresolved overnight shifts with explicit OUT punches may require manual review because the module's existing daily first/last pairing does not pair shifts across midnight.

## Security PUSH user and template pull (v19.0.0.0.36)

For registered `DeviceType=acc` terminals, **Pull Users and Templates** queues three read-only device queries: `user`, `biodata Type=1` (fingerprints), and `biodata Type=9` (visible-light face). Each runs as a separate command, delivered when the device polls `/iclock/getrequest`. All four legacy ADMS devices continue to receive `DATA QUERY USERINFO`.

`/iclock/querydata` accepts `type=tabledata`, `SN`, `cmdid`, `tablename`, `count`, `packcnt`, and `packidx` and returns `tablename=number_of_records` after persistence. `cmdid` and `tablename` must match an existing sent/done query of the same approved device. Retried pages are idempotent by device/PIN and device/PIN/type/slot. Response bodies are limited in size and are never written to log lines. A final successful page can complete a query if the device does not send `/iclock/devicecmd` confirmation. Nonnegative query return values are success; errors such as `-629` remain failed. Security PUSH unsolicited `table=tabledata` user and unified-biometric records use the same private parser.

The generic cache is **not** an interoperability conversion service. `biodata` templates are stored privately as device-native base64; no automatic export to ADMS fingerprint `FP` records occurs. Current legacy `DATA USER`/`DATA FP` upload actions are blocked for access-control devices. Biometric face/fingerprint transfer across device firmware/algorithms requires separate verified Security PUSH upload support and physical-device enrollment testing.

### Security PUSH user writes (v19.0.0.0.37)

`DATA UPDATE user` transfers only a normal user's PIN and display name (no credentials, cards, or authorization). `DATA UPDATE biodata` is a separate manually confirmed stage, using precisely cached slot metadata and validated base64. Metadata from old v36 pulls is insufficient: source re-pull is required. Source and target must match `MultiBioDataSupport` and `MultiBioVersion` for Type 1 / Type 9. Odoo command IDs allocate under `FOR UPDATE` lock on the device row, reconciling the counter with `MAX(command_id)`; optional `depends_on_id` enforces successful previous ACK before delivering a later template command. The command field is group-restricted.

As of v19.0.0.0.41, the `biodata` table name stays lower-case while its parameter names use canonical protocol casing: `Pin`, `No`, `Index`, `Valid`, `Duress`, `Type`, `MajorVer`, `MinorVer`, `Format`, and `Tmp`.

## Exact historical HR match (v19.0.0.0.44)

`hr.attendance._zk_sync_local_day()` regards an existing overlapping HR record as already represented only if **both** the check-in and derived checkout are identical to the raw day's first/last timestamps (or both checkouts are genuinely unset). It returns `unchanged` without writing provenance, updating worked hours, or raising a conflict warning. If either boundary differs, it returns `conflict` and keeps the existing row. This covers previously imported HR rows with `biometric_generated=False` while maintaining provenance safety.

## Wizard completion and transfer-linked employee mapping (v19.0.0.0.45)

- **Active transient dialogs:** `zk.attendance.pull.wizard.action_queue`, `zk.attendance.mapping.wizard.action_apply/action_correct_raw/action_correct_attendance`, and `zk.device.user.transfer.wizard.action_transfer` return their existing notification with `params.next = {"type": "ir.actions.act_window_close"}`. The toast can be read and the dialog closes. An exception still leaves the modal open. The retired `zk.device.user.sync.wizard` has no UI action.
- **Intent persistence:** new private metadata fields on `zk.device.command`: `transfer_requested_by`, `transfer_source_user_id`, `transfer_employee_id`, `transfer_pin`, `transfer_name`. These are populated **only on an explicitly authorized outgoing profile command**, not on arbitrary inbound user-pull records or biometric-template commands. Upgrading adds empty columns; no old records are classified as transfers.
- **Queue order:** normal-user profile → dependent read-only destination user refresh. Classic ADMS also queues existing fingerprints gated by successful profile acknowledgment. Security PUSH sends biometrics only in a separate explicitly verified stage. Queued profile/verification commands show in Command History; the target must poll and return successful command results/data before it is shown as mapped.
- **Safe auto-link:** on successful profile ACK, check any already-returned destination Device User; on subsequent `USERINFO`/`user` upserts, check the latest successful transfer intent on that **exact target device + PIN**. Confirm unchanged source employee mapping, explicit authorized source, destination, and employee company access, exact stored target name (trim whitespace), and target privilege `0`. Preserve an existing different target employee. The actual write runs under the recorded requesting manager identity with the same explicit company/public-employee guards used in manual mapping, not under the unauthenticated device principal.
- **Failures:** no mapping on a failed/pending profile, mismatched identity, privileged destination, changed source, revoked operator access, or missing target user response; leave unmapped for authorized manual review. A terminal ACK alone does not prove that the target has returned the expected user identity.

This change does **not** infer an employee from a globally repeated PIN and does not retroactively map users from old transfer commands.


## Authorized cross-company transfer and list layout (v19.0.0.0.46)

- **Device Users list:** profile photo (`image_1920`) is no longer a list column. It is still stored and displayed on the Kanban card and Device User form; neither cache data nor images are deleted.
- **Transfer wizard selector:** `permitted_device_company_ids` is computed from `env.user.company_ids` with no sudo. The `target_device_id` domain allows approved terminals from those companies and its field context broadens `allowed_company_ids` only to that assigned-company set (not all database companies). The source device company no longer restricts the destination. Target user-inventory time and cache-status preview fields compute under the same explicitly authorized multi-company context instead of using an active-company-limited related field.
- **Server-side validation:** `zk.device.user._queue_transfer_to_device()` independently requires Biometric Manager role, approval on both terminals, and current user authorization for both source and target device companies. The method widens only the authorized active-company context for device operations; it does not elevate the user to superuser. Security PUSH repeats the two-company authorization check and retains all its inventory, PIN, pending-command and template guards.
- **Deferred employee mapping:** `_zk_apply_transfer_mapping()` permits a different authorized target company but re-checks the original requesting manager’s role, the manager’s current source/target/employee company memberships, ACK success, target identity, normal privilege, freshness and existing-employee conflict safeguards. No implicit global PIN mapping, automatic employee creation or change of device-company ownership.
- This change creates no commands, mappings, device users, or biometric templates on module upgrade. It affects only transfers explicitly started after upgrade. Staging verification is required on Classic ADMS and Security PUSH terminals.

## v0.49 Device User Name field

`zk.machine.attendance.device_user_name` is a non-stored, readonly `fields.Char` computed from the cached `zk.device.user.name` by the exact `(device_id, device_id_num)` key. It batches lookups, uses scoped sudo for the device-user cache (operators can read raw logs but not all Device Users), and returns only a name for a log the caller can already see. It does not link employees or change historical raw evidence, and therefore requires no new SQL column. The rendered name is current cache data, not a punch-time snapshot.

## v0.49 Classic ADMS user-photo upload

The approved-device Classic `OPERLOG` receiver now accepts the Attendance PUSH `USERPIC PIN=...\tFileName=...\tSize=...\tContent=...` record type alongside existing `USER` and `FP`. It uses the existing strict JPEG decoder and device/PIN image cache (including an unmapped profile-only stub when necessary). Photo bytes/filenames are not logged. The receiver acknowledges `OPERLOG` only after the processing transaction succeeds. This is **passive upload support only**: no unverified Classic `DATA QUERY USERPIC` is sent to device 700.
