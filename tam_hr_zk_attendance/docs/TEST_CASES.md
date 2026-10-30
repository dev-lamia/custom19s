## v0.51 — automatic Classic photo flag and attendance diagnostics

- Approved `att` device: options handshake advertises `TransFlag=1111000001` without needing a device checkbox. Unapproved `att` or any `acc` device: `1111000000`; Security PUSH registration/config unchanged.
- A documented queued `CHECK` refreshes Classic options without a physical power/network disconnect on compatible firmware; it must never DELETE or CLEAR data. A documented queued `LOG` may send newly available records. Neither command guarantees a historical photo upload.
- PIN 1002 with only a facial-recognition template and no JPEG user-photo record must **not** be treated as having a cached image.
- Duplicate biometric HR attendance on a day: raw log retained, HR not duplicated, no repeated WARNING for routine biometric conflict. Conflicting manual/unverified HR record: real WARNING remains. Older unverified open HR attendance: HR auto-close blocked, raw punch retained, manual review WARNING, no repeated ERROR traceback. Unexpected failures remain ERROR.
- Regression-test USERPIC validation, device+PIN identity isolation, and exact requested-PIN command acknowledgment as in v0.50 tests.

# Manual Test Cases

## v0.48 photo-upload and access-control regression checks

- On an approved Security PUSH test terminal, upload one valid `userpic` row with matching base64 `size`, JPG `filename` and `content`. Expect `HTTP 200 userpic=1`; confirm the photo appears on **the exact device + PIN** Kanban/form, not another device with the same PIN.
- Repeat the same packet: expect the same one device user (upsert), never a second user, employee or biometric template.
- Send USERPIC before a USER record: expect a non-privileged, unmapped device-user stub; then send USER and verify identity fills in without removing its photo or assigning an unrelated employee.
- Send malformed base64, non-JPG bytes, wrong encoded length, too-large photo, wrong `count`, unknown serial, unapproved device and `att` device packets. Expect explicit rejection, no success ACK and no partial photo writes. Check that logs never include base64, file contents or filenames.
- Check the v0.47 `userauthorize` flow on a staging terminal and separately test PINs 2005/9001 after applying approved target permissions. Verify destination local clock and real scan; never claim the photo change fixes an unrelated `event=23` denial.

## v0.47 regression checklist

- Classic handshake `pushver=2.4.1` never overwrites installed PushVersion; absent DeviceType/PushVersion never clears stored metadata.
- Approved INFO/GET OPTION replies containing valid FWVersion/PushVersion values populate only version fields, source, timestamp and safe summary. ACK Return=0 without values updates nothing. Unsolicited/biometric command bodies never become visible response text.
- Profile transfer without explicit target time-period/door is rejected before queueing anything. With an approved rule, queue profile → authorization → verification, with dependencies and idempotent target mappings; failed authorization cancels dependent verification.
- Existing matching target profile can receive one authorization-only command; a different name, privilege 14, conflicting employee or missing target inventory blocks it. No admin privileges, templates, cards or passwords are copied.
- RTLOG event=23 is never an attendance punch; event 22/23 log diagnostics exclude raw payload and flag recent clock drift.
- Physical-test PIN 2005 and PIN 9001 on 394/401; confirm no `event=23`, correct target clock and locally approved time period. Re-import unchanged raw punches creates no duplicates.

## TC-01 — Existing Classic Device Handshake

Call `/iclock/cdata?SN=TEST&options=all`.

**Expected:** HTTP 200 options response; device row created disabled if new.

## TC-02 — Security PUSH Registry

Simulate:

```text
POST /iclock/registry?SN=ACC001
DeviceType=acc,~DeviceName=SpeedFace,FirmVer=TEST,PushVersion=3.1.2
```

**Expected:** HTTP 200 with `RegistryCode=...`; no 404; device diagnostics populated.

## TC-03 — Security PUSH Configuration

Call `/iclock/push?SN=ACC001` after registry.

**Expected:** HTTP 200 configuration containing `PushProtVer=3.1.2`, `TransTables=User Transaction`, `Realtime=1`, and `SessionID`.

## TC-04 — Device 394 Regression

