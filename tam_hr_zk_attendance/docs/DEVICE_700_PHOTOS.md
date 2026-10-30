# Device 700 — single-device photo diagnostics (v19.0.0.0.51)

The device is `AJE1261000700`, Classic Attendance PUSH (`att`). A visible-light face template and a display/profile JPG (`USERPIC`) are **not** synonymous. PIN 1002 may have face recognition enabled without a separately stored profile portrait.

On all **approved Classic `att`** devices the module now advertises `TransFlag=1111000001` as part of their next standard `/iclock/cdata?options=all` handshake. There is no checkbox. `CHECK` is a documented Classic command to refresh server options; `LOG` asks to transmit new data. These commands are not a documented historical USERPIC pull. `CHECK` may provoke reuploads depending on device marks; use one device at a time with a tested deduplicating receiver, and only after backing up DB + filestore in a quiet window.

## Queue CHECK, then optionally LOG

In an **Odoo shell** on the upgraded database, run this once with `COMMAND='CHECK'`. After reviewing Command History, rerun with `COMMAND='LOG'` if needed. The serial, approval, protocol and active-command checks prevent accidental cross-device work. The only side effect is a queue item; device-triggered reuploads may follow.

```python
exec("""
import time
from psycopg2 import errorcodes

SN = 'AJE1261000700'
COMMAND = 'CHECK'  # Later change to 'LOG' to request newly available uploads
assert COMMAND in ('CHECK', 'LOG')

for attempt in range(1, 5):
    try:
        env.cr.rollback()
        env.invalidate_all()
        Device = env['zk.device'].sudo()
        Commands = env['zk.device.command'].sudo()
        device = Device.search([('serial_number', '=', SN)], limit=1)
        if not device or not device.is_approved or device.device_type != 'att':
            print('STOP: Missing, unapproved or not a Classic ATT device')
            break
        pending = Commands.search_count([
            ('device_id', '=', device.id),
            ('state', 'in', ['pending', 'sent']),
        ])
        if pending:
            print('STOP: Existing active commands:', pending)
            break
        cmd = device.queue_adms_command(
            COMMAND,
            'Diagnostic 700 Classic photo ' + ('options refresh' if COMMAND == 'CHECK' else 'new data check'),
        )
        cmd_id = cmd.command_id
        env.cr.commit()
        print('QUEUED', COMMAND, 'for', SN, 'command_id=', cmd_id)
        break
    except Exception as exc:
        code = getattr(exc, 'pgcode', None)
        env.cr.rollback()
        env.invalidate_all()
        if code == errorcodes.SERIALIZATION_FAILURE:
            if attempt == 4:
                print('STOP: device record busy; try later')
                break
            time.sleep(attempt)
        else:
            raise
""")
```

## Read-only result check

```python
env.cr.rollback()
env.invalidate_all()
SN = 'AJE1261000700'
PIN = '1002'
device = env['zk.device'].sudo().search([('serial_number', '=', SN)], limit=1)
if not device:
    print('Device not found')
else:
    user = env['zk.device.user'].sudo().search([('device_id', '=', device.id), ('pin', '=', PIN)], limit=1)
    print('Device:', device.serial_number, 'type:', device.device_type)
    print('PIN:', PIN, 'name:', user.name if user else 'NOT CACHED')
    print('Actual USERPIC JPEG cached:', bool(user.image_1920) if user else False)
    ts = env['zk.device.biometric.template'].sudo().search([
        ('device_id', '=', device.id), ('pin', '=', PIN),
    ])
    print('Biometric types cached (NOT photos):', sorted(set(ts.mapped('biometric_type'))))
    commands = env['zk.device.command'].sudo().search([
        ('device_id', '=', device.id),
        ('operation', 'ilike', 'Diagnostic 700 Classic photo%'),
    ], order='id desc', limit=5)
    for cmd in commands:
        print('Command',cmd.command_id,'type',cmd.operation,'state',cmd.state,'return',cmd.return_code,'payload',cmd.last_payload_at)
```

Watch for `POST /iclock/cdata?...table=OPERLOG` and `ZK OPERLOG stored: ... pictures=1`. An `OPERLOG users=1` or `fingerprints=2` does not mean a picture was uploaded. If the physical terminal contains a verified photo but **nothing** is sent by CHECK/LOG, the model/firmware may require USB user-portrait export. Do not send `DATA DELETE USERPIC`, `CLEAR`, `REBOOT`, reset timestamps, or change `att` to `acc` to obtain an image. A speculative `DATA QUERY USERPIC PIN=1002` is not documented for Classic ADMS; do not label an ACK or `-1` as photo success without a USERPIC packet.
