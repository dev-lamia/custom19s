# Manual test cases

Use an internal user unless a role is explicitly stated. Run expiry tests in a test database or with controlled dates. Save records where a constraint or confirmation result must be verified.

| ID | Test | Setup / Input | Steps | Expected result |
|---|---|---|---|---|
| TSD-01 | Create type | Internal user | Create a Document Type with a name | Type is saved and appears by sequence/name. |
| TSD-02 | Deactivate type | Existing type | Set Active false | Type is excluded from implemented selectors. |
| TSD-03 | Sequence | Two types with different sequences | Open type list / selector | Lower sequence is ordered first. |
| TSD-04 | Sales-only type | `sale_ok` true; others false | Open SO document Type selector | Type is selectable on SO, not PO/vendor selectors. |
| TSD-05 | Purchase-only type | `purchase_ok` true; others false | Open PO document Type selector | Type is selectable on PO, not SO/vendor selectors. |
| TSD-06 | Vendor-only type | `vendor_ok` true; others false | Open vendor document Type selector | Type is selectable on vendor, not SO/PO selectors. |
| TSD-07 | Multi-use type | Sales, Purchase, Vendor true | Check all three selectors | Type is selectable in all enabled areas. |
| TSD-08 | Customer flag only | `customer_ok` true; other flags false | Inspect all module document areas | No module selector uses the type; no separate customer-document area exists. |
| TSD-09 | Vendor tab visibility | Partner with `supplier_rank > 0` | Open partner | Vendor Documents tab is visible. |
| TSD-10 | Non-vendor tab visibility | Partner with `supplier_rank = 0` | Open partner | Vendor Documents tab is hidden. |
| TSD-11 | Vendor type filtering | Vendor-only and non-vendor types | Add Vendor Document | Only active `vendor_ok` types are selectable. |
| TSD-12 | Vendor upload | Vendor document | Choose type, description, and file; save | File and metadata persist. |
| TSD-13 | Vendor expiry metadata | Vendor document | Set expiry date, department, stop setting | Values persist; Last Notified On remains system-managed. |
| TSD-14 | Purchase type filtering | Purchase-only and sales-only types | Add PO Supplier Document | Only active `purchase_ok` types are selectable. |
| TSD-15 | Purchase uploads | Purchase Order | Add two Supplier Documents with files | Both lines and files persist. |
| TSD-16 | Sales type filtering | Sales-only and purchase-only types | Add manual SO document | Only active `sale_ok` types are selectable. |
| TSD-17 | Manual SO line preserved | SO with manual document | Change Related Purchase Orders | Manual line remains after onchange rebuild. |
| TSD-18 | PO-to-SO copy | PO-001: Certificate A/B; PO-002: Certificate C | Select both POs on SO | Three generated SO lines exist, each with Source PO and source Purchase Document. |
| TSD-19 | Remove related PO | Result of TSD-18 | Remove PO-001 | PO-001-derived lines disappear; PO-002 and manual lines remain. |
| TSD-20 | Repeated PO selection | PO with one document | Trigger related-PO onchange repeatedly | Rebuild does not add duplicate `(PO, document)` lines. |
| TSD-21 | Reminder at 31 days | Vendor document expires in 31 days | Run cron | No reminder activity is created. |
| TSD-22 | Reminder at 30 days/today | Valid department manager/user; documents at +30 and today | Run cron | A To-Do activity is created on each vendor contact. |
| TSD-23 | Expired reminder | Document expired yesterday | Run cron | No reminder activity is created. |
| TSD-24 | Stopped reminder | In-window document with Stop Notifications true | Run cron | No reminder activity is created. |
| TSD-25 | Missing recipient | In-window documents: no department, no manager, or manager without user | Run cron | No activity is created for each incomplete recipient path. |
| TSD-26 | Same-day cron | Valid in-window document | Run cron twice on one date | Only the first run schedules an activity; `last_notified_on` prevents a duplicate. |
| TSD-27 | Next-day cron | Valid document remains in window after TSD-26 | Run cron on the following date | A new reminder may be scheduled; suppression is per day, not once overall. |
| TSD-28 | Expiry blocking boundaries | Vendor docs: expired, today, +15, +30, +31, and no date | Open/confirm PO for vendor | All except +31/no-date are in the affected type set and block confirmation. |
| TSD-29 | Stop does not unblock | Affected Vendor Document with Stop Notifications true | Attempt PO confirmation | Confirmation remains blocked. |
| TSD-30 | UI blocking | Vendor has affected type | Open draft/sent PO | Warning lists affected types and Confirm button is hidden. |
| TSD-31 | Server validation | Vendor has affected type | Invoke/attempt `button_confirm()` through an authorized non-UI path | `UserError` prevents confirmation. |
| TSD-32 | ACLs | Normal internal user | Access the four custom models via their available interfaces | Full CRUD is granted by this module’s `base.group_user` ACLs; parent-menu visibility may vary. |
