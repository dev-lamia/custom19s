## 19.0.0.0.54 — Registry warning cleanup

This is a metadata-only correction: only the public HR proxy field labels change in Python, with the previous business labels retained explicitly in the list/form XML. There are **no new fields, no stored-column changes, no migrations, and no device instructions** triggered by upgrading. The transfer wizard and attendance processing are unchanged.

After a staging backup, upgrade **only** `tam_hr_zk_attendance`, then check that the `zk.device.user` and `zk.attendance.mapping.wizard` duplicate-label messages are gone. A full Odoo registry rebuild will still print unrelated warnings (legacy `_sql_constraints`, non-chatter `tracking`, Studio duplicates, deprecated imports/routes) until their owning addons are separately repaired. Do not change unrelated modules as part of this ZIP and do not run `-u all` solely to remove warnings.

## v0.52 upgrade

No new database columns or tables. Adds two explicit Security PUSH-only transfer wizard stages and read-only cached modality/photo indicators; does not auto-resend existing users. Do not run new repair operations until the two device identities, approved company access, source picture and/or Type 9 templates, target native algorithms, and configured access rights have been checked. Backup database and filestore before staging upgrade.

## v0.51 scope, safety, and expected attendance notices

- Upgrade `tam_hr_zk_attendance` normally in a staging clone after DB and filestore backup. The v0.50 `classic_userpic_upload` field/checkbox is **removed**; if the database had the old field, its former physical column is deliberately **not dropped** by a destructive migration. No new column is needed.
- All approved Classic Attendance PUSH (`att`) devices advertise user photo uploads when they next receive options, without user interaction. Approved Security PUSH (`acc`) and unapproved devices remain unchanged. Do not interpret the automatic flag as a proven historical photo dump.
- The device does not need to be physically disconnected repeatedly: `CHECK` can prompt settings refresh, and `LOG` can request sending newly available data. Both may re-upload packets, so use a one-device command at a time and observe the existing idempotent punch handling.
- Normal successful ATTLOG/RTLOG storage and already-existing biometric HR duplicates are no longer WARNINGs. Manual/unverified older open HR attendances remain untouched; blocked HR reconciliation is reported as an actionable WARNING rather than a full ERROR traceback. **A manual HR review is still necessary** to correct those records.
- No claim of fixing an Odoo.sh backend query killed after 990 seconds: investigate locks/performance separately, preserving production database state.

# Upgrade Safety

## 19.0.0.0.48 — Profile-photo upload release

No schema-changing fields, table creation or migration were added; the existing `zk.device.user.image_1920` field is used. Module upgrade itself does not pull/send commands or change existing users, mapping, HR attendance, raw punches or biometric templates. Future valid `userpic` packets can create a device-specific, non-privileged, unmapped cache stub if USER has not been received, or update the picture of an existing cached user. Existing photos are preserved until a valid new upload replaces them.

Validate with **Odoo 19 staging DB + real SpeedFace** before production. `userpic` now receives protocol acknowledgment only after a valid JPG is persisted; malformed/unsupported uploads still return HTTP 400 so a device may retry. Monitor upload outcomes and avoid logging sensitive photo contents. Upgrading this module does **not** automatically repair the existing `Invalid Time` denial on 401. Keep `acc` on Security PUSH devices; choose the explicit authorization-only repair and check local clock/door/time schedules with a physical scan.

## 19.0.0.0.47 — Production rollout

- Back up database and filestore; test with the actual Odoo 19 production-clone schema. Only obvious `att` numeric legacy handshake versions migrate from the old Push Version slot into the new ADMS Handshake Version slot. No attendance, employee, user mapping, biometric or command record is changed by the migration.
- Newly queued profile transfers require deliberate target time-period and door selection. Previously transferred 2005 and 9001 require authorization-only repair after identity/inventory and access-policy checks; these are never queued automatically during upgrade.
- Device 700 still explicitly reports `DeviceType=att` in its handshake. Its firmware screen may show installed PUSH software `Ver 3.1.6S-20260115`; this does not authorize Security PUSH transfers or establish compatibility. No protocol flag is force-changed.
- Device 401's physical Invalid Time diagnosis remains conditional on local clock, approved access time periods, door and holidays. Return=0 on a newly sent command is NOT a successful physical access test.

## 19.0.0.0.44 — Existing exact-match attendance

