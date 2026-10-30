## v0.51 — Classic device pictures without an opt-in checkbox

1. Back up the Odoo database **and filestore**, and upgrade `tam_hr_zk_attendance` v19.0.0.0.51 in staging before production. There is no extra Boolean field or per-device photo setting.
2. An **approved `att`** terminal automatically receives `TransFlag=1111000001` when it asks Odoo for Classic ADMS options; unapproved/`acc` devices are unaffected. The receiver retains private JPEG USERPIC packets in the correct device+PIN cache.
3. To have device 700 read the new options **without physically disconnecting**, queue a single documented `CHECK` command when its queue is empty. It may cause additional data uploads according to the device's stamps; test during a quiet window. Device polling delivers it automatically.
4. For **newly available** pictures, a documented `LOG` command asks the terminal to transmit newly available data. Neither CHECK nor LOG is a guaranteed historical-photo query. A documented Classic `DATA QUERY USERPIC` has not been verified for this firmware.
5. Check the terminal for a **real user portrait** (PIN 1002). A face template alone is not a JPEG user photo. A qualifying photo may be sent as `OPERLOG USERPIC`, shown in `ZK OPERLOG stored: ... pictures=1`, and persisted in `zk.device.user.image_1920`. Image content is not logged.
6. Do not change device type, reset the terminal, clear data, or send DELETE commands to retrieve photos.

# Configuration

## v0.48 user photo reception

Approved Security PUSH `acc` devices may upload user profile photos with `tablename=userpic`. No setting, new model, database column or media directory needs to be manually created. Files are persisted in the existing Device User `image_1920` field and Odoo's standard image storage. Use HTTPS, existing device approval and company permissions. Repeated HTTP 400 on `userpic` means the new code is not deployed or the payload failed size/type/JPEG validation; the server does not log or store raw picture content. Retain separate `biodata` and `biophoto` capability policy.

## v0.47 destination authorization setup

Before Security PUSH transfer, have the destination security administrator verify the destination Access Group ID, Time Period ID and Door ID locally. The v0.53 transfer wizard pre-fills Group=1 / Time Period=1 / Door=1 for convenience, but a single mandatory confirmation must explicitly approve the actual target policy; defaults do not prove that access is appropriate. Time Period 1 may be all-day on some terminals, so selecting it must be an intentional access policy decision. To correct already-enrolled 401 users without touching their biometric templates, pull the target's users, choose **Repair existing user — authorize access only**, enter the destination-approved rule/door, and verify one physical punch. Check the terminal clock (Asia/Bahrain / UTC+3 for devices physically in Bahrain), holidays and access groups if Invalid Time continues.

## Device setup

Open **Biometric Attendance → Devices**. Devices open in Kanban first, with list and form views also available.

Important fields on the Device form:

| Field | Meaning |
| --- | --- |
| Device Name | Friendly editable name used by people, for example `Bahrain Main Entrance`. |
| Serial Number | Immutable hardware serial used to identify the terminal in ADMS/PUSH requests. |
| Company | Company that owns the device and controls multi-company visibility. |
| Location | Free-text physical location, for example `Riyadh - Warehouse Gate`. |
| Timezone | Physical timezone used to interpret device-local timestamps. |
| Approved Device | Allows sensitive user/template pull or transfer operations for this terminal. |
| Receive Attendance | Controls whether incoming attendance payloads from this terminal are stored. |
| ADMS Status | Computed Online/Offline status using the module's shared connection threshold. |
| Last Seen | Last tracked device contact used for operational diagnostics. |
| Users Last Refreshed | Last successful user/template refresh timestamp. |

Protocol diagnostics such as reported device name, firmware, push version, registry time, and IP address are read-only.

## Recommended onboarding

```text
1. Configure the terminal's ADMS/Cloud Server URL to point to Odoo.
2. Let the terminal connect so Odoo can discover its serial number.
3. Open Biometric Attendance → Devices.
4. Set Device Name, Company, Location, and the correct physical Timezone.
5. Leave Receive Attendance off until the device is verified.
6. Approve the device when it is trusted for user/template synchronization.
7. Enable Receive Attendance when raw punch storage should begin.
8. Pull users/templates and map each exact device/PIN to the correct employee.
9. Make a test punch and verify Attendance Logs before relying on derived Attendances.
```

## Employee mapping

The authoritative mapping is **Device Users**. Each mapping belongs to one exact physical terminal and one PIN.

```text
Device + PIN → Mapped Employee
```

Do not treat the numeric PIN as a company-wide or database-wide employee identifier. The deprecated employee biometric PIN field is retained only for upgrade compatibility and is not used for incoming attendance matching.

For an unknown PIN:

1. Pull users from the relevant device if its user cache is not current.
2. Open **Biometric Attendance → Device Users**.
3. Open the exact device/PIN record.
4. Select the correct **Mapped Employee**.
5. Use **Map Past Punches** for previously unmapped raw evidence if needed.

Use **Fix Wrong Employee** only when an existing device/PIN mapping was wrong. Select **Correct Employee** from the authorized-companies-filtered public employee list; the wizard cannot create an employee. The correct employee can belong to a different company from the device, provided the Biometric Manager has access to **both** companies. If the person is missing, create their complete record in Employees first. Choose both local device dates; if no punches match, the tool changes nothing. Raw punches are scoped by the dates and device/PIN, and the current Odoo device-user mapping is updated. The tool never guesses across another device with the same PIN and never edits the physical terminal.

## Pull Attendance wizard

Open a Device and choose **Pull Attendance**.

- **From Date** and **To Date** define the complete business period to retrieve.
- **Device Request Range (Days)** controls how that period is split into smaller queued device requests.

Example:

```text
Selected period: 01 Oct → 31 Oct
Device Request Range: 7

Queued device ranges:
01–07
08–14
15–21
22–28
29–31
```

Changing the request range does not change the From/To dates.

## User update and transfer

From a Device User:

- **Refresh from Device** requests the latest cached user information for that PIN.
- **Update Device User** updates the same physical device/PIN using supported cached user fields.
- **Transfer to Device** is only for a different approved terminal.

Transfer validation blocks the same source/target device and blocks a target PIN already present in Odoo's refreshed target-user cache. A Biometric Manager can select an approved destination from **another assigned company** even with only the source company active in the company switcher; access to source company, destination company, and mapped employee company is checked server-side. Transferring does not change either device's owning company or the employee's company. Review the target refresh status shown by the transfer wizard before sending data.

## Timezone

Device timestamps are interpreted in `zk.device.tz` and converted to UTC for Odoo storage. An incorrect device timezone can shift punches into the wrong Odoo time or even the wrong work date.

The **Sync Timezone** action queues the supported ADMS timezone option. It does not open a direct LAN connection to the terminal.

## Security PUSH devices (`DeviceType=acc`)

A typical supported initialization is:

```text
GET  /iclock/cdata?SN=...&options=all&pushver=3.1.2&DeviceType=acc
POST /iclock/registry?SN=...
POST /iclock/push?SN=...
POST /iclock/cdata?SN=...&table=rtlog
```

Later polling details vary by firmware.
