## 19.0.0.0.62 — Classic ADMS Update User command fix (2026-10-27)

- Fix `action_update_device_name` on Classic ATT devices: join command fields
  with actual ASCII tab separators, not literal backslash-t sequences. The old
  format could enroll a malformed biometric PIN instead of renaming its user.
- Reject malformed PINs and control/field-injection characters in all user
  update fields. Keep original privilege, card, password, group and timezone
  on an existing user's **name update**; cross-device enrollment still creates
  destination users as normal (`Pri=0`).
- Require Biometric Manager authorization, device approval, company access,
  and an idle destination for both ATT and ACC name-update operations. Check
  selected users before queueing the first command.
- No database changes, migrations, attendance changes, user/cache deletions,
  or automatic device commands upon upgrade. Existing malformed terminal
  users are not removed automatically.
- Add regressions for Classic command delimiters, privilege preservation,
  malformed biometric PINs/names/credentials, and partial-batch rejection.

## 19.0.0.0.61 — Classic unified face + normal-role bulk transfer

- Classic ADMS full transfer now includes compatible cached Type 9 native face
  (`DATA UPDATE biodata`) as well as Classic fingerprints, profile and photo;
  blocks mismatched/unknown face template formats before queuing commands.
- Single and bulk face-only repair for existing matching normal users.
- Classic Type 9 BIODATA and legacy FACE receiver; dedicated bounded Classic
  face pull with original template-type preservation.
- Source admin privilege is never copied to a newly enrolled Classic user;
  target normal role always `Pri=0`.
- Fix Security PUSH bulk command dependency gap between different users.
- Add regression coverage for normal roles, native faces, sequencing and
  all-or-nothing bulk validation. See docs/CLASSIC_FACE_TRANSFER_61.md.

## 19.0.0.0.58

- Open selected-user bulk wizard to approved Classic/legacy ADMS sources as well as Security PUSH.
- Add Classic-to-Classic preflight, PIN/identity collision guards, and ordered profile/USERINFO/fingerprint/photo command chains.
- Never reinterpret ATT commands as Security PUSH or silently translate unsupported facial templates.
- Expose photo synchronization from the device form to Classic devices (CHECK/LOG pending upload only; not a historical pull).
- Preserve ACC-to-ACC authorization, biometrics and photo transfer paths.

## 19.0.0.0.57 — Clear batch source-device diagnostics (2026-10-14)

- Diagnose selected source device by serial number, reported protocol and approval
  state before opening Transfer Selected Users. The old generic error obscured
  whether the selected list came from a Classic ADMS terminal or an unapproved
  Security PUSH source.
- Revalidate source and destination separately at wizard submission with clear
  device-specific errors. Keep the ACC-only, device approval, Biometric Manager,
  company access and matching-identity checks unchanged; never change a terminal
  protocol or approve devices automatically.
- Add regression tests ensuring that unsupported/unapproved devices stop the
  batch without queuing any commands. No new database fields or migrations.

## 19.0.0.0.56 — Odoo 19 batch-action upgrade fix (2026-10-14)

- Remove unsupported `groups_id` from the `ir.actions.server` record
  `zk_device_user_batch_transfer_server_action` in `views/device_user_views.xml`.
  This fixes `ValueError: Invalid field 'groups_id' in 'ir.actions.server'`
  during module installation or upgrade on Odoo 19.
- Preserve the Biometric Manager checks inside
  `zk.device.user.action_open_batch_transfer_wizard` and
  `zk.device.user.batch.transfer.wizard.action_transfer`, the model access
  rules, and the manager-only Device Users menu. No privilege is granted
  by removing the rejected XML field.
- Keep all v0.55 batch-transfer and user-picture features unchanged;
  no stored fields or data migrations are introduced.
- Add a regression test for the registered list action and the absence
  of the rejected server-action field.

## 19.0.0.0.55 — 2026-10-14

- Added device-form Pull Profile Pictures for approved Security PUSH devices.
- The query response independently counts accepted image records, including
  firmware -1 ACK and querydata arriving after the ACK.
- Added Device Users list Action → Transfer Selected Users for up to 25 users
  from a single source device. All users are preflighted before queuing any
  commands and ordered with a cross-user dependency chain.
- Added photo-only bulk repair for matching destination users, leaving
  working fingerprints, faces and access policy unchanged.
- Added security checks, tests, and workflow documentation.
- No changes to raw punches, HR attendance generation, employee mappings,
  device protocols or stored timezones.

## 19.0.0.0.54 — Device-user mapping label warning cleanup (2026-10-14)

- Assign distinct model-level labels to internal public-directory employee selectors to resolve the two Odoo 19 registry `Two fields ... have the same label` warnings from `zk.device.user` and `zk.attendance.mapping.wizard`.
- Retain user-facing **Mapped Employee** and **Current Employee** labels through explicit view attributes so staff workflows and screen terminology remain unchanged.
- Preserve private `employee_id` mappings, public-directory selectors, ACLs, transfer commands, raw punches, HR attendances and all biometric data without migration or backfill.
- No `_sql_constraints` declarations exist in this add-on; the many unnamed legacy-constraint warnings in the provided registry log are emitted by other installed modules. Likewise, `tracking` warnings and non-biometric duplicate labels from other modules must be fixed in their respective owners. Do not globally silence Odoo warnings.
- Added a registry regression test for field-label uniqueness and preserved user-facing view labels. Static archive/syntax/XML checks are not a substitute for an Odoo 19 staging registry load.

