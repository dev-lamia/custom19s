## v0.51 — automatic Classic USERPIC and quieter duplicate-attendance diagnostics

For **approved Classic Attendance PUSH** devices (`att`), Odoo automatically
advertises `TransFlag=1111000001` rather than `1111000000`. There is **no
checkbox**: the old v0.50 opt-in field was removed from the model and views.
If upgrading an existing v0.50 database, its old DB column is intentionally
not dropped (no destructive migration). Security PUSH (`acc`) and unapproved
terminals are unchanged. A documented Classic `CHECK` command may tell the
terminal to re-read options without physically disconnecting it; this can
also lead to repeat uploads according to the terminal's timestamp state.
A documented Classic `LOG` command requests transmission of newly available
data. Neither command guarantees retransmission of older profile JPEGs.

The photo receiver stores bounded JPEG USERPIC records in device-specific
`zk.device.user.image_1920` with no biometric/identity remapping. Normal
accepted ATTLOG uploads and existing biometric-HR conflicts no longer produce
routine WARNING noise. An unknown-provenance open HR attendance continues to
block unsafe auto-closure and is logged as a clear manual-review WARNING,
not an ERROR traceback; raw punches remain intact. Unexpected exceptions
still log full exceptions. Long PostgreSQL timeouts need separate database
lock diagnostics: they are not claimed to be fixed by this change.

**Important:** A face template is not necessarily a display portrait; PIN
1002 using facial recognition does not establish that 700 has a USERPIC JPEG.
The documented Classic ADMS QUERY list has no tested historical USERPIC pull
command for this firmware. Do not use `DATA DELETE USERPIC` (destructive).

### v0.49 Raw attendance device names

Attendance Analysis now displays **Device User Name** immediately after **Employee**. It shows the source terminal's current cached name for the **exact device + PIN**, even on an unmapped raw punch. Blank device names remain blank; existing attendance and employee links are not modified. This is a computed display label and is not a stored historical name. Classic ADMS (`att`) devices can now upload `USERPIC` through `OPERLOG` (passive reception), but device 700 has **no verified on-demand photo-pull command** in this module. The Security PUSH (`acc`) photo query is not used on Classic devices.

# TAM Biometric Device Integration

## Security PUSH user photos and device access (v0.48)

Security PUSH Access Control terminals may upload **user profile pictures** with `table=tabledata&tablename=userpic&count=N`. The module now validates and stores their JPG/base64 payloads against the exact **device + PIN** into the existing Device User image. A successful persisted upload returns `userpic=N`; malformed, oversized or unsupported image packets are rejected, not silently marked successful. The photo is not an attendance event, and it is not a fingerprint/face template. Device 389's repeated `userpic` HTTP 400 responses should cease after it next sends a valid image to this updated receiver.

**Transferred users:** v0.47 added a necessary `userauthorize` stage to the Security PUSH profile workflow, and the explicit authorization-only repair stage remains. This is not proof that device 401's "Invalid Time" is fixed. Confirm the intended Time Period/Door and the **physical device clock** before using the repair stage on PIN 2005 or 9001, then test an actual scan. Keep 394/401 in `acc` mode; do **not** change to `att` to bypass access-control rejection. Switching terminal device type can clear local user/biometric data.

## Version diagnostics and transferred-user access (v0.47)

`pushver` from the Classic ADMS handshake (for example `2.4.1`) is **not** proof of the installed PUSH software release (for example `Ver 3.1.6S-20260115`). Device Technical Details now display them separately. An approved Classic ADMS device has **Request Version Info** which queues INFO, GET OPTION FROM FWVersion and GET OPTION FROM PushVersion. Versions update only when a validated version identifier is actually reported in OPTIONS/INFO/DEVICECMD/registration. Return=0 by itself does not update versions. An older firmware may not send a version value even after acknowledging the request. Never change `device_type=att` to `acc` just because the installed PUSH release matches another terminal.