Reconnect `AJE1261000394`.

**Expected:** `/iclock/registry` becomes 200 instead of 404. The device should proceed to `/iclock/push` and/or normal ongoing PUSH activity rather than repeating only handshake + failing registry.

## TC-05 — Mapped Classic ATTLOG

Map PIN 1001 to an employee and send a valid `ATTLOG` row.

**Expected:** raw row has employee; touched day updates `hr.attendance`.

## TC-06 — Unknown Classic PIN

Send valid `ATTLOG` for an unmapped PIN.

**Expected:** raw row is created with Employee empty; no `Device User ...` employee is created; no standard attendance is created.

## TC-07 — Mapped Security RTLOG

Send:

```text
time=2026-10-06 08:30:00\tpin=1001\tevent=0\tinoutstatus=0\tverifytype=15\tindex=1
```

**Expected:** raw biometric row is stored and standard attendance sync runs for mapped PIN 1001.

## TC-08 — RTLOG Error/Alarm Event

Send an RTLOG row with event in the 20-199 error/alarm range.

**Expected:** it is not stored as attendance.

## TC-09 — Receive Attendance Disabled

Send valid ATTLOG/RTLOG from a device with Receive Attendance off.

**Expected:** request is acknowledged; no raw or standard attendance row is created.

## TC-10 — Bad Timestamp

Send malformed timestamp.

**Expected:** line is skipped and warning logged; batch continues.

## TC-11 — Duplicate

Send the same accepted punch twice.

**Expected:** second create is isolated by savepoint and skipped.

## TC-12 — Raw Storage Failure

In a test database, force an unexpected raw model create error.

**Expected:** endpoint returns HTTP 500 with `ERROR`, not HTTP 200 `OK`.

## TC-13 — HR Attendance Failure Isolation

Force a downstream `hr.attendance` validation failure after raw row creation.

**Expected:** raw row remains; derived day is rolled back/logged.

## TC-14 — Device Diagnostics

Reconnect a Security PUSH device.

**Expected:** Last Seen, Last Registry, Device Type, firmware/push version fields update where supplied.


## TC-15 — Odoo 19 View Upgrade

Upgrade the module on Odoo 19.

**Expected:** `machine_attendance_view_search` loads without `Invalid view` / `ParseError`. The search view uses an attribute-free `<search>` root and `<group>` node, as required by Odoo 19.


## Duplicate/retry regression cases (19.0.0.0.4)

1. POST the exact same ATTLOG payload for the same device 10 times. Exactly one raw row must exist.
2. POST the same PIN/timestamp/punch type from two different physical devices. Two rows must exist.
3. POST two punches for the same PIN on the same device at different seconds. Both rows must exist.
4. Run GETREQUEST and ATTLOG concurrently for one device. Neither request should fail with `SerializationFailure` from `zk_device.last_seen`.
5. Upgrade a database containing historical repeated raw punches. The current upgrade must preserve historical rows; duplicate protection for new events uses the nullable `source_event_key` plus the legacy-column lookup.

## ADMS command regression cases (19.0.0.0.7)

1. Queue `DATA QUERY USERINFO PIN=<pin>`; verify USER and FP records return
   through `OPERLOG` without template content in application logs.
2. Queue `DATA QUERY ATTLOG`; verify batched raw attendance is stored and the
   command remains sent until the terminal acknowledges after transfer.
3. Queue a `DATA USER` display-name update, query the PIN, and verify the name
   returned by the device.
4. Upgrade a database whose historical `address_id` contains `KSA`; the upgrade
   must not attempt an integer conversion or rewrite historical raw rows.

## TC-16 — Device/PIN scoped mapping

Map the same PIN on two different devices to two different employees, then import one event from each device.

**Expected:** each raw event maps only through its own device/PIN pairing; no employee-wide PIN fallback is used.

## TC-17 — Historical mapping modes

Open a mapped Device User and select **Map Past Punches**.

**Expected:** Map-only updates only unmatched raw logs. Rebuild requires From Date, To Date, and confirmation. Correction may replace only biometric-derived `hr.attendance` carrying matching device/PIN provenance; unrelated/manual attendance must remain untouched.