## 19.0.0.0.53 — Single-click Security PUSH transfers

- Default transfer wizard operation queues profile (if absent), destination `userauthorize`, user query, cached native Type 1/9 templates and cached JPEG profile picture as one dependent chain. Existing user is not recreated when exact PIN/name/normal role and employee are consistent.
- Convenience defaults: target Access Group ID 1, Time Period ID 1, Door ID 1. Retains one unchecked explicit identity + access policy confirmation because ID 1 can grant 24-hour access; checks target inventory and company access.
- Replaces the blocked Security PUSH `Update Device User` legacy action with `DATA UPDATE user` containing PIN and validated Name only, without updating card/password/admin/access attributes. Firmware-specific partial update must be verified on staging.
- No changes to attendance timestamps/timezone rendering, HR sync or historical data; no new stored fields or database migration. A real terminal end-to-end test is still required before production use.

## 19.0.0.0.51 — 2026-10-13

- Removed per-device Classic USERPIC opt-in Boolean and device-form checkbox.
  Approved Classic `att` terminals advertise UserPic automatically; `acc`
  and unapproved terminals keep their existing flags.
- De-escalated normal saved ATTLOG/RTLOG, accepted command deliveries, and
  existing biometric HR conflicts from WARNING to INFO/DEBUG.
- Expected HR provenance validation blockers remain protective; they produce
  an actionable manual-review WARNING instead of repeated ERROR tracebacks.
  Raw punch logs remain saved and prior HR history remains untouched.
- No historical USERPIC query is claimed; CHECK/LOG available through the
  existing guarded command queue as optional protocol tests, not automatic
  commands or a guaranteed picture pull.
- Regression tests updated for flag isolation. No new data fields.

## 19.0.0.0.50 — Opt-in Classic ADMS user photo push and query verification (2026-10-13)

- Add **Receive Classic ADMS User Photos** on approved `att` device forms. It is **OFF by default**, per device, and must be deliberately enabled (e.g. only device 700) by a Biometric Manager. The Classic `options=all` handshake then advertises `TransFlag=1111000001` rather than `1111000000` (tenth bit = UserPic); the other nine bits stay unchanged. Unapproved devices and all `acc` Security PUSH devices keep the old flag and behavior. No device type conversion or queued command is involved.
- Preserve the v0.49 strict JPEG USERPIC receiver, while adding safe `OPERLOG` picture-record counts and enabled-handshake diagnostics (never log PIN, image, filename or base64). Reject Classic `OPERLOG` packets above 8 MiB. Process each packet inside a database savepoint so any malformed photo/error rolls back the whole batch before replying error, never an incorrect success ACK.
- Complete a sent Classic `DATA QUERY USERINFO PIN=<pin>` based on a **matching persisted USER PIN**, not any unrelated USER or FP payload; global user queries still require a received USER row. Record `last_payload_at` for verified responses. This addresses misleading `payload_received` statuses without modifying attendance imports or user/employee mappings.
- No historical image pull is attempted or promised. Enabling the option and having the device re-read the handshake may cause **future** photo uploads if this firmware supports them. Existing photos remain cached; no attendance/profile/biometric data is deleted or rewritten during upgrade. A single new Boolean database column is created by the normal Odoo module upgrade; there is no manual migration.
- Static syntax/XML checks and isolated handshake/codec checks done; staging Odoo 19 + physical 700 verification remain mandatory.

## 19.0.0.0.49 — Device User Name in raw attendance (2026-10-13)

- Add read-only **Device User Name** immediately after **Employee** in the Attendance Analysis list and raw-punch form. The value comes from the currently cached `zk.device.user.name`, matched by the **exact source device + biometric PIN**. It can display an unmapped person's name, without guessing an Odoo employee from the PIN.
- Compute the value in batches as an **unstored** field; do not modify historical raw punches, attendance records, employee mappings, or the physical terminal. Blank names remain blank when the device did not report one. Device-user name edits are reflected in future reads and are not a historical snapshot.
- Add a regression test for same PIN on different devices, missing mapping, missing cached name and name updates.
- Implement bounded Classic Attendance PUSH **passive** photo reception: accept validated `USERPIC PIN=...\tFileName=...\tSize=...\tContent=...` records from `OPERLOG` on an approved device, using the same 2 MiB JPEG normalization and device-specific PIN storage as Security PUSH, without creating or mapping any employee. Raw image and biometric data are never logged. `USERPIC` is not a biometric template.
- The protocol documents Classic user photo upload but does not establish a supported on-demand `DATA QUERY USERPIC` for this terminal. Do not send the Security PUSH photo query or switch `DeviceType=att` to `acc`. Return `-1` from 401's photo query did not produce a picture. No classic active photo-pull button is added without physical firmware validation.
- No new SQL columns or data migrations. Full Odoo registry and terminal tests remain required before production rollout.