- For historic HR rows whose check-in and checkout exactly match the first/last raw punches for that employee and local device day, the receiver now considers HR synchronized and suppresses the old false-positive conflict warning.
- This is intentionally a read-only match, **not** a conversion of unknown-provenance HR records into biometric-owned records. Never mark `biometric_generated=True` automatically based solely on timestamp equality.
- Other overlaps or differing times still generate a conflict and preserve existing HR attendance. Reimporting identical raw data will not duplicate raw events or HR records. No upgrade-time data changes occur.

## 19.0.0.0.43 — Production-safe repeat imports

- Back up the production database **and filestore**, copy the current module ZIP, and validate the Odoo 19 upgrade with actual database schema in staging. Run the module's regression suite against Odoo, then compare July 16/19/20 manual HR IDs and raw punch IDs before/after test pulls.
- No database migration, delete, truncation, deduplication, backfill, or automatic historical reconciliation happens merely by installing this version. Previously unmapped existing raw events can gain an employee reference **only when the matching device event is imported again**, never by global backfill.
- Exact re-import event identity: (physical device, PIN, UTC datetime to the second, punch/status code). Verification method is not part of the key. A corrected device timezone changes the computed UTC timestamp, so fix timezone configuration **before** bulk pulling and review historical events on staging.
- Existing manual/unproven HR attendances (e.g., IDs 9016, 9024) are not changed or tagged as biometric. A conflicting biometric day is logged as a conflict and its raw evidence is retained without a duplicate HR record. Reconciliation cannot automatically determine whether a previously-created, untagged attendance was manually entered or generated by an older module; handle it explicitly after review.
- Completed local days with a single IN punch are finalized at zero hours when those days are reprocessed. Existing genuinely completed biometric hours are not cleared. This is an intentional behavior change and must be checked against payroll/HR policy before deploying.
- The administrator **source** identity can be copied as a normal destination user, subject to the same destination PIN and company checks. Promotion to administrator is a separate authorized manual step on the target terminal. Do not bulk-push biometric templates without physical-model compatibility validation.
- Keep access-control/network rules for unauthenticated ADMS endpoints, and never print biometric payload bytes in logs or tickets. Run canary imports with one device and a short date range before January–October full re-import.

## 19.0.0.0.32 — Private biometric cache ACL registration

- Adds three `ir.model.access` rows for existing models and one unassigned service-only `res.groups` record. Neither ordinary users nor Biometric Managers inherit the group.
- Does **not** expose fingerprint/template data to staff, add views/menus, or change any device/employee/punch/attendance behavior. Existing protocol methods continue to use `sudo()`.
- Does not modify employee, Device User, raw punch, biometric cache, command history or attendance rows. No migration, uninstall hook, data cleanup or destructive command is included.
- A full Odoo database upgrade on a backed-up staging instance is required to validate actual `ir.model.access` loading and Odoo 19 registry initialization. The supplied registry failure line has no traceback; unrelated `_sql_constraints` / `permission_manager_basic` warnings must be investigated in their owning modules.


## 19.0.0.0.31 — Correction wizard employee directory

- Switches the correction target selector from private `hr.employee` to read-only public employee records; this prevents empty dropdowns for non-HR Biometric Managers.
- Removes the optional create-employee branch and its text field. Employee master records must be created in Employees.
- Adds server-side company/access checks and requires a different existing employee, valid dates and matching raw evidence.
- No SQL migration or data cleanup is included; existing Device Users, raw punches, employee master records and biometric-derived attendance are left untouched during module upgrade. Corrections only change data on explicit user confirmation after the upgrade.
- Existing transient (wizard) records are temporary; any open wizard should be closed and reopened after upgrading so its client view matches the new fields.

## 19.0.0.0.23

This release is a UI/documentation maintenance upgrade only:

- Device User form replaces the PIN icon in the title with an explicit **Biometric ID** label.
- View XML is reformatted for maintainability and receives comments around major view/action sections.
- README and docs are aligned with the current device-first UI, transaction model, idempotency implementation, multi-company behavior, and biometric-template limitations.

There is no data migration for 19.0.0.0.23 and no intended change to device protocol, raw punch, employee mapping, command, biometric template, or `hr.attendance` data.

## 19.0.0.0.20

