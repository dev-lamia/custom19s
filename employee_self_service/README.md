# Employee Self-Service Portal — Odoo 19 Custom Module

## ফিচার সমূহ

- **My Account পেজে** "My Payslips" টাইল যোগ হবে
- Employee তার সকল **validated/paid payslip** দেখতে পাবে
- প্রতিটি payslip এর **বিস্তারিত বেতন বিবরণ** দেখা যাবে (Allowance, Deduction, Net Pay)
- **PDF Download** করা যাবে সরাসরি পোর্টাল থেকে
- Security: প্রতিটি employee শুধু **নিজের** payslip দেখতে পাবে

---

## ইনস্টলেশন

### ধাপ ১: Module কপি করুন
```bash
cp -r employee_self_service /path/to/odoo/custom_addons/
```

### ধাপ ২: odoo.conf আপডেট করুন
```ini
addons_path = /path/to/odoo/addons,/path/to/odoo/custom_addons
```

### ধাপ ৩: Odoo রিস্টার্ট করুন
```bash
sudo systemctl restart odoo
```

### ধাপ ৪: Module ইনস্টল করুন
1. **Settings > Technical > Update Apps List** করুন
2. Apps-এ গিয়ে `Employee Self-Service Portal` খুঁজুন
3. **Install** বাটনে ক্লিক করুন

---

## Employee এর Portal User সেটআপ

Employee কে portal access দিতে:

1. **Employees** অ্যাপে যান
2. Employee খুলুন → **Action** → **Grant Portal Access**
3. Employee এর `user_id` ফিল্ডে portal user সেট করুন

**অথবা**

Employee এর Work Email দিয়ে portal user তৈরি করুন — module স্বয়ংক্রিয়ভাবে match করবে।

---

## Dependencies

| Module | কারণ |
|--------|-------|
| `portal` | Portal framework |
| `hr` | Employee model |
| `hr_payroll` | Payslip model |
| `website` | Website rendering |

---

## URL Routes

| URL | বিবরণ |
|-----|--------|
| `/my/home` | My Account (payslip tile যোগ হবে) |
| `/my/payslips` | Payslip তালিকা |
| `/my/payslips/<id>` | একটি payslip এর বিস্তারিত |
| `/my/payslips/<id>/download` | PDF ডাউনলোড |

---

## সমস্যা হলে

**Payslip দেখা যাচ্ছে না?**
- Employee record এ `user_id` সেট আছে কিনা চেক করুন
- Payslip এর state `done` বা `paid` আছে কিনা দেখুন

**PDF কাজ করছে না?**
- `hr_payroll` module এ payslip report template আছে কিনা দেখুন
- wkhtmltopdf ইনস্টল করা আছে কিনা চেক করুন