# Changelog

## 19.0.0.0.48 — Security PUSH USERPIC upload support (2026-10-13)

- Implement `POST /iclock/cdata?table=tabledata&tablename=userpic&count=N` for approved Security PUSH (`acc`) terminals, using the protocol's `userpic pin=...\tfilename=...\tsize=...\tcontent=...` JPEG/base64 record and `userpic=N` success acknowledgment. Also accepts split `Content=` lines from affected firmware. Unsupported/malformed photos still return an error, never a fake successful acknowledgement.
- Validate package count, maximum request and per-photo size, filename, exact base64 length, JPEG integrity and bounded decoded pixel count. Re-encode JPEG to remove EXIF and arbitrary embedded metadata. Do not log payload, filename, user image or biometric data.
- Store photos in the **existing** `zk.device.user.image_1920` field, scoped strictly to source device + PIN, for the existing Kanban/form. If the photo arrives before the profile, create only a minimal unmapped device-local user cache row (`Privilege=0`, no employee); a later `user` update completes the profile. Never infer an employee from a PIN or change existing employee mappings. Repeated uploads update the same row.
- No new database columns/tables/migrations; upgrade itself creates no user, device command, picture, punch or HR attendance record. Existing picture data is preserved. Raw photo attachments are created only by valid future device uploads.
- Existing v0.47 authorization workflow remains unchanged: `DATA UPDATE userauthorize` requires a specifically approved destination time-period/door; historic PINs (e.g. 2005/9001) require **Repair existing user — authorize access only** plus a terminal-side clock, schedule, and verified scan. **Do not switch a Security PUSH `acc` terminal to attendance `att` to bypass an access rejection**; doing so may remove the access-control protocol and erase device data.
- Added codec/ORM regression tests; unit photo parser tested outside Odoo, full Odoo/SpeedFace integration still requires staging and a real userpic packet captured safely on the device. No biometric BIOPHOTO support is advertised or added.

## 19.0.0.0.47 — Device version diagnostics and explicit Security PUSH access authorization (2026-10-12)

- Fixed Classic ADMS `pushver` versus installed PUSH-software confusion. `pushver=2.4.1` is saved in **ADMS Handshake Version** and must not overwrite **Installed Push Version**. Validated `FWVersion`/`FirmVer` and `PushVersion` data received from the device's OPTIONS, registration, INFO or GET OPTION acknowledgment can populate firmware and installed PUSH fields. The command form shows only the allowlisted, sanitized Safe Version Response; raw device command bodies, arbitrary OPTIONS/INFO details and biometric data remain private. A successful Return=0 *without* an actual version value leaves the version fields unchanged. The form includes a Classic ADMS-only **Request Version Info** action.
- Removed noisy routine GETREQUEST/DEVICECMD/CDATA warnings; errors and failures remain logged. Security PUSH RTLOG event 22/23 is summarized as a non-attendance rejection without raw PIN/biometric payloads, with a possible timezone/clock-skew warning for recent events. Rejections must never create HR attendance.
- For new Security PUSH profile transfers, the Biometric Manager must deliberately choose the **target device's approved Access Group ID (1–99)**, **Time Period ID (1–50)** and **Door ID (1–16)** and confirm the policy. Odoo queues `DATA UPDATE user` as a **normal user**, then a dependent `DATA UPDATE userauthorize`, then a dependent target user query. An authorization failure cancels the dependent verification. `StartTime=0` and `EndTime=0` are no longer sent by the enrollment profile. Do not infer authorization from source Group=1 or the source admin role. The destination access group is explicitly selected for new profiles.
- Added **Repair existing user — authorize access only** to the wizard for already transferred PINs, including 2005/9001. This stage verifies the cached target PIN, name, normal-user role, and employee mapping consistency before queueing a single authorization. It does not resend profiles/templates, grant admin, copy cards/passwords, or change payroll/HR attendance.
- **Device-side validation remains mandatory:** Return=0 does not prove that the terminal has accepted a biometric scan or allows the selected time period. Confirm target device clock (Bahrain UTC+3), locally configured time period, door authorization, and test a normal-user punch. RTLOG `event=23` is a denial, not an accepted attendance event; do not import it as a punch.
- Added a small guarded post-migration moving only obvious numeric legacy `push_version` values for devices reporting `DeviceType=att` into the new **ADMS Handshake Version** field. The original value is preserved there. All raw punches, HR attendance, employees, device-user mappings, biometric templates and command-history records are untouched by migration. Other version values and `acc` devices are untouched.
- Existing v0.46 queued/completed user commands are not retroactively authorized. Use the explicit repair stage after confirming the target access policy. Full Odoo 19 staging tests and physical SpeedFace terminal tests are required before production deployment.

## 19.0.0.0.46 — Authorized cross-company user transfers and lean Device Users list (2026-10-12)

