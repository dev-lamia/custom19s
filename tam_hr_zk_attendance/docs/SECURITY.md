# Security

## v0.48 Security PUSH profile-photo controls

Only an existing approved `acc` device may submit `userpic` tabledata under the existing device-serial trust model. User pictures are personally identifying data; apply HTTPS, narrow Biometric Manager access, limited retention and protected Odoo filestore/backups. The upload validates count, base64, JPG structure, dimensions and size, then normalizes the photo to strip EXIF and stores it in the existing Device User image field. It never appears in the log body or template cache and never identifies an HR employee from a numeric PIN.

No additional device authentication was introduced in v0.48: the existing controller trusts an approved serial number, so production deployments should additionally enforce server/network safeguards and consider per-device authentication in a separately tested release. Invalid photo requests are *not* accepted with `200` to silence retries. A record that contains an unfamiliar source PIN can only create an unmapped, normal-privilege **device-specific cache record**, not a real employee.

## v0.47 access authorization and metadata protections

Security PUSH access rules are explicit security decisions: never copy source admin rights, card/password or assume time period 1 is safe. The wizard pre-fills it but requires manager confirmation before sending commands. The new authorization-only action is protected by the same Biometric Manager role, company permissions, target approval, PIN/name/privilege verification and pending-command checks as profile transfers. Command bodies (including biometric templates) remain private; only sanitized firmware/PUSH release identifiers are visible as diagnostic response. Do not treat unauthorized event 23 as a valid attendance punch.

## Public device routes

ZKTeco hardware calls `/iclock/*` without an Odoo user session, so the protocol routes use `auth="none"` and `csrf=False` where required by the hardware protocol.

A serial number identifies a terminal but is not a cryptographic credential. Security PUSH registry/session values are kept for protocol compatibility; they should not be treated as equivalent to strong device authentication.

## Two separate device gates

The Device form intentionally separates:

- **Approved Device**: required before sensitive user/template query or transfer commands are accepted/queued for that device.
- **Receive Attendance**: controls whether attendance payloads from the device are stored.

Newly discovered devices default to an unapproved/disabled state and should be reviewed before production use.

## Access model

### Biometric Operator

Can read, within allowed companies:

- Dashboard;
- Devices;
- raw Attendance Logs.

Operators do not receive manager-only Device User or Command History actions.

### Biometric Manager

Inherits operator access and can additionally:

- create/edit approved device configuration;
- manage Device User mappings;
- run historical mapping/correction wizards;
- queue supported attendance/user/template actions;
- view safe Command History status.

Record rules scope devices, device users, command history, and raw attendance to the user's allowed companies. These rules and existing group memberships have **not changed** to support cross-company employee mapping. An authorized manager may link an employee from another company only if their user account is allowed to access **both** companies. Device and raw punch company ownership always stays with the physical terminal, and the employee's HR company is not changed.

## Device/PIN mapping safety

A PIN is authoritative only together with its physical device. Incoming attendance is resolved using the exact `zk.device.user` record for that device + PIN. The deprecated `hr.employee.device_id_num` field is not public, is not imported from a device, and is not used to match attendance.

Unknown device PINs never create employees automatically. Their raw punches stay unmapped until a manager maps the correct Device User.

The **Fix Wrong Employee** wizard does not create employees either. The Correct Employee dropdown reads the public `hr.employee.public` directory across the manager's **permitted companies**, with both quick-create and form-create disabled. The backend checks access to the *device's* company, the device-user write ACL/record rules, and the *employee's* company and public-record visibility before narrowly elevating private employee resolution. The Device User form uses an `hr.employee.public` selector that updates the existing `employee_id` relation, and direct Device User employee assignments perform the same two-company/public-visibility checks. No global private HR read/write access is given to Biometric Managers. Date bounds and non-empty matching raw evidence are required before any correction. The employee may be employed elsewhere; raw evidence retains the physical device's company, while derived HR attendance is employee-centric.


## Transfer-derived employee mapping (v19.0.0.0.45)

A mapped source employee can follow an authorized **cross-company** device transfer without a second manual assignment, even when the destination company is not currently selected in the company switcher. Only the profile command stores private, immutable expected PIN/name/employee and requesting-manager references. Transfer requests require manager membership and explicit access to **both the source and destination device companies**, plus the mapped employee company. The wizard expands the selection context only to the logged-in user’s assigned companies; it does not give additional companies or record permissions. The mapping callback checks the original manager’s current group and company memberships again when the target device acknowledges its profile and returns a verified identity. The actual destination user must be read back from the terminal, retain normal privilege (`0`), and match the intended PIN/name; the device must have acknowledged its profile command as successful. The mapping write uses the original manager identity so server-side public-employee and both-company mapping checks still apply even though inbound PUSH requests run as public/protocol routes. Existing conflicting destination mappings are never overwritten. No ambient PIN lookup, automatic employee creation, retrospective bulk transfer mapping, or template/credential privilege copy is permitted. Command metadata fields are hidden from ordinary staff by the private protocol-service group.

## Biometric template handling

`zk.device.fingerprint` and `zk.device.biometric.template` are private protocol/cache models with no ordinary menu/view access. Template values are not written to normal application logs. The models have explicit ACL entries **only** for `group_biometric_protocol_internal` (Private Biometric Protocol Service), an internal group created **without any members or implied groups**. Do not assign it to users: it permits direct read access to biometric bytes. Biometric Operators, Biometric Managers, and standard internal users do not inherit these ACLs. Incoming device messages and authorized outbound synchronization use explicit server-side `sudo()` operations, as before.

The deprecated `zk.device.user.sync.wizard` model is retained for upgrades but has no view/action; its read-only ACL also belongs exclusively to that internal group. These ACL entries remove Odoo 19's missing-access warnings without granting ordinary staff biometric cache access.

The generic template cache can represent fingerprint, face, palm, and other types, but only observed fingerprint (`FP`) protocol operations are currently enabled. Face/palm/other transfer must remain disabled until the real device payload format is verified on physical hardware.

## Command payloads

Command History deliberately renders only safe operational fields such as device, business operation, state, timestamps, result code, and attendance import counters. Raw ADMS command text can contain biometric data and is intentionally absent from normal views.

## Raw attendance evidence

`zk.machine.attendance` is exposed as read-only Attendance Analysis for module users. Device, PIN, punch time, punch/status, and verification information are source evidence. Mapping/correction tools can change derived employee linkage only through controlled workflows.

## Elevated protocol processing

Public device ingestion uses privileged server-side access because there is no interactive user behind the terminal request. This makes device approval, Receive Attendance, multi-company assignment, and network protection important.

## Failure acknowledgement

Unexpected raw-storage failures return an error response instead of falsely acknowledging the payload as stored. Derived `hr.attendance` processing is isolated with savepoints so an HR-side validation failure can be logged without turning a valid device row into a guessed employee mapping.

## Deployment recommendations

Where possible:

- serve device-facing routes over HTTPS supported by the terminal firmware;
- restrict `/iclock/*` at the reverse proxy/firewall to expected device/NAT networks;
- do not enable proxy/request-body logging for biometric payload routes;
- limit Biometric Manager membership to administrators who genuinely need device-user synchronization.
