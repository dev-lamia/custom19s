## v0.53 — Single-click Security PUSH transfer

Open the source Device User, choose **Transfer to Device**, select the approved Security PUSH target, verify destination access Group/Time Period/Door (default 1/1/1), check the **one** identity-and-access-policy confirmation, and click **Transfer User**. The server validates identity, fresh destination user inventory (24 hours), rights to both companies, algorithm compatibility, photo size and user roles **before** any writes are queued. It then queues in strict dependency order: new normal user (if absent) → authorize time period/door → target user query → all available compatible fingerprint/face templates → JPEG photo if cached. Existing same-identity users skip profile creation. Conflicts and admin destination users block transfers. Failed commands prevent subsequent commands from being sent. A queued transfer is not a completed physical transfer: check command history and have the user verify fingerprint, face and approved door access on the target. Repair-only options remain available. Period 1 can be unrestricted; manager confirmation is always required. The source employee mapping follows the user only after verified matching destination identity. No automatic historical attendance, timezone or payroll changes.

## v0.51 Classic user photos without disconnecting the terminal

The former Classic photo opt-in checkbox was removed. Approved `att` devices advertise UserPic automatically via the documented tenth `TransFlag` bit. After the upgrade, queue `CHECK` (only when command history has no pending/sent commands) to ask a terminal such as 700 to re-read its options without physical disconnection; queue `LOG` subsequently if you want to test newly available data transmission. Observe the next `/iclock/cdata` options and `OPERLOG ... pictures=N` logs. A `DATA QUERY USERINFO` pull can update a name and fingerprint templates but does **not** mean a portrait was sent. The Classic QUERY command list does not demonstrate a historical USERPIC photo pull. Device type, employee mappings, raw punches and HR history must remain unchanged.

# Workflow

## v0.48 incoming Security PUSH user photos

After the upgraded server receives `table=tabledata&tablename=userpic&count=1`, it decodes the JPG user profile photo, validates the uploaded size and exact source device + PIN, stores it on the Device User record, and returns `userpic=1`. Repeated uploads reuse the same row. The existing Kanban/form displays the image; the list does not. If the photo arrives before the user's profile, it creates only an unmapped device-local cache stub; later `user` tabledata supplies the profile. Malformed uploads return an explicit error so the device can retry after correction.

**Device 401 invalid-time:** Enrollment alone is not sufficient. For users previously transferred under v0.46, use v0.47's explicit **Repair existing user — authorize access only** stage after checking the desired **destination** group/time period/door and its *physical* clock. A `Return=0` on `DATA UPDATE userauthorize` still requires physical verification. Do not switch 401 to `att`: it already reports `acc`, and changing the terminal type can wipe data and remove the desired access-control functionality.

## v0.47 Security PUSH employee transfer workflow

1. Pull source and destination users. 2. Start the Transfer Device User wizard and choose profile stage. 3. Confirm target PIN inventory, destination-approved Access Group ID, Time Period ID and Door ID. 4. Queue profile, then dependent userauthorize, then user query. 5. Confirm all commands report success and that the user's PIN/name/role mapping was verified. 6. Push compatible biometric templates in the second stage. 7. Have the employee punch on the destination: failed access/Invalid Time must be investigated on the terminal, not generated as an Odoo punch. For previously transferred users, choose authorization-only stage to assign the approved target rule without touching biometrics.

## 1. Device discovery and configuration

```text
Terminal points to Odoo ADMS URL
        ↓
/iclock/cdata handshake
        ↓
Odoo identifies terminal by Serial Number
        ↓
Device record exists/created
        ↓
Administrator configures:
Device Name + Company + Location + Timezone
        ↓
Approve Device for sensitive user/template operations
        ↓
Enable Receive Attendance when ready
```

The friendly Device Name is not the ADMS identity. `serial_number` remains the physical protocol identifier.

## 2. Classic attendance PUSH