- Remove Profile Picture column from the Device Users list without deleting cached images or removing the Kanban/form picture.
- Transfer wizard's approved Target Device dropdown now includes all devices owned by the manager's assigned companies, including secondary companies not active in the company switcher. The old same-company-only UI domain and Classic ADMS / Security PUSH server rejections are replaced with explicit, backend-validated authorization to BOTH source and destination companies.
- Only Biometric Managers may transfer. Preserve approval, device-family compatibility, PIN collision, Security PUSH fresh inventory, dependent commands, biometric format/algorithm verification, and ordinary destination user privilege safeguards. No ACL/record-rule grant or sudo bypass is added to the selector.
- After successful profile ACK and verified target-user inventory, carry the employee mapping across authorized companies while keeping the source/target device-company ownership and employee-company ownership unchanged. Recheck that the original requesting manager still has the Manager role and access to the source company, destination company, and employee company before applying the deferred mapping. Preserve all conflicting target mappings.
- Add cross-company and permission-revocation regression coverage; document the updated flow and deployment checklist. Upgrading creates no device commands, mappings, templates, or historical attendance changes; validate on staging before production.

## 19.0.0.0.45 — Wizard completion and verified transfer mapping (2026-10-12)

- All **three active modal wizards** (dated Attendance Pull, historical mapping/correction, and Device User Transfer) now show their existing completion notification and **close the modal** via the notification's `next: ir.actions.act_window_close` action. Validation errors leave the modal open so the user can fix inputs. The deprecated compatibility wizard still has no entry point.
- Cross-device **normal user profile** transfers now remember the explicitly mapped source `hr.employee`, source Device User, destination PIN/name and requesting manager on the queued **profile** command. The mapping is not guessed from a global PIN or copied when the command is merely queued.
- After the destination acknowledges the profile successfully, a **dependent read-only user query** is automatically queued (`USERINFO` for classic ADMS; filtered `user` for Security PUSH). Once the destination reports that same PIN and name with normal-user privilege, the existing `zk.device.user` row is automatically linked to the source employee. This covers target data arriving before or after the profile ACK, and repeated user pulls remain idempotent.
- Never override a different target employee, apply an unacknowledged or failed transfer, or create an optimistic device user on queue. If name/privilege/source mapping changed, permissions were removed, or the target query fails/omits the profile, retain it unmapped for explicit review. Source/target companies must match; the original Biometric Manager must be authorized for both the device company and the source employee company. The target biometric templates stay on their previous guarded transfer path.
- Retained **active** Employee form compatibility `Employee ID` field with no biometric button, and corrected punch-code docs: `3 = Break In`; only `1 = Check Out` and `5 = Overtime Out` are explicit OUT codes in the current algorithm.
- No data rewrite or historical backfill at upgrade; no new user, employee, biometric template or attendance record is created by upgrading. Added regression tests for transfer mapping, conflicting identities and wizard notification closure. Full Odoo 19 and physical terminal integration must still be run on staging.

## 19.0.0.0.44 — Exact-match historical HR no-op (2026-10-12)

- When a historical `hr.attendance` row already has exactly the derived first and last punch timestamps, treat the row as synchronized without creating a duplicate or raising an HR conflict warning. Applies to the September 14/15 production case (existing HR IDs 9895 and 9940).
- Leave the original attendance ID, timestamps, `biometric_generated=False`, biometric source metadata, and worked hours unchanged. An exact match is not sufficient proof to reclassify an existing record as biometric-generated.
- Different check-in or checkout times, missing/outstanding checkouts, and unrelated overlapping records continue to follow the existing safe conflict behavior. No bulk backfill, automatic history migration, HR relabeling, or raw-punch deletion.
- Regression tests cover exact match across two historical dates, a second identical pull and a conflicting checkout. Stage-test with the production database backup before rollout.

## 19.0.0.0.43 — Idempotent re-import and historical HR reconciliation (2026-10-12)

- Repeat ATTLOG/RTLOG imports upsert by physical device, PIN, exact UTC timestamp (seconds) and punch type. An existing unmapped row can gain a verified employee mapping or previously absent verification method. Existing mapped evidence is never reassigned by a repeat import; use the audited correction wizard. The nullable unique event hash continues to prevent concurrent duplicate insertion; pre-hash legacy rows are checked before creating anything.
- Reconcile derived HR attendance through one shared helper for live PUSH and historical rebuilding. An existing manual/unverified or other-device attendance on a local day is preserved and reported as an HR conflict instead of causing repeated Odoo validation errors or creating another attendance. Raw evidence is retained even when HR reconciliation is blocked.
- A single check-in on a **completed local day** becomes a zero-hour biometric attendance (`check_out=check_in`); the active local day remains open. Near-identical repeated IN scans under five minutes do not count as a checkout. Genuine later checkout updates a previously zero-hour record. No automatic bulk repair is run at upgrade time.
- Sort Command History newest first in both the model, Kanban and list views. Command delivery remains oldest pending first; historical command rows are untouched.
- Allow a source Security PUSH administrator to transfer identity and compatible templates into an **ordinary target user** (`Privilege=0`) through the existing verified two-step workflow; never clone admin access, passwords, cards, or door rights. Legacy ADMS cross-device user creation likewise uses normal role, omits passwords/cards and queues templates after successful profile acknowledgment. Administrator promotion must be done by an authorized terminal administrator locally; there is no unverified remote-admin action.
- Adds regression tests and revised rollout documentation. No migration deletes/backfills any existing raw punches, users, biometrics, HR attendances or commands. Historical results change only when the device pulls again or an operator explicitly rebuilds selected dates. Validate on staging before production.