For Security PUSH transfers, user profile + fingerprint/face template acceptance does not grant a valid *door/time-period* authorization. New profiles require the manager to select the destination's approved Time Period ID and Door ID. The wizard queues profile, authorization and verification in dependency order. Existing transferred users can use **Repair existing user — authorize access only** (after refreshing the destination's user inventory); this does not resend biometric templates or change PIN mappings. Test PIN 2005/9001 in person after confirming both target clock/time zone and the destination's time rules.

- Technical name: `tam_hr_zk_attendance`
- Odoo version: 19.0
- Module version: `19.0.0.0.51`

## Purpose

This module connects supported ZKTeco biometric/access-control terminals to Odoo through device-initiated ADMS/PUSH requests. It keeps raw device punches as audit evidence, maps each **physical device + PIN** to an employee, derives biometric `hr.attendance`, and can queue supported user/template operations for terminals that poll Odoo for commands.

Supported protocol flows include:

- classic attendance PUSH (`ATTLOG`);
- Security PUSH 3.1.2 registration/configuration (`/iclock/registry`, `/iclock/push`);
- realtime verification events (`RTLOG`);
- asynchronous command delivery through `/iclock/getrequest` and `/iclock/devicecmd`;
- `USER` and verified fingerprint (`FP`) cache/update/transfer through `OPERLOG`.

## ADMS device registration

A newly discovered ADMS terminal is automatically created in the database main company, but remains **unapproved** and has **Receive Attendance** disabled. A Biometric Manager must set its final Company, Location, and Timezone, then approve it before enabling attendance or device commands.

## Current Odoo navigation

```text
Biometric Attendance
├── Dashboard
├── Devices
├── Device Users          (Biometric Manager)
├── Attendance Logs
└── Command History       (Biometric Manager)
```

The normal Employee form intentionally has no biometric-device action button; the active inherited view only shows the separate compatibility Employee ID after Job Title. Device identity and employee mapping are managed from **Device Users** so the same numeric PIN can safely belong to different employees on different terminals.

## Identity rule

A PIN is never global.

```text
Device A + PIN 2 → Employee A
Device B + PIN 2 → Employee B
```

Incoming attendance is resolved only through the matching `zk.device.user` for the exact physical device and PIN. The Employee ID field is retained for compatible business reports and integrations; it is not authoritative for biometric identity, which always uses Device + PIN.

## Operational workflow

1. Open **Biometric Attendance → Devices** and verify the detected terminal.
2. Set the friendly Device Name, Company, Location, physical Timezone, and **Receive Attendance** setting.
3. Approve the device before pulling or sending user/biometric information.
4. Choose **Pull Users and Templates**. The request is queued and delivered when the terminal next polls Odoo.
5. Open **Device Users** and map the exact device/PIN to the correct employee.
6. Use **Map Past Punches** when the selected employee is already correct and only old raw punches from this device + Biometric ID are unmapped. Use **Fix Wrong Employee** only when that device + Biometric ID was assigned to the wrong employee. Choose the **Correct Employee** from the company-filtered public employee directory; there is no employee-creation option in the correction tool. Create a missing employee properly in the Employees application first. The selected date range limits which raw punches are moved, while the current Odoo device/PIN employee mapping is also updated; the physical terminal is not changed.
7. Use **Update Device User** to update the same terminal/PIN. Use **Transfer to Device** only for another approved terminal. A Biometric Manager can choose a target in another company assigned to their user account, even when that company is not active. After verified target enrollment, its device/PIN automatically inherits the source employee mapping without overwriting conflicts.
8. Use **Command History** to monitor queued, sent, completed, failed, or waiting-too-long requests.

## Attendance pull dates

The **Pull Attendance** wizard separates the requested business period from the device request size:

- **From Date / To Date** = the full period to retrieve.
- **Device Request Range (Days)** = the maximum number of days included in each queued device request.

For example, 1–31 October with a request range of 7 is queued as several smaller requests without changing the selected 1–31 October period.

## Data safety and duplicate handling

