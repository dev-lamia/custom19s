# Classic ATT face transfer (19.0.0.0.61)

## Why this change

Prior releases rejected the entire Classic/legacy ADMS *Complete transfer*
when a user's cached Security PUSH unified `biodata` included a face template.
The ZKTeco **Attendance PUSH Communication Protocol (2020)** documents the
unified `DATA UPDATE BIODATA Pin=...\tNo=...\tIndex=...\tValid=...\tDuress=...\tType=9\tMajorVer=...\tMinorVer=...\tFormat=0\tTmp=...`
command for visible-light face templates, alongside a distinct older
`DATA UPDATE FACE` legacy format. These formats are **not interchangeable**.

## New behaviour

- Two Classic-compatible terminals (`att` or unknown Classic legacy) can perform
  a `full` transfer: normal-role profile (`Pri=0`, even if source is admin),
  destination USERINFO verification, Classic FP records, compatible native
  Type 9 unified face records, and optional USERPIC photo, in that order.
- Matching target normal users are not overwritten; biometric/photo repair
  can be run on them.
- `face_only` sends only the matching user's cached native Type 9 face
  templates. It never silently resends a photo, fingerprint or privilege.
- Bulk transfer preflights all selected records before queuing any command,
  chains every per-user command across the batch, and aborts if a conflicting
  PIN, unsupported template, missing biometrics (face-only), or mismatched
  algorithm is found. The limit remains 25 selected users per batch.
- Security PUSH bulk profile creation is chained to the previous user's last
  operation (fixing an ordering gap).
- Device permission and company checks are unchanged.

## Firmware-dependent limitations

- **Pull Face Templates (ATT)** queues `DATA QUERY BIODATA Type=9` only for
  an approved Classic terminal, and caches the returned Type 9 templates from
  `/iclock/cdata?table=BIODATA`. Device firmware may decline this query.
- Legacy `FACE PIN=... FID=... SIZE=... TMP=...` enrollment uploaded in Classic
  `OPERLOG` is retained in its original legacy form and replayed with the
  documented `DATA UPDATE FACE` command, not converted to unified BIODATA.
  For legacy native replay, both devices must advertise the same face version.
- Native Type 9 transfer requires a complete cached biometric record with
  base64 body, original slot metadata, and source/target registry metadata
  advertising identical face algorithm versions and adequate package size.
- Unsupported other FACE encodings, palms, or incomplete/mismatched metadata
  are blocked, not silently ignored or converted.
- Some Classic firmware does not implement the unified BIODATA update command.
  **Device `Return=0` proves command acknowledgement only**. Physically
  verify actual face recognition and enrolled-face count on the destination.
- The cached `registry_payload` may predate switching an ACC device to ATT;
  update the firmware registration metadata where possible before production
  use. Never fake `MultiBioVersion` in the database to bypass the check.
- Physical access authorization is distinct from ordinary-user privilege;
  this module does not copy source permissions/password/cards/door rights.
- A previous failure in the device's inbound BIODATA parser (HTTP 400) is
  independent of this outbound feature and is not altered by this patch.
- Install/upgrade in staging and test a single identity physically before a
  large production batch. Existing queued commands are untouched by upgrade.

## Release checklist

1. Back up Odoo database and the original addon; apply ZIP to the addon path.
2. Upgrade `tam_hr_zk_attendance` in Odoo 19.
3. Refresh destination user inventory and confirm no PIN collision.
4. Test one PIN with cached Type 9 face and check Command History + physical
   terminal face recognition.
5. Use batch only after the single-user test, with no active target commands.