## 19.0.0.0.42 — Authorized cross-company employee mapping (2026-10-09)

- Permit a Biometric Manager to link a Device User to an employee employed by a different company **only when the manager is authorized for both the device company and the employee company**. Device ownership, record rules, Biometric Operator/Manager groups, model ACLs, and all transfer restrictions remain unchanged.
- Remove Odoo's implicit same-company check from the Device User and raw attendance **employee reference only**; retain `_check_company_auto` for the models and all other company checks. A raw punch remains owned by the **physical device's** company; the linked employee and generated Odoo `hr.attendance` follow the employee's HR identity/company.
- Switch the Device User editor to a writable `hr.employee.public` proxy (backed by the unchanged `employee_id` mapping) to avoid requiring private HR read rights. Populate that dropdown and the historical correction wizard's public employee selector with the logged-in manager's permitted companies, including secondary companies not currently active. Validate the employee's **public-directory visibility** and both companies again server-side on direct mapping edits or correction wizard submission; reject unauthorized or crafted cross-company requests. No global private `hr.employee` access or new permissions are granted.
- Keep historical correction limited to the exact device + PIN + selected local date range, preserve manual attendance, never change source punches or the physical terminal, and never auto-map an unknown PIN.
- No migrations, record backfills, automatic mappings, device commands, biometric transfers, or changes to the command queue. Add multi-company regression tests and update the user documentation.

## 19.0.0.0.41 — Security PUSH biometric-write field casing

- Changed the `DATA UPDATE biodata` parameter names to the protocol's canonical mixed case. The table name remains the successfully verified lower-case `biodata` form.
- This follows production evidence: the same terminal accepted the user-profile update but rejected the lower-case biometric parameter payload with `Return=-11`. No automatic retry is created; verify one template after upgrade.

## 19.0.0.0.40 — Remote ADMS terminal restart

- Added a Biometric Manager-only **Restart Device** action. It queues the standard `REBOOT` command for an approved, idle terminal; the terminal restarts only on its next ADMS poll, while Odoo.sh remains running.
- The action refuses to run ahead of pending or sent work, preventing a restart from interrupting queued transfers or pulls.

## 19.0.0.0.39 — Security PUSH biometric capability negotiation (2026-10-09)

- Advertise `MultiBioDataSupport` and `MultiBioPhotoSupport` in the Security PUSH `/iclock/push` configuration response after device registration.
- Restrict advertised BIODATA types to the intersection of registered device capabilities and the module's implemented templates: fingerprint (Type 1) and visible-light face (Type 9). Do not advertise unimplemented BIOPHOTO support or Type 8 palm templates. Missing/invalid device capability metadata fails closed.
- Keep classic ADMS `/iclock/cdata?options=all` negotiation, attendance sync, employee transfer permissions, template contents, command queues and all existing data unchanged. No automatic retries or biometric transfer commands are generated by this upgrade.
- Include regression checks for populated, missing and reduced device capability masks, plus server config output. The terminal must request `/iclock/push` again to receive the new configuration. This addresses a verified negotiation omission, not a proven cause of firmware `Return=-18`.

## 19.0.0.0.38 — Empty-target enrollment and transfer wizard fix (2026-10-08)

- Accept a **successful full Security PUSH user query with Return=0** as evidence that an empty target terminal was checked. Security PUSH firmware may report zero through `/iclock/devicecmd` without a `/iclock/querydata` body; a missing `last_user_sync_at` alone must not block enrolling the first user. The latest full-user query must be completed within 24 hours. Unrelated biometric queries, failed commands, and unverified devices never satisfy the inventory check.
- Pre-create the transfer transient record and open it with `res_id`, fixing `Expected singleton: zk.device.user.transfer.wizard()` when Transfer User was invoked on an unsaved read-only modal. Allow target/stage/confirmation fields to be edited while retaining source read-only fields.
- Keep server-side target selection checks, biometric-manager permission, same-company enforcement, duplicate PIN protections, admin-transfer blocking, pending-command safeguards and two-stage biometric verification.
- No automatic push, bulk transfer, re-enrollment, template copy, data migration or modification of existing device user/attendance records during upgrade. Reopen old wizards after upgrade.
- Add Odoo regression coverage for empty and failed inventories and wizard initialization. Production database integration and physical-device write testing still required.

## 19.0.0.0.37 — Controlled Security PUSH user and biometric transfers (2026-10-08)

