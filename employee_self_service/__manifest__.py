# -*- coding: utf-8 -*-
{
    'name': 'Employee Self-Service Portal',
    'version': '19.0.1.2.0',
    'category': 'Customizations',
    'summary': 'Employee Portal with Payroll, Attendance, Personal Details and Time Off',
    'description': """
        Employee Self-Service Portal for Odoo 19.
        Employees can log in to the website portal and view their:
        - Payslips / Salary Slips
        - Attendance Records (Check-in / Check-out)
        - Personal Details
        - Time Off Requests
    """,
    'author': 'Softeko_Lamia',
    'maintainer': 'Softeko',
    'depends': [
        'portal',
        'hr',
        'hr_payroll',
        'hr_attendance',
        'hr_holidays',
        'website',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/employee_portal_security.xml',
        'views/portal_templates.xml',
        'views/payslip_portal_templates.xml',
        'views/attendance_portal_templates.xml',
        'views/personal_details_portal_templates.xml',
        'views/timeoff_portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'employee_self_service/static/src/css/portal_style.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'website': 'https://www.softeko.co/',
    'support': 'contact@softeko.co',
}