The upgrade does not delete, deduplicate, or rewrite raw punches or existing employee mappings. It may fill a missing `zk.device.serial_number` from a legacy device name only where that name is non-empty and cannot collide with another serial.

The legacy employee PIN column remains as inert compatibility data. The retired employee-centric transient model remains imported without UI/action/ACL so upgrading does not destructively remove an already-installed technical model.

## 19.0.0.0.7 — legacy `address_id` compatibility

Some older installations used `zk_machine_attendance.address_id` as a text location (for example `KSA`), while others used it as a `res.partner` foreign key. Version 19.0.0.0.7 stopped declaring/using that overloaded raw-log field so Odoo would not attempt unsafe text/integer conversion.

The database column and existing attendance history were deliberately left untouched. Current physical location belongs on `zk.device.address_id` (shown as **Location**).

## 19.0.0.0.5 — non-destructive duplicate protection

Current upgrades do **not** globally delete or rewrite historical `zk_machine_attendance` rows to enable duplicate protection.

Only newly created punches receive `source_event_key`. The field is nullable, so older historical rows remain valid even if they contain identical values.

Before creating a new row, the controller also checks the historical event identity:

- physical device;
- biometric PIN;
- exact UTC punch timestamp, including seconds;
- punch type.

This prevents a retransmission from recreating an old event while preserving existing rows.

### Recovery of data deleted by an older package

A module upgrade cannot reliably reconstruct raw punches that were already deleted by an earlier release. Restore them from a database backup or re-import/retransmit them from the physical terminal if it still retains the transaction history.


## v19.0.0.0.35 — Restore original next-day rule

No migration or bulk repair is performed. Existing biometric and manual attendances, raw punches, employee/device mappings and biometric templates are preserved on upgrade. Auto-close occurs only **during** later live sync or an administrator-confirmed rebuild when a subsequent local-day check-in is processed. It affects only verified, biometric-generated, currently open older-day `hr.attendance` records: checkout becomes equal to original check-in (zero worked hours). Confirm on staging first; test on a copy of the production database. Use the native `out_mode` selection if present; the addon does not declare or extend this field. Explicit OUT punches and manual/unproven attendances are not auto-closed.

## v19.0.0.0.36 — Security PUSH rollout

- Upgrade on a staging clone of the actual production database first. No data rewrite/migration is included in this version.
- Confirm the four legacy devices still queue one `DATA QUERY USERINFO` command and import users unchanged.
- On each approved SpeedFace `DeviceType=acc` terminal, run one **Pull Users and Templates** request, then verify three distinct command rows: `user`, `biodata Type=1`, `biodata Type=9`. A device can reject one query while processing others; inspect each result separately.
- Security PUSH devices respond on `/iclock/querydata`. If a reverse proxy blocks it, fix the route before retrying. Confirm the device IP/network is trusted; existing public PUSH routes identify devices by registered serial number rather than cryptographic device authentication.
- Verify record counts and template support against physical enrollment; do not transfer biometric data to these terminals yet. The UI blocks unverified legacy upload actions.
- Keep database+filestore backups and the complete old production ZIP. An Odoo runtime/actual SpeedFace test is required before production deployment.

## v19.0.0.0.37 — Controlled Security PUSH write compatibility

- Take a database and filestore backup, test the module upgrade on a staging copy with the deployed production schema, and verify all six devices still connect.
- No migration deletes or modifies existing device users, templates, attendance or raw punches. New biometric metadata columns are nullable/defaulted, so previously cached records are preserved. **Re-pull the source device** after upgrading to populate missing `no/index/format/duress` metadata; otherwise the biometric push stage is blocked.
- Security PUSH profile push is intentionally limited to one normal (privilege 0) device user at a time. Admins and PIN conflicts are blocked. Passwords, access cards and door access authorization are not transferred.
- Never use the biometric stage until a first-stage profile ACK succeeds, the user is visible physically on the target terminal and a target pull confirms name and PIN. Identical source/target device algorithm support is mandatory.
- Raw command strings can contain biometric payload and are restricted to the internal service group at field level. Review production network/proxy access to unauthenticated `/iclock/getrequest` before sending any biometric template over this protocol; a device serial alone is not strong authentication.
- On a failed profile or template update, stop, examine numeric return codes and rerun pulls. Template commands with failed prerequisites are canceled rather than delivered. Odoo runtime integration and physical-device tests are required.