- Adds a **single normal user profile** Security PUSH transfer stage, using `DATA UPDATE user` with protocol-correct field names and TAB delimiters. No super-admin rights, access cards, passwords or door authorization are copied.
- Adds an explicit **biometric-only second stage** after a fresh target-user pull confirms PIN and identity. Only native-format fingerprint (Type 1) and visible-face (Type 9) templates with complete metadata and identical advertised algorithms may be queued. No automatic bulk transfer.
- Captures Security PUSH `no`, `index`, `type`, `format` and `duress` metadata during biometric pulls. Previously cached biometric records are preserved but require a new source-device pull before pushing biometrics.
- Protects raw command bodies from normal Biometric Manager RPC access because biometric update commands contain sensitive templates.
- Serializes command IDs using a database row lock and actual command history to avoid duplicate `(device_id, command_id)` allocations. Device errors prevent dependent biometric commands from being sent.
- Keeps all legacy ADMS pull/push functionality, historical attendance, next-day zero-hour rule and employee mappings unchanged. No destructive migration or automatic push occurs on upgrade.
- Security PUSH physical-device write behavior **must be validated one profile at a time on staging** before enabling biometric transfer on production; device-returned command ACK and a fresh pull are required to verify persistence.


## 19.0.0.0.36 — Security PUSH query compatibility for access-control terminals

- Select a device-specific protocol using the registered `DeviceType=acc` value: retain classic `DATA QUERY USERINFO` for ADMS terminals, and queue `DATA QUERY tablename=user,fielddesc=*,filter=*` for Security PUSH devices.
- Queue separate Security PUSH biometric queries for device-advertised fingerprint (Type 1) and visible-light face (Type 9), without sending templates to other terminals.
- Add `/iclock/querydata` multipart receiver and unsolicited Security PUSH `/iclock/cdata?table=tabledata` ingestion with approved-device restrictions, command/device/table correlation for query replies, strict record counts, scoped transaction savepoints, idempotent upsert, payload-size limits and no template logging.
- Interpret Security PUSH positive `Return` values as uploaded-record counts rather than failures; preserve legacy success handling and negative error codes.
- Cache unified Security PUSH templates only in the private generic biometric cache. Block unverified legacy `DATA USER`/`DATA FP` transfer and update actions when either endpoint is an access-control terminal. Do not claim that Security PUSH template uploads are yet supported.
- Preserve v19.0.0.0.35 next-day zero-hour checkout behavior, existing employee mappings, legacy ADMS commands, ACLs and upgrade migrations. No migration modifies records.
- Add codec and Odoo regression tests plus deployment/review guidance. Test with these specific SpeedFace firmware versions on a staging server before production deployment.

## 19.0.0.0.35 — Restore next-day missed-checkout handling

- Restored the original business rule: when the next local day's biometric check-in arrives, safely close the earlier **proven biometric-generated** open attendance using its own check-in timestamp as checkout (zero worked hours).
- Applied the shared rule to both incoming ATTLOG/RTLOG sync and the historical rebuild/correction wizard; process all touched days in chronological order to avoid Odoo's overlapping/open attendance validation errors.
- Select `out_mode='auto_check_out'` only when the native field and selection exist; otherwise use the supported `manual` value, or omit the field if it is unavailable. No custom checkout fields, schema changes, data backfills, or destructive migrations.
- Do not treat explicit OUT-type punches as the next day's new check-in. Genuine later checkouts supersede the zero-hour placeholder and use native `manual` where supported. Preserve manual/unproven attendances; an unresolved manual open attendance is reported for review rather than automatically modified. Existing past records are not altered during the upgrade itself.
- Added regression tests for cross-day zero-hour checkout, idempotency, manual record safety, supported/fallback modes, chronological rebuild and consecutive-day ADMS processing.


## 19.0.0.0.34 — Dashboard status-filter compatibility

- Fixed the Online and Offline dashboard cards on Odoo 19. Their connection-status filter now handles Odoo's normalized `OrderedSet` selection value instead of raising an RPC error.

## 19.0.0.0.33 — Older-schema upgrade migration fix

- Moved legacy `zk_device.name` to `serial_number` backfill from the pre-migration to a guarded post-migration. This supports databases where the old `zk_device` table does not yet contain `serial_number`, preventing the Odoo.sh registry build failure.
- The backfill now skips duplicate legacy names, preserving unique-serial safety and leaving ambiguous records unchanged for manual review.



## 19.0.0.0.32 — Explicit private model access declarations

- Declared explicit Odoo access-control entries for `zk.device.biometric.template`, `zk.device.fingerprint`, and the retired `zk.device.user.sync.wizard` compatibility model to address the module-specific missing-ACL warnings seen during registry loading.
- Scoped these entries to a new **unassigned** internal protocol group, not Biometric Operators, Biometric Managers or general users. Private template bytes remain inaccessible to ordinary RPC callers; the existing scoped `sudo()` protocol paths remain unchanged.
- Preserved the legacy sync wizard without adding a menu or an employee-creation path. No data migration, deletion or historical punch/employee mapping modification is performed.
- Audited module Python sources for unsupported `_sql_constraints` declarations: this release already uses Odoo 19 `models.Constraint`. Other modules may still emit generic warnings; the supplied `Failed to load registry` line lacks the traceback needed to locate that failure.
- Added access-isolation regression coverage and security/upgrade/manual-test documentation.