Raw punch creation and biometric `hr.attendance` synchronization stay inside the normal Odoo HTTP transaction. Savepoints isolate individual duplicate collisions and derived-attendance failures; the controller does **not** manually commit a separate raw-punch transaction.

New raw events receive a deterministic `source_event_key` based on physical device, PIN, exact UTC timestamp, and punch type. A nullable unique constraint protects new concurrent/retried events, while an explicit legacy-column lookup prevents retransmission of historical rows whose event key is intentionally empty. Existing historical raw rows are not globally rewritten or deduplicated during upgrade. **Repeated imports** leave matching punches untouched, but can fill an empty employee mapping from the verified Device + PIN mapping or a missing verification method. Existing mappings are never overwritten by a repeat import. New physical events are inserted once. If an existing non-biometric/manual HR attendance conflicts on a day, the raw punch is kept and Odoo HR attendance is not duplicated.

Raw Attendance Analysis is read-only from this module and continues to display punch seconds.

## Biometric template support

The module maintains a private cache for Classic `FP`, legacy Classic `FACE`, and unified visible-light face `BIODATA Type=9` (plus the existing Security PUSH biometric cache). As of version **19.0.0.0.61**, compatible ATT-to-ATT Type 9 and native Classic FACE templates can be sent as separate documented command formats; a dedicated **Pull Face Templates (ATT)** action requests native Type 9 data. Palms and unknown/converted template formats remain unsupported. Device acknowledgements cannot replace physical enrollment/authentication tests. See `docs/CLASSIC_FACE_TRANSFER_61.md`.

Template values are not shown in ordinary Odoo views and are not written to normal application logs.

## UI maintenance

The module uses:

- device-first Kanban/list/form navigation;
- a profile-style Device User Kanban/form;
- custom SVG artwork for the dashboard/device UI;
- chatter on Device configuration;
- read-only Attendance Analysis;
- manager-only Device User and Command History workflows.

View XML is intentionally formatted and commented so later changes can be reviewed without working through compressed one-line architecture definitions.

## Documentation

- [Configuration](docs/CONFIGURATION.md)
- [Workflow](docs/WORKFLOW.md)
- [Technical documentation](docs/TECHNICAL.md)
- [Security](docs/SECURITY.md)
- [Manual test cases](docs/TEST_CASES.md)
- [Upgrade safety](docs/UPGRADE_SAFETY.md)
- [Changelog](CHANGELOG.md)


### Odoo 19 access-control warning maintenance (19.0.0.0.32)

Private biometric template/fingerprint caches and the retired sync compatibility wizard
now have explicit model ACL declarations assigned **only** to the unassigned
`group_biometric_protocol_internal` role. Do **not** assign that internal role
to staff: the biometric cache stores sensitive template bytes. Standard users
and Biometric Managers cannot read the caches through ordinary RPC; server-side
ADMS ingestion/authorized synchronization still uses narrowly scoped `sudo()`.
This module uses `models.Constraint`, not legacy `_sql_constraints`. A generic
registry-failure line cannot be diagnosed without its full traceback.


### Missed checkout handling (v19.0.0.0.35)

For a **completed device-local day** containing only an IN scan, live sync or confirmed rebuilding closes the proven biometric attendance at its original check-in (worked hours: **0.00**); the current day remains open. Also, when a mapped employee has a **proven biometric** open attendance from a previous device-local day, an incoming or rebuilt next-day check-in closes that older record at its **original check-in timestamp** (worked hours: **0.00**). Manual/unverified records are never changed. Genuine same-day punches replace zero-hour placeholders if later received. Both live ADMS processing and the historical rebuild wizard use the same helper. This is not a scheduled job and upgrading by itself does not change existing attendances. `out_mode` is a native optional field: use `auto_check_out` if the selection exists; otherwise use `manual` if supported. No new attendance fields are added.

### Access-control Security PUSH terminals