## TC-18 — Unapproved target protection

Attempt a user/template refresh or transfer to an unapproved device.

**Expected:** no sensitive ADMS command is queued. Approving the device is required first.


## TC-19 — Same PIN on different devices

Create/map:

```text
Device A + PIN 2 → Employee A
Device B + PIN 2 → Employee B
```

Send one punch from each device.

**Expected:** each punch maps to its own employee. Neither device uses the deprecated employee-level PIN as a fallback.

## TC-20 — Pull Attendance date/chunk behavior

Open **Pull Attendance**, select 01 Oct through 31 Oct, and leave **Device Request Range (Days)** at 7.

**Expected:** the business dates stay 01 Oct through 31 Oct while several smaller date-range commands are queued.

## TC-21 — Device User form PIN label

Open a Device User form.

**Expected:** the title area shows the text label **Biometric ID** next to the PIN. The old ID-badge icon is not used for the PIN in the form title.

## TC-22 — Read-only Attendance Analysis

Open **Biometric Attendance → Attendance Logs**.

**Expected:** users can search/open raw punches but cannot create, edit, duplicate, or delete raw evidence through this module's views.

## TC-23 — View/documentation maintenance validation

Upgrade the module and inspect all files under `views/`.

**Expected:** XML loads successfully, view architecture is readable/indented rather than compressed into one-line records, and maintenance comments do not alter Odoo behavior.

## TC-24 — Public employee search (no private HR role)

Log in as an internal **Biometric Manager** without HR Officer/HR Administrator rights. Open **Device Users → Fix Wrong Employee**, select an existing Device User with a company you are allowed to access, and search **Correct Employee** by name.

**Expected:** the dropdown returns existing employees in the manager's permitted companies through `hr.employee.public`, without a private `hr.employee` access error or a **Create...** / **Create and Edit...** option. There is no **Create a new employee** choice or free-text new employee name. Employee master data remains managed in Employees.

## TC-25 — Allowed secondary company search

Grant the Biometric Manager access to Companies A and B, keep A as main company, and open a Device User owned by B. Search Correct Employee for a known B employee.

**Expected:** both A and B employees are selectable when the manager is authorized for both companies, including when the employee's company is not the current main company. A crafted request to link an employee in unauthorized Company C is rejected. A user without B in their permitted companies cannot link a B employee; a user without the device's company cannot correct the device.

## TC-26 — Correction validation, no unintended changes

Open Fix Wrong Employee and test missing Correct Employee, the same mapped employee, empty From/To Date, From Date after To Date, and dates with zero matching raw punches.

**Expected:** validation stops processing before modifying the Device User, raw punches, or derived attendance. The date range uses the configured device timezone.

## TC-27 — Explicit raw-only correction

For a verified incorrect PIN mapping with matching raw punches, select another existing employee in an authorized company and **Move raw punches only**.

**Expected:** only raw rows for the exact device + PIN + local date range change Employee, and the current Odoo Device User mapping changes. Punch timestamps/types, punches from other devices, existing `hr.attendance`, and the physical device remain unchanged.

## TC-28 — Confirmed attendance rebuild

Repeat TC-27 using **Move punches and rebuild Odoo attendance**, with confirmation ticked, on a staging database containing attributable biometric attendance and some manual records.

**Expected:** only proven biometric attendance for the former employee, same device and PIN in the date range, is removed. Corrected target biometric attendance is rebuilt, unrelated/manual attendance survives, and HR overlap constraints fail transactionally rather than partially deleting history.


## TC-29 — Odoo 19 missing private-model ACL warning

Upgrade `tam_hr_zk_attendance` to 19.0.0.0.32 in a backed-up staging Odoo 19 database.

**Expected:** no `models ['zk.device.biometric.template', 'zk.device.fingerprint', 'zk.device.user.sync.wizard'] have no access rules` warning attributed to this module. Check all other registry warnings independently; this module defines no `_sql_constraints`.

## TC-30 — Private template and retired-wizard access isolation

Use three different sessions: a normal internal user, a Biometric Operator, and a Biometric Manager. Attempt an RPC read of `zk.device.fingerprint`, `zk.device.biometric.template`, and the deprecated `zk.device.user.sync.wizard` model.

