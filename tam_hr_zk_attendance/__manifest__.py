# -*- coding: utf-8 -*-
{
    'name': 'Biometric Attendance — ZKTeco ADMS',
    'version': '19.0.0.0.62',
    'category': 'Human Resources/Attendances',
    'summary': 'Secure ADMS attendance, device+PIN employee mapping, correction safeguards, and private biometric synchronization and single-click validated protocol-aware user/biometric/photo transfers.',
    'description': """ZKTeco Biometric Attendance (ADMS)
===================================

Receive attendance data from ZKTeco terminals through their outbound ADMS/PUSH
connection. The module keeps auditable raw attendance events, maps device PINs
to employees, and synchronizes standard Odoo attendances.

Key capabilities
----------------
* Classic ATTLOG and Security PUSH RTLOG reception.
* Protocol-aware Security PUSH user/biometric pulls, bounded JPG user-photo upload, and private template caching.
* Device registration, timezone-aware timestamp conversion, and manual device
  location tracking.
* ADMS command queue for supported terminals: query users, query attendance,
  update users, and synchronize fingerprint templates.
* Unknown PINs are retained as raw evidence; employees are never created from
  unauthenticated device traffic.
* Biometric templates are not exposed in views or request logs.
* Approved-device controls, multi-company isolation, and read-only raw evidence.
* Controlled historical mapping and correction scoped to exact device + PIN + local dates.
* Provenance-protected biometric attendance rebuilds; manual and uncertain history stays untouched.
* Classic Attendance PUSH Type 9 unified face-template writes, with matched-algorithm preflight; terminal-side enrollment needs physical verification.
* Source admin users are enrolled as normal users (Pri=0) on compatible destinations. Palm is not transferred.

ADMS is device-initiated: Odoo never needs inbound access to a terminal's LAN
IP address. Supported devices poll the configured Odoo endpoint for commands.
""",
    'author': 'Softeko_RIFAT',
    'company': 'Softeko',
    'maintainer': 'Softeko',
    'website': "https://www.softeko.co/",
    'depends': ['base_setup', 'hr_attendance'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'views/dashboard_views.xml',
        'views/attendance_pull_wizard_views.xml',
        'views/attendance_mapping_wizard_views.xml',
        'views/device_user_transfer_wizard_views.xml',
        'views/device_user_batch_transfer_wizard_views.xml',
        'views/device_user_views.xml',
        'views/zk_device_views.xml',
        'views/machine_attendance_views.xml',
        'views/biometric_device_attendance_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'tam_hr_zk_attendance/static/src/scss/biometric_dashboard.scss',
        ],
        'web.assets_backend_lazy_dark': [
            'tam_hr_zk_attendance/static/src/scss/biometric_dashboard.dark.scss',
        ],
    },
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
