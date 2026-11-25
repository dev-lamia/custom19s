# Employee Self-Service Portal — Odoo 19 Custom Module

## Features

- A "My Payslips" tile will be added to the **My Account page**
- Employees can view all their **validated/paid payslips**
- Employees can view the **detailed salary breakdown** of each payslip (Allowance, Deduction, Net Pay)
- **PDF downloads** are available directly from the portal
- Security: Each employee can only view **their own** payslips

---

## Installation

### Step 1: Copy the Module
```bash
cp -r softeko_employee_self_service /path/to/odoo/custom_addons/
```

### Step 2: Update odoo.conf
```ini
addons_path = /path/to/odoo/addons,/path/to/odoo/custom_addons
```

### Step 3: Restart Odoo
```bash
sudo systemctl restart odoo
```

### Step 4: Install the Module
1. Go to **Settings > Technical > Update Apps List**
2. Go to Apps and search for `Employee Self-Service Portal`
3. Click the **Install** button

---

## Employee Portal User Setup

To grant portal access to an employee:

1. Go to the **Employees** app
2. Open the employee record → **Action** → **Grant Portal Access**
3. Set the portal user in the employee's `user_id` field

**Alternatively**

Create a portal user using the employee's Work Email — the module will automatically match the user.

---

## Dependencies

| Module | Purpose |
|--------|---------|
| `portal` | Portal framework |
| `hr` | Employee model |
| `hr_payroll` | Payslip model |
| `website` | Website rendering |

---

## URL Routes

| URL | Description |
|-----|-------------|
| `/my/home` | My Account (payslip tile will be added) |
| `/my/payslips` | Payslip list |
| `/my/payslips/<id>` | Details of an individual payslip |
| `/my/payslips/<id>/download` | PDF download |

---

## Troubleshooting

**Payslips are not visible?**
- Check whether `user_id` is set on the employee record
- Check whether the payslip state is `done` or `paid`

**PDF download is not working?**
- Check whether the payslip report template exists in the `hr_payroll` module
- Check whether wkhtmltopdf is installed
