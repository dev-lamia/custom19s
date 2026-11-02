# Product Job Specification (Odoo 19)

Adds Product Specification tab to `product.template` (Sales / Products / Products).

## Relationship

`spec_job_id` is a Many2one to `sale.job.code.configuration` with the visible Job Code as record name. This is a selectable dropdown, not a fixed Selection list, because codes are database records.

Other values are read-only, non-stored computed fields pulled from the selected Job Code. They update on opening and on changing the dropdown.

## Mapping

| Product field | Job Code field |
|---|---|
| Design Name | design_name |
| Job Code | job_code (selected record) |
| Customer Name | partner_id |
| Customer Code | partner_id.customer_code |
| One Up Size | job_one_up_size |
| No. of Ups | job_number_of_ups |
| One Repeat Size | job_one_repeat_size (optional in deployed versions) |
| No. of Repeats | job_number_of_repeats |
| Circumference | job_circumference |
| Print Width | job_print_area |
| Film Width | job_film_size_to_be_used |
| Sleeve Size | job_sleeve_size |

No extra access groups are added. Existing product access control and Job Code read access still apply.

The uploaded crm_requirement_form(1).zip lacks `job_one_repeat_size` on the Job Code model. To avoid upgrade errors, the compute reads it only when registered; without it, value is 0.0. Validate live-field mapping if necessary.