## v19.0.0.0.38 — Empty-target transfer wizard hotfix

- No migration or data rewrite. A successful Security PUSH user pull returning `0` is a valid, empty inventory even when the terminal does not send a user payload and `last_user_sync_at` remains empty. A recent successful completed full user query (or a recent persisted user payload) is required.
- Device User transfer wizard is pre-created and referenced by `res_id`. The target is selected after creation, and server-side validation enforces the required target. Close and reopen any modal that was open before upgrading.
- Staging tests should start with one non-admin user into an empty target. Check the command ACK and verify the user by pulling target users again. Do not attempt biometric transfer until identity and algorithm compatibility are confirmed.
- Other device sync, attendance, command history, and private biometric-template storage are unchanged.


## Security PUSH negotiation deployment — 19.0.0.0.39

1. Back up database and filestore. Upgrade on staging first.
2. Verify `/iclock/push` contains `MultiBioDataSupport` for fingerprint Type 1
   and visible-face Type 9 and contains all-zero `MultiBioPhotoSupport` for
   device records that advertise these types. No private session ID should
   be copied into tickets or logs.
3. Observe an actual device `/iclock/push` fetch after staging restart or
   reconnect. The Odoo code being upgraded alone does not prove the terminal
   has fetched the new negotiated mask.
4. Test exactly one biometric push and verify the command ACK and a fresh
   device pull. Do not bulk-transfer while `Return=-18` remains unexplained.
5. The module does not modify existing template data, employee mappings,
   command history, or attendance records as part of this upgrade.

## v19.0.0.0.44 → v19.0.0.0.45: wizard close and verified transfer mapping

- No destructive migration. New private transfer intent fields are blank on all existing command rows; previously queued transfers are **not** automatically matched retrospectively.
- A newly queued authorized profile transfer adds a dependent **read-only target user query**. This is expected new command-queue traffic. The dependent query runs only after profile ACK success, subject to device polling. If firmware omits response, the target remains unmapped until its matching identity is observed.
- The destination user is **not created at queue time** and a successful ACK alone does not assign an employee. A returned normal user with matching name/PIN can inherit the source mapping without another wizard. Source mapping must remain unchanged, and the requesting manager must still be authorized for both relevant companies at link time.
- Failed/renamed/conflicting/privileged transfers require manual review; do not retry by forcing direct database employee mapping without establishing the destination identity.
- Active wizard dialogs now close after their success notification; validation errors are unchanged.
- Staging rollout: backup database and filestore, upgrade module, execute transfer and wizard checks in `docs/TEST_CASES.md`, verify Command History shows profile + dependent verification and no duplicated Device User/raw attendance/HR attendance. Physical device testing is still required.


## v19.0.0.0.46 — Cross-company selection and transfer safeguards

No migration, command execution, bulk user creation, HR modification, template copying, or stored-profile-image deletion occurs from upgrading. The Device Users list no longer shows the picture column; pictures remain on cards/forms. Existing device record rules/ACLs remain in effect.

Before production, test both devices in different *assigned* companies while only the source company is active: source user opens the wizard, target is selectable, command is queued, device acknowledges it, and verification populates only the intended employee. Check the unauthorized-company, revoked-access, stale-inventory, conflicting-PIN, and privilege-elevation denial paths. Physical terminal tests remain necessary for biometric transfer.


### 19.0.0.0.59 — group raw punches by Device User Name

The **Attendance Analysis → Group By → Device User Name** filter groups by
`zk.machine.attendance.device_user_id`, a stored, computed link resolved using
**both the physical device and the PIN**. The visible `device_user_name`
column remains a live, non-stored name lookup. The linked Device User display
name includes its device serial and PIN so identical names on two terminals
are not merged. The group option is limited to Biometric Managers because
normal operators do not have read access to the Device User model.

An upgrade creates one nullable indexed Many2one field on the raw punch table.
The post-migration links existing raw punches where the exact device/PIN
corresponds to a cached user. New user profiles trigger recomputation of their
matching historical raw punches. Only **grouping metadata** is added: it does
not map employees, change raw punch timestamps, delete or duplicate punches,
or create `hr.attendance` rows. Unrecognized device/PIN pairs remain unlinked.

Perform database and filestore backups and test staging upgrades first. This
migration writes the new `device_user_id` column for potentially many records;
run during a maintenance period if the raw punch table is large.