```text
POST /iclock/cdata?table=ATTLOG
        ↓
Check Receive Attendance
        ↓
Parse PIN + local timestamp + punch/status + verification
        ↓
Convert device-local time to UTC
        ↓
Resolve exact Device + PIN mapping
        ↓
Upsert exact raw punch (new event, or existing evidence)
        ↓
Mapped employee?
   ├── No  → keep raw punch only
   └── Yes → process days chronologically; close any previous-day missed
              biometric checkout at its OWN check-in (zero hours) before
              creating the next day's attendance
              → update that biometric-derived employee/device/PIN day
```

**Missed checkout:** On import or confirmed rebuild of a completed local day with no valid checkout, `check_out` equals `check_in` for a proven biometric attendance (zero hours). For an already open proven biometric attendance, the next local-day check-in also triggers this close. It then has zero worked hours. A real second punch on the old day is preferred, and manual/unproven attendance is not auto-closed. Explicit OUT punches from overnight shifts do not trigger the rule. The mode uses native `out_mode=auto_check_out` if defined and allowed, otherwise native `manual` if supported; this module adds no checkout-mode field. Both live processing and the confirmed historical rebuild use this rule. Upgrading the module does not retroactively change attendances until the corresponding day is processed/rebuilt.

## 3. Security PUSH realtime attendance

```text
GET /iclock/cdata?options=all&pushver=3.1.2
        ↓
POST /iclock/registry
        ↓
POST /iclock/push
        ↓
POST /iclock/cdata?table=rtlog
        ↓
Supported verification event
        ↓
Same raw attendance pipeline
```

Alarm/error RTLOG entries are not treated as attendance punches.

## 4. Unknown biometric ID

```text
Punch arrives for PIN 9999
        ↓
No Device User for this exact device + PIN
        ↓
Store raw attendance with Employee empty
        ↓
Do not create an employee
        ↓
Do not create derived hr.attendance
```

A numeric PIN used on another terminal is not considered a match.

## 5. Pull users/templates

From the source Device choose **Pull Users and Templates**.

```text
Odoo queues user query
        ↓
Device polls Odoo
        ↓
Device returns USER / verified FP data through protocol payloads
        ↓
Odoo upserts private cache by source Device + PIN
        ↓
Existing explicit employee mapping is preserved
```

The pull does not guess an employee from the deprecated employee-level PIN field.

## 6. Map a Device User

Open **Biometric Attendance → Device Users** and open the exact source device/PIN.

Set **Mapped Employee** manually. This mapping applies only to that terminal and PIN.

For existing raw evidence:

- **Map Past Punches** can link previously unmapped raw rows.
- Rebuild requires a date range and confirmation before biometric-derived attendance is created/updated.

## 7. Correct a wrong employee mapping

Use **Fix Wrong Employee** when a device/PIN was previously assigned to the wrong employee. Choose **Correct Employee** from the public directory for companies the manager is authorized to access; the employee may belong to another company than the device. The selector does not offer quick-create; missing employees must be created properly in the Employees application first. The wizard rejects a same-employee target, missing/reversed dates, an employee company the manager cannot access, unauthorized device-company access, or zero matching raw punches. Raw punches remain owned by the device company; the employee's employing company does not change.

Correction is limited to:

```text
Selected Device
+ Selected PIN
+ Selected local-device From/To dates
```

**Move Raw Punches Only** changes the Employee relation on those raw rows without altering source device/PIN/timestamp/punch evidence. The current Odoo Device User employee mapping is updated for future ingested punches, but the physical terminal is never updated by correction.

**Move Punches and Rebuild Odoo Attendance** additionally removes/rebuilds only `hr.attendance` records proven by biometric provenance to belong to that exact source. Unproven/manual attendance remains unchanged and may require review.

## 8. Update the same device user

Use **Update Device User** from the Device User form when changing the same terminal/PIN.

```text
Source Device + PIN
        ↓
Queue supported user update
        ↓
Same Source Device + PIN
```

This is not a transfer and must not create another device identity.

## 9. Transfer to another device

Use **Transfer to Device** only for a different approved target terminal.