## 19.0.0.0.32 — Safe existing-employee correction

- Loaded the hidden `device_user_id` field so a newly opened wizard initializes its Device/PIN/Company related fields and picker domain correctly.
- Replaced the historical correction wizard's private employee dropdown with a company-scoped `hr.employee.public` selector for Biometric Managers without HR access.
- Removed wizard-created name-only employees, target-mode radio buttons and native employee quick-create.
- Restricted lookup to the device company, including when it is an allowed secondary company; the server also checks device-user write access, company and public employee visibility before resolving the private employee.
- Added validation for missing target, same employee, missing/reversed dates and no matching punches before any correction write.
- Extended automated/manual test coverage and updated README, security, technical, workflow, configuration and upgrade-safety documentation. No upgrade data cleanup or mutation.


## 19.0.0.0.30 — Precise mapped card and employee picker

- Made the dashboard **Mapped Device Users** card open only mappings with an employee, including the matching native search filter context.
- Loaded the wizard Company field and applied an explicit same-company domain to **Existing Employee**, restoring its list while retaining Odoo multi-company protection.



## 19.0.0.0.29 — Native Odoo dark-asset override

- Added a dedicated `web.assets_backend_lazy_dark` stylesheet, following Odoo Enterprise dark-mode bundling, to override the light dashboard cards and explicitly restore readable punch-table text in dark mode.



## 19.0.0.0.28 — Guided correction and native dark dashboard

- Split the mapping wizard into two locked workflows: **Map Past Punches** shows only its two mapping choices, while **Fix Wrong Employee** shows only its two correction choices.
- Added an explicit correction target: select an existing Odoo employee or create a named new employee, preventing accidental duplicates when the employee already exists.
- Reworked dashboard colours with Odoo SCSS theme variables and explicit embedded-list foregrounds so the dark asset has legible cards, headings, and punch rows.



## 19.0.0.0.27 — Clear workflows, reliable filters, and theme-safe dashboard

- Repaired the Attendance Log **Today** and **Yesterday** filters using Odoo-supported dynamic date expressions; the invalid `tomorrow` expression no longer causes an RPC error.
- Made the dashboard Online, Offline, and Punches Today cards open their exact filtered results, and added the missing Offline card.
- Made Device User **Biometric ID** display inline, aligned the mapping buttons, and renamed the choices to **Map Past Punches** and **Fix Wrong Employee** with context-sensitive safety guidance.
- Updated the dashboard and device cards to use Odoo theme variables, keeping light and dark mode readable without hard-coded white surfaces.


## 19.0.0.0.26 — Anonymous ADMS company assignment

- Fixed fresh ADMS terminal registration when `company_id` is mandatory: anonymous device requests now explicitly use the database main company instead of relying on the public HTTP request context.
- Newly discovered devices remain unapproved with attendance disabled until a manager assigns their final Company, Location, and Timezone.

## 19.0.0.0.25 — Fresh-install view fix

- Removed obsolete empty Pivot and Graph view records. Those records were safe only when updating a previously existing view and caused a **Missing view architecture** error on a fresh Odoo.sh installation.
- Device Users remain Kanban/List/Form, Command History remains List/Kanban/Form, and Attendance Logs remain List/Form.

## 19.0.0.0.24 — Restored Employee ID compatibility

- Restored **Employee ID** after Job Title on the Employee form, using the existing stored compatibility value without changing any employee data.
- Added the matching read-only compatibility field to `hr.employee.public`.
- Kept Device + PIN as the sole authoritative biometric mapping and updated the local attendance policy report to use Employee ID through the compatibility alias.
## 19.0.0.0.23 — Device User label, readable views, and documentation alignment

- Replaced the Device User form's PIN icon with a normal **Biometric ID** label.
- Reformatted all module view XML into readable, indented structures and added maintenance comments around major views, actions, mappings, and safety-sensitive UI sections.
- Aligned README and docs with the current device-first menu structure, Device + PIN identity rule, current HTTP transaction/savepoint behavior, `source_event_key` idempotency, command/UI access, and verified fingerprint-only transfer limitation.
- Added an explicit upgrade-safety note confirming this release performs no data migration or intended protocol/data behavior change.

## 19.0.0.0.22 — Native date filters and Device User profiles

- Removed the invalid Device User and Attendance Log Pivot views and restored Command History to list-first navigation.
- Added a manager-editable Device User profile picture and redesigned its Kanban cards with native employee-style avatars, fallback silhouette, and icon-led details.
- Added Attendance Log Yesterday and native Date filters. The Date menu dynamically shows the current and recent calendar months according to Odoo.

## 19.0.0.0.21 — Search and analysis views