Registered `DeviceType=acc` devices now use Security PUSH `user` and typed `biodata` pull queries with a `/iclock/querydata` response handler. For details and staging checks, see `docs/TECHNICAL.md` and `docs/UPGRADE_SAFETY.md`. Legacy ADMS pulls remain unchanged. Security PUSH profile and biometric update commands are supported as a dependent single-click workflow; physical-terminal write compatibility must be confirmed with one test employee before biometric transfers.

### Security PUSH one-click transfer (v19.0.0.0.53)

Open **Device Users → a source user → Transfer to Device**. Select an approved target, review its fresh user inventory (within 24 hours), confirm the destination's access Group/Time Period/Door policy, tick the single identity-and-access-policy checkbox, and press **Transfer User**. This queues **all available data in a dependent sequence**: normal user profile for a new PIN, destination authorization, exact PIN user verification, available compatible Type 1 fingerprints and Type 9 face templates, and optional cached JPEG profile picture. The wizard defaults Group=1, Time Period=1 and Door=1, **but these are locally configured destination IDs**; a manager must confirm these settings because Period 1 may allow unrestricted access. Existing verified normal users with the same PIN/name/employee are handled without recreating their profile. Different identities/admin users are blocked. Source templates must have complete native metadata and match device algorithms; failures stop submission rather than leaving a half-queued transfer. Missing source templates or pictures are skipped, not fabricated. The ACK of each command gates the next; a successful ACK never replaces a real fingerprint/face/door test. Source admin rights, cards and passwords are not transferred. Use specialist authorization, face or photo repair only when needed, and keep Classic ADMS-to-Classic transfers separate.

**Update Device User:** The form button now queues `DATA UPDATE user` for approved `acc` devices with only PIN and validated Name, rather than the blocked Classic `DATA USER` format. This intentionally does not send access group, privilege, password or card updates. Test on a staging device, since firmware-specific partial-update support has not been verified on the physical terminal. The Classic device path is unchanged.

### Security PUSH transfer (v19.0.0.0.37)

Only Biometric Managers may transfer enrollment data. For SpeedFace-to-SpeedFace transfers, use the Device User transfer wizard and start with **Step 1 — Test one employee profile**. This sends one `DATA UPDATE user` command with a normal (privilege-0) role. After the target accepts it, **pull users on the target**, physically verify that the name and PIN are correct, and only then select **Step 2 — Send biometrics after user verification**. The second stage requires a fresh source pull (to capture precise biometric metadata), matching supported algorithms, non-duress templates, and a matching normal user on the target. The source profile may be an administrator: it is always enrolled as a **normal** destination user (Privilege=0). Administrator privileges, passwords, card assignments and door access policies are deliberately excluded. Any promotion to administrator must be performed through authorized local controls on the physical target terminal. No bulk Security PUSH push is enabled.


### First employee on an empty Security PUSH target (v19.0.0.0.38)

An empty destination is expected: click **Pull Users and Templates** on the *target* once to establish a fresh user inventory. If the terminal returns `0`, the successful completed `DATA QUERY tablename=user,fielddesc=*,filter=*` command serves as proof even when no `/iclock/querydata` body is sent and `last_user_sync_at` is blank. You do **not** need to enroll anyone locally on that target before transferring the first profile. Open **Device Users → source user → Transfer to Device**, choose the target, start with **Step 1 — Test one employee profile**, and confirm. After a successful device acknowledgment, re-pull target users to verify the new PIN and name before transferring templates. Bulk transfers and remote administrator-role replication are excluded; an administrator on the source may be transferred as a normal user.

Transfer wizards are pre-created as transient Odoo records so their Transfer User action does not raise an empty-recordset `Expected singleton` error. Close and reopen any wizard created before the upgrade.

### Security PUSH biometric negotiation (19.0.0.0.39)

For registered `DeviceType=acc` terminals, the `/iclock/push` server response now
advertises `MultiBioDataSupport` (Types 1 and 9 when the device supports them)
and an all-zero `MultiBioPhotoSupport` mask. Odoo supports unified BIODATA
records here but does **not** implement the distinct BIOPHOTO table, so it
must not claim photo support. The server masks unimplemented biometric types
instead of enabling every type reported by the device.

