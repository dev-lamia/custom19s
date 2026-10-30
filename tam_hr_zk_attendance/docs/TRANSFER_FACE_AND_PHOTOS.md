> **Update for 19.0.0.0.61:** Classic ATT now supports bounded native legacy
> FACE and unified Type 9 BIODATA receive/transfer; see
> [CLASSIC_FACE_TRANSFER_61.md](CLASSIC_FACE_TRANSFER_61.md). This older
> document is preserved for historical changes and pre-.61 behavior.

# v0.53 — One-click profile, biometrics and photo transfer

For supported `acc` → `acc` transfers, click **Transfer to Device**, choose the target, confirm locally approved access Group 1 / Time Period 1 / Door 1 (change them when policy differs), tick the single confirmation and submit. The wizard preflights all cached biometric and photo payloads, queues identity-safe enrollment/authorization/verification and dependent compatible fingerprint/face/photo updates as one operation. Missing source picture/biometric cache is skipped and should be investigated before assuming transfer completeness. Existing matching normal users do not receive a duplicate profile. Always inspect Command History and test one employee physically. Photo-transfer `DATA UPDATE userpic` write support on the actual target firmware remains unverified; ACK/readback test required. Time Period 1 may authorize all hours. Never rely solely on its numerical ID for policy.

## Specialist repairs

If the destination already has a working user, choose authorization-only, face-only or photo-only repair only when required. Repair stages retain the same PIN/name/privilege/company checks, and never recreate a user. The source picture is not a face recognition template. The previous two manual steps are no longer necessary for standard transfers.


## v0.55 — pulling pictures and transferring selected users

Approved Security PUSH devices have a **Pull Profile Pictures** button on their
Device form. It queues exactly one `DATA QUERY tablename=userpic,fielddesc=*,filter=*`
for the terminal. The terminal may return all photos, a subset or no pictures;
firmware may return `-1` even if its `/iclock/querydata` upload succeeds.
Check individual `zk.device.user.image_1920` and Command History
**Records Received / Last Payload** separately from Return. Existing image
cache is not fabricated from photos on another device. A missing image after a
pull must be investigated on the destination terminal.

To transfer multiple users, navigate to **Device Users → List**, filter to the
source device, select up to **25** rows, then choose **Action → Transfer Selected
Users**. Choose one approved Security PUSH destination and confirm the access
policy; **Complete transfer** preflights identities, face/fingerprint
compatibility and source photos for all selected users before queuing any
commands. User chains are linked in sequence across the whole batch; a failed
command cancels dependent work rather than skipping ahead.

For users already enrolled and successfully punching on the target, use **Repair
photos for existing matching users only**. This queues only `DATA UPDATE
userpic` per selected user (after the same PIN/name/company checks). It does not
change group/time-period/door or resend any fingerprints or face templates.
The actual photo-upload command is firmware-dependent and must be read back
using the Pull Profile Pictures button after the terminal acknowledges it.
Do not assume that `DATA UPDATE userpic Return=0` guarantees a stored photo.

Classic ADMS (`att`) devices are not compatible with these Security PUSH
photo-query or batch-transfer actions. The device must have a separate profile
JPEG; a facial-recognition template is not the same thing.


### Protocol-aware actions (v0.58)

Classic (`att` or legacy ADMS without DeviceType) supports the same batch
selection UI as Security PUSH, but the command format differs. For Classic,
complete transfer writes the normal user, verifies USERINFO, and sends cached
fingerprint templates with ordered dependencies. Existing profile JPEGs can be
written via Classic DATA UPDATE USERPIC on supported firmware; check command
acknowledgement and physical screen. The Classic historical photo query and
face biometric template write are not verified and are not falsely reported
as completed. Mixed ACC/ATT biometric transfers remain disabled pending
algorithm/format compatibility validation.