The target dropdown shows approved devices in **all companies assigned to your user**, including secondary companies not currently active. Only Biometric Managers with access to **both source and destination companies** may transfer across companies; the user's permitted companies are verified again when the request is submitted. The wizard shows the status of the target's most recent user inventory query. A successful full Security PUSH query returning **0 users** is sufficient for an empty target and does not require manually enrolling somebody first. The transfer is blocked when the target is unapproved or same as the source, has no recent verified user inventory, belongs to a company not assigned to the manager, has a conflicting PIN, or has outstanding commands.

**Historical behavior through v0.52 only:** For Security PUSH, **Step 1** queues a normal user profile plus a **dependent, read-only target user verification query**. After a successful profile acknowledgment and a returned target identity matching the source PIN and name (normal role), Odoo **automatically copies the existing source employee mapping** onto the new target Device User. The terminal may still need a manual **Pull Users and Templates** if its filtered response is not provided or incomplete. Verify the profile on the physical terminal. **Step 2** may then send compatible biometric templates; biometrics are never automatically sent as part of a first-user transfer. The source user and source mapping remain unchanged.

Classic ADMS transfers likewise queue a normal user profile, a dependent `USERINFO` verification query, and existing gated fingerprint commands. A fresh target user response will inherit the employee mapping automatically once the profile ACK succeeds. No target device user is invented when the command is merely queued. A target PIN already mapped to a different employee, a different device user name, an elevated destination role, a failed profile, or unauthorized cross-company mapping is never overwritten. This employee-link automation applies **only to verified transfers**, not arbitrary matching PINs. Without a verified response, check Command History and refresh target users before attempting manual correction.

All active wizard confirmation buttons display their existing success notification **and close the dialog**. Validation errors keep the wizard open for correction.

## 10. Pull historical attendance

From a Device choose **Pull Attendance**.

The wizard uses:

- From Date / To Date = full requested period;
- Device Request Range (Days) = chunk size for queued requests.

The device processes these requests asynchronously during later polls.

## 11. Restart a remote terminal

From an approved, idle Device, a Biometric Manager can choose **Restart Device**. Odoo queues `REBOOT`; the terminal restarts when it next polls ADMS. This restarts only the remote terminal, not Odoo.sh. Complete or cancel pending commands first.

## 12. Command History

Command History shows safe operational information:

```text
Queued/Pending → Sent → Completed or Failed
```

A sent request older than the configured UI threshold is marked **Waiting Too Long**. The raw ADMS command payload is intentionally not rendered in normal views.

## 12. Attendance Analysis

**Attendance Logs** opens read-only **Attendance Analysis**. It is raw source evidence, not a manual attendance-entry screen.

Use filters/grouping to review:

- mapped/unmapped punches;
- date;
- company;
- location;
- employee;
- device;
- biometric ID.

### Troubleshooting: "Batch transfer requires an approved Security PUSH source device"

Use the source terminal's **Device Users** page before selecting records. For
394 -> 401, open device **394**, click its Device Users button, select only its
users, and use **Action -> Transfer Selected Users**. Set destination to 401.
A batch can contain 1–25 users from **one** source, not mixed device records.
Both source and destination must be approved and report `acc`. A terminal
reporting `att` is Classic ADMS: never force its device-type field to `acc` in
Odoo; the firmware must actually implement Security PUSH.

Version 0.57 identifies the rejected source or target SN, its protocol, or its
approval state in the error rather than changing the validation. For previously
transferred, physically working users, prefer photo-only repair instead of
full transfer. For a photo pull use the destination device's **Pull Profile
Pictures** command and check the cached picture count independently from
terminal command ACKs.


### Mixed device fleets (v0.58)

Use the **same selected-user wizard** for Classic (including legacy ADMS
handshakes without a DeviceType value) and Security PUSH. The wizard chooses
protocol-native commands; the devices do **not** need the same reported
DeviceType string if both are Classic. Security-to-Classic biometric transfers
remain blocked because formats cannot be safely translated. Classic transfer
preflight requires a fresh target USERINFO cache, and does not treat a photo
as a face template. See README for firmware-dependent photo limitations.