This is a handshake change, not a data migration. The device must reconnect
and fetch `/iclock/push` again before its effective negotiated capabilities
can change. Do not retry failed biometric writes automatically or interpret
`Return=-18` as proof of malformed data; investigate firmware/storage responses
if the error persists after receiving new config. Legacy ADMS remains unchanged.


### Cross-company employee attendance mapping (v19.0.0.0.42)

Biometric Managers with access to **both** the device's company and the employee's employing company can link a device/PIN to an employee in a different company. The Device User form and Fix Wrong Employee wizard filter their employee selectors to the manager's permitted companies. Device ownership, company record rules, HR employee company, physical terminal data and biometric transfer rules do not change. Cross-company links take effect for future matched attendance; use the date-scoped mapping/correction wizard for history. See `docs/SECURITY.md` and `docs/TEST_CASES.md`.

## Wizard completion and automatic mapping on verified transfer

Dated Attendance Pull, historical mapping/correction and Device User Transfer dialogs now show the completion notification and close automatically. Queueing does not mean the target device has executed the command: check **Command History** for progress.

A mapped employee now follows a successfully **verified** cross-device profile transfer. Odoo stores the explicit source mapping on the queued profile command, sends a dependent target user query after the successful profile acknowledgment, and attaches the mapped employee when the destination reports the same normal user (exact target device, PIN and name). It does not create a guessed user on queue and will not overwrite another employee's target mapping. Security PUSH biometrics still require the separate verified second stage. See [Workflow](docs/WORKFLOW.md) and [Security](docs/SECURITY.md).

### Registry field-label maintenance (v19.0.0.0.54)

The private Device User employee mapping (`employee_id`) and public-directory proxy (`employee_public_id`) retain separate field labels in model metadata to avoid Odoo 19 duplicate-label warnings. Device User views still display **Mapped Employee**; the historical correction wizard still displays **Current Employee**. No employee, biometric, attendance, or Security PUSH transfer data is changed. Other modules' Odoo 19 deprecations and field warnings are deliberately out of scope.

### Security PUSH batch transfer and photo pull (v0.55)

Device form: **Pull Profile Pictures** queues a userpic read request for that
terminal. Check the Device Users picture and received-record count, not merely
Return=-1. Device Users list: select rows from one source device and use the
**Transfer Selected Users** Action menu. The modal supports complete transfer
or photo-only repair for existing matching users, with a maximum of 25 per
batch. See `docs/TRANSFER_FACE_AND_PHOTOS.md`.


### Protocol-aware transfer (v19.0.0.0.58)

Select up to 25 users from **one** approved source device and choose an approved
destination using **Action → Transfer Selected Users**. The wizard supports
Security PUSH (`acc`) → Security PUSH and Classic/legacy Attendance ADMS
(`att` or a legacy handshake without DeviceType) → Classic/legacy ADMS.
Mixed-protocol biometric template transfers remain blocked: the cache cannot
translate face/fingerprint algorithms. All users are preflighted before queuing
any writes. On Classic terminals, verified cached USER and FP data can be
sent using the existing Classic commands, and separately stored profile JPEGs
may be written using the documented Classic USERPIC command. This photo write
is **firmware-dependent** and has not been verified on all devices. Do not
confuse a facial-recognition template with a profile photo. Classic face write support is now implemented for correctly cached native
legacy FACE or unified Type 9 templates, but real-device compatibility and
successful recognition still require physical verification; no face enrollment
can be recreated from a JPEG.

The **Pull Profile Pictures** action is also available on approved Classic
terminals, but unlike Security PUSH's query it only refreshes the upload
options and requests pending records; it is **not** a historical USERPIC pull.
Do not repeatedly issue it when a terminal has no USERPIC to send.

Before deployment test with one user in staging, inspect the command history
and confirm physical fingerprint/face verification and photos on the target.
No device-type switch is required or recommended.