**Expected:** all three sessions receive Access Denied for all three models, including read and search. None of these users is a member of the internal `group_biometric_protocol_internal` service group. No new menu is present for the retired wizard. A real device fingerprint upload and manager-authorized transfer continue to operate through existing scoped server-side processing.


## Next-day missing checkout regression (v19.0.0.0.35)

- 23 Sep one check-in, 24 Sep check-in: both completed days finalize to check_out = check_in, worked_hours = 0. An IN from the current local day remains open until a valid OUT or future-day reconciliation.
- Device sends 24 Sep before 23 Sep in the same ADMS batch: results are still chronological.
- Historical rebuild selecting 24 Sep only, with a previous-day open biometric attendance: previous-day record closes at its own check-in.
- Rebuild rerun: no duplicate attendances or extra writes.
- Genuine second punch later on 23 Sep: replaces zero-hour placeholder; optional native out_mode changes to manual when supported.
- Manual/unverified open attendance: preserved, rebuild reports conflict; raw punches remain available after live sync errors.
- Native `out_mode` variants: `auto_check_out` preferred if defined, otherwise `manual`; no optional field means no out_mode write.
- Explicit overnight checkout punches must not trigger next-day zero-hour closure; require review if current pairing can't represent overnight shifts.

### v19.0.0.0.37 Security PUSH staged transfer

1. Stage the module; verify ordinary-user profile-only push queues `DATA UPDATE user` to a freshly-pulled empty same-company ACC device. Confirm `Return=0`, fresh target pull, physical profile.
2. Ensure a source administrator (privilege 14) can be enrolled only as a *normal* target user (Privilege=0), and that duplicate PIN, another company, unapproved device, invalid PIN, or stale target cache still blocks writes before queueing.
3. Re-pull source biometric data after upgrading. Confirm cached Type 1 / 9 records contain exact `no`, `index`, algorithm and format metadata.
4. After physical user verification, push one sample fingerprint and verify on target before face; check format, metadata and firmware compatibility. A negative ACK must stop later dependent template commands.
5. Check a stale `adms_command_sequence` recovers without a duplicate key. Check concurrent sessions cannot allocate identical command IDs.
6. Confirm raw command text is inaccessible via Biometric Manager RPC; transfer wizard displays counts/status only. Legacy ADMS 4-device behavior and next-day checkout logic must remain unchanged.

## TC-42 — Cross-company device-user mapping (v19.0.0.0.42)

Create Device A in Company A and Employee B in Company B. Grant a **Biometric Manager** access to Companies A and B (no HR Officer rights). Keep Company A as active and link the Device A/PIN to Employee B through the Device User form.

**Expected:** Employee B is available in the picker and mapping saves. The device and its cached/raw punches still belong to Company A; the employee remains in Company B. No device command is queued and no prior attendance changes automatically.

## TC-43 — Cross-company historical correction (v19.0.0.0.42)

Create a wrongly mapped Device A/PIN and a raw punch. With the same manager, choose Company B Employee B from the **Fix Wrong Employee** public directory and run the raw-only workflow for the exact local date.

**Expected:** only that device/PIN and date range are corrected; the employee link points to B, the raw record remains Company A, and any unrelated records are unchanged. The rebuild mode, when explicitly confirmed, creates employee-centered `hr.attendance` with B as the employee's HR company.

## TC-44 — Unauthorized cross-company link denied (v19.0.0.0.42)

Grant a different Biometric Manager only Company A. Attempt to select Company B Employee B in the Device User mapping or send a crafted RPC to the correction wizard.

**Expected:** Company B employee is excluded from the picker and the server rejects the link without modifying the record. Biometric Operators still cannot edit device users; users without access to Company A cannot read/modify Device A; private biometric model access remains unchanged.

## TC-43 — Historical repeat imports and manual-attendance preservation

