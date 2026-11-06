# Product RM TDS — Odoo 19

Adds a tab on non-Plate `product.template` records with three repeatable lists:

- Dimensions & Physical Properties
- Material & Surface Treatment
- Barrier & Quality Metrics

Each list has Property and a single numeric Value (Float, 4 decimal places).
Properties are unique across the three categories (not unique per product; multiple rows
of the same property are allowed).

## Upgrade notes

Replaces the previous single-value/legacy columns in the *view* only. Database fields
are intentionally retained, including `value_text`, to avoid destroying historic data.
Migration `19.0.1.3.0` copies whole-number values to `value_float` and moves legacy
Treatment Level and Substrate Grade lines to the correct category. It converts a legacy
text value only when the text is a valid single number. Non-numeric text such as `PET`
or `38-42` remains preserved in a hidden legacy column and cannot meaningfully be shown
as a Float. Review/convert those records manually if necessary.

Keep the previous module directory name `product_rm_tds`, upgrade through Apps,
and verify a database backup before migrating production.

Depends on `project_plate_tds` because that module defines the `is_plate` flag.


## Product duplication (19.0.1.5.0)
- Three RM TDS One2many fields explicitly use `copy=True` on `product.template`. When a product template is duplicated, independent RM TDS line records are created with the same property reference and editable values.
- RM TDS tab is also exposed on `product.product` (Product Variants). The data belongs to the product template and is shared by variants of the same template. When the standard variant Duplicate operation creates a distinct product template, that template also receives independent copied lines.
- Property option records are reused; they are not duplicated.
- Verify product-template and product-variant duplication in your exact Odoo instance, especially for multi-variant products and customized duplicate overrides.