- Removed the duplicate status badge from the device card; the central status display is now green when online and red when offline.
- Added native search, company and location filters/grouping to Devices, Device Users, Command History, and Attendance Logs. Biometric ID search is available where a PIN exists.
- Added Device User and Command History Kanban/Pivot views, plus Attendance Log Pivot/Graph analysis. All results remain constrained by the existing active-company record rules.

## 19.0.0.0.20 — Device/PIN mapping safety and operations

- Retired employee-form biometric workflow and public global employee PIN exposure; legacy values remain non-authoritative compatibility data.
- Added exact device+PIN correction of raw mappings and proven biometric-attendance provenance/rebuild safeguards.
- Added company-scoped timezone-aware dashboard metrics, shared online status, device Kanban, chatter tracking, target-cache freshness, custom SVG assets, and stale-command visibility.
- Added a private extensible template cache. Fingerprint is the only verified cache/transfer protocol; face, palm, and other types require physical-device verification before enablement.
- Upgrade preserves raw attendance, existing mappings, device users, and employee data; it only backfills a missing serial where safe.


## 19.0.0.0.5 — Non-destructive idempotency + seconds display

- Removed the destructive 19.0.0.0.4 historical deduplication migration from the package.
- Added a non-destructive migration that only drops the old four-column UNIQUE constraint.
- Added nullable `source_event_key` fingerprints for NEW raw punches only.
- Existing historical attendance rows are not deleted, updated, or backfilled during upgrade.
- New identical retransmissions are deduplicated safely while historical rows remain untouched.
- Existing historical rows are still checked by device + PIN + exact timestamp + punch type before inserting a retransmission.
- Punching Time in the attendance list explicitly displays seconds in Odoo 19.

## 19.0.0.0.4 — Production duplicate/retry fix

- Removed the nested database cursor and manual commits from ADMS attendance storage.
- Prevented `zk.device.last_seen` from being written on every high-frequency GETREQUEST/ATTLOG/RTLOG call.
- Replaced legacy `_sql_constraints` with the Odoo 19 `models.Constraint` API.
- Added exact-punch idempotency per physical device + biometric ID + timestamp + punch type.
- Added a pre-upgrade cleanup that keeps one row and removes exact retransmission duplicates already created by 19.0.0.0.3.
- Kept HR attendance synchronization best-effort using savepoints inside the request transaction.
- Duplicate device retries are acknowledged as success instead of creating another raw row.

## 19.0.0.0.3

- Production hotfix for Odoo 19 search-view validation.
- Removed unsupported attributes from the `<search>` root and `<group>` node in `machine_attendance_views.xml`.
- No attendance/protocol logic was changed by this hotfix.

## 19.0.0.0.2

- Added Security PUSH 3.1.2 `/iclock/registry` support.
- Added Security PUSH `/iclock/push` initialization/configuration support.
- Added `RTLOG` real-time verification event parsing.
- Added device protocol diagnostics and last-seen information.
- Added full POST payload logging preview for protocol troubleshooting.
- Removed automatic biometric-triggered `hr.employee` creation.
- Preserved unmapped punches as raw records with no employee relation.
- Return HTTP 500/`ERROR` on unexpected raw persistence failure instead of false `OK` acknowledgement.
- Expanded verification method values.
- Updated configuration, security, workflow, technical, and regression-test documentation.
- Added upgrade migration to make raw `employee_id` nullable on existing databases.

## 19.0.0.0.9 — Biometric Attendance application

- Promoted the module to a standalone Odoo application with a branded icon, dashboard, Devices, Device Users, Attendance Logs and Command History navigation.
- Added manager-only ADMS actions to pull attendance history, pull users/templates, synchronize timezone, refresh a PIN, and push a cached user plus every cached template to another ADMS terminal.
- Added a target-device field and guided in-app workflow; biometric template data remains out of normal views and logs.
- Added dashboard styling and refreshable native Odoo KPI/action buttons.
- Documented the ADMS-only workflow and role restrictions.

## 19.0.0.0.10 — Fluid dashboard and menu icon

- Added the root-menu `web_icon` so the branded application icon is displayed in Odoo navigation.
- Replaced the sheet-based dashboard with a full-width fluid layout, eliminating dashboard form fields and unused sheet space.
- Redesigned KPI actions as vertical cards: large icon, number, then descriptive label.

## 19.0.0.0.18 — Controlled mapping, scoped access, and safe monitoring

- Added a manager-only historical mapping wizard with Map Only and explicit date-scoped Map and Rebuild modes.
- Raw biometric logs are now read-only for all interactive roles; public protocol ingestion still uses sudo.
- Added device-company record rules for devices, cached users, commands, and raw logs.
- Added a safe command form that shows operation, state, response, and import counters without exposing command payloads.
- Separated human-facing device name from immutable ADMS serial use in protocol logging.
- Added scoped Device Users navigation, a safer transfer dialog, approved-device command guards, and refreshed device/attendance forms.

## 19.0.0.0.19 — Legacy employee PIN retirement

- Removed the legacy global Biometric Device ID from the employee form and stopped populating it during device-user sync.
- The device/PIN mapping in Device Users remains the only authoritative identity mapping; historical legacy values are left untouched in the database.