1. Import the same device + PIN + exact date-range ATTLOG twice. Verify the first import creates raw punches, the second creates **zero** raw rows. Confirm Command History shows duplicate/skipped punches and that existing raw IDs stay unchanged.
2. First import one punch for an employee; import later with an additional OUT. Verify only the new raw event is created and only the proven biometric HR checkout is extended.
3. Repeat an older raw event whose `source_event_key` is `NULL`. Verify it is not duplicated; if its employee mapping was previously empty and is now verified for that device + PIN, only that empty mapping is filled. Previously mapped employee values are never automatically replaced.
4. With pre-existing unmarked `hr.attendance` ID 9016/9024-like entries on July 16, pull again for that date. Verify manual rows, original check-in/out and provenance remain unchanged; raw events persist; no second overlapping HR record is added.
5. Import one IN on a completed day and assert `check_out == check_in` / zero worked hours. Import a later genuine OUT and confirm the same derived record is updated. Two IN scans 60 seconds apart are not a real OUT.
6. Command History must show latest commands first, without changing the FIFO queue for pending device execution.
7. Source admin to normal target: verify a `Privilege=0` user is created, biometric stage requires target inventory and PIN/name verification, and local privilege promotion is separate. Do not queue speculative remote super-admin commands.

## TC — Exact legacy HR match on repeated historical pull (v19.0.0.0.44)

Create an existing HR row with `biometric_generated=False`, then pull the same employee/day punches with the exact same first and last timestamps (e.g. 2026-09-14 05:10:40–14:08:50 and 2026-09-15 05:05:25–14:36:57). Repeat the pull.

**Expected:** Raw rows are idempotent; both HR IDs and their timestamps remain unchanged, the provenance flag stays False, and no HR conflict warning is emitted for those exact matches. Change the last HR checkout by one second and repeat in staging; this must still be logged as a conflict, with no forced modification.

## TC-45A — Modal wizard actions close after success

Open dated **Pull Attendance**, **Map Past Punches**, **Fix Wrong Employee** (both options) and **Transfer to Device** as a Biometric Manager. Complete each action with valid data. Expect success toast then modal close; no second click, stuck dialog or duplicate submission. Invalid inputs still raise a visible Odoo validation error and leave the dialog open for correction. The deprecated sync wizard has no menu/action and is not included.

## TC-45B — Transfer inherits source employee without guessing PIN

Create an approved source and destination in the same company; explicitly link the source Device User to an employee authorized for the requesting manager. Transfer a **normal profile**. Before ACK and target USER query, expect **no** destination Device User or guessed employee. After target ACK success and returned matching normal user (`PIN`, `Name`, `Privilege=0`), expect exactly one new Device User on target mapped to the **same `hr.employee`**; source stays untouched. Repeat the target query and confirm the mapping and row ID remain stable. Test USER arriving before ACK as well as after. Verify classic `USERINFO` and Security PUSH `user` query are queued dependent on profile success.

## TC-45C — Transfer safety rejection cases

Profile ACK failure, stale/unanswered query, wrong destination user name, nonzero privilege, source employee remapped after queue, transfer to another company, requesting manager lacking employee-company access, and an already mapped target PIN must **not** assign or override another employee. No optimistic row on command queue, no biometric sending due only to profile ACK, no global PIN-based fallback. Ensure terminal user responses do not fail HTTP persistence solely due to a revoked mapping permission; deferred mapping is logged instead.


### v19.0.0.0.46 — cross-company transfer regression

- With user allowed in A and B but only A active, open a Device User from A: target picker includes approved device B, excludes unapproved/unauthorized devices, and no photo column appears in Device Users list. The Kanban and form keep images.
- Send profile A → B on Classic ADMS; after profile ACK and target USERINFO, target device/PIN receives the source employee mapping, keeping device company B and original employee company unchanged. Repeat source/target inventory pulls without duplicates.
- Repeat A → B on compatible Security PUSH profile stage; verify fresh inventory prerequisite, dependent verification, normal destination privilege, and eventual mapping.
- Deny spoofed target B to a manager authorized only in A; deny user without Biometric Manager rights even if both companies are assigned. Removing target-company rights after a queued profile must prevent delayed employee mapping.
- Reject an existing different target PIN/employee mapping, unapproved target or incompatible transfer device family; do not copy cards, password, administrator privileges or door authorizations.
