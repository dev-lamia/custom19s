# RM Quality — Simple Checks & Sampling (Odoo 19)

- **Technical addon:** `quality_rm_spec_sampling`
- **Version:** 19.0.1.0.12
- **Updated:** 2026-11-09
- **Source:** supplied workbook `RM Master_QC_Specification_With_Sampling.xlsx`
- **Extends:** standard Odoo `quality.check`, `product.template`, `stock.picking`, `mrp.production`
- **Status:** Python/XML/ZIP static checks done; **not live-tested in an Odoo database**.

## Daily user workflow (no TDS)

**Incoming RM:**

1. On the purchased product, open the single **RM Quality** tab: tick **QC Required**, choose Material Type and Film Grade (if a film). Enter optional basic technical property values.
2. A QC administrator maintains test limits, sampling and methods in **RM Quality → Configuration → QC Test Rules**. The 21 incoming QC parameters supplied by the workbook are seeded as initial reference rules. This is configuration, *not* an activation or approval workflow.
3. Use normal Odoo **RFQ → Purchase Order → Receipt**. This addon **does not block PO confirmation based on a TDS or approval**.
4. On the receipt, click **QC Inspection**. The addon creates/reuses an existing Odoo `quality.check` for each QC-required received product/lot, copying the applicable master test rules into permanent snapshots and creating the expected sample rows.
5. In **QC Inspections**, click **Enter Results** per test, record readings or manual results, and choose **Pass** or **Fail**. A check cannot Pass with incomplete/failed readings. Quality Check results do **not** automatically hold stock, scrap, return or block receipt validation.

**Production:** Manufacturing Order → **Production QC** → select process stage → **Open QC Check** → enter readings and Pass/Fail. The workbook's 45 process QC parameters drive stage-specific tests; the addon does not automatically stop production.

## Sample rules and formulas

- The importer copies the source workbook's sampling rules. The first explicit number in `5 Rolls / Pallet` is a **per-base-unit initial count**, not a complete lot-wide sampling calculation. Adjust the **Number of Samples** for the actual receipt. A rule like `All Rolls Sampled` requires an actual count from the inspector.
- When both reference limits are plain numbers, measurements use numeric comparison (inclusive limits).
- For `Nominal - 5% / Nominal + 5%`, **Film Thickness** numeric limits can be resolved from the matching Product property **Thickness / Gauge**. E.g., nominal 120 → minimum 114 and maximum 126. Film Grammage can be resolved only if a matching **Grammage / Basis Weight** product property is configured and populated. Other unmatched formula/reference limits remain **Manual**, never an invented automatic Pass.
- A manually assessed test requires a nonempty reading and an explicit Manual Pass or Fail.
- Defect codes `RM001–RM020` are selected only for observed defects.
- **AQL lot acceptance** and **stock disposition** are not inferred from incomplete source rules.

## Configuration

- **QC Test Rules:** source workbook's 21 incoming and 45 production tests, including scope, material/stage, units, limits and sampling.
- **Defect Codes:** the 20 source workbook error descriptions.
- **Product Properties:** per-category technical identification fields, automatically shown on each product.
- **Consumable Allocation:** reference matrix (43 source entries), not a QC test flow.

## Legacy / upgrade safety

This version **removes the TDS/QCS process from the user interface and business workflow**. Previously installed `rm.qc.specification` and related database models, form definitions, sequences and historical relations are retained **only for safe upgrade and existing data**. No new QC check is generated from QCS/TDS. Existing recorded checks remain accessible for audit, and previously approved QCS records are not deleted or migrated into new rules.

**Important:** Any previously edited, product-specific QCS limits are **not automatically carried over** to global test rules. Review the Test Rules and product properties before a new live inspection, especially for formula-based limits. Existing historical checks retain their own saved snapshot readings and limits.

**Installation/upgrade:** Back up database and filestore, replace the addon folder, restart Odoo, upgrade the existing addon (do not uninstall), refresh browser. Test a QC-required film product, an incoming receipt, an Out of Spec measurement and a production stage in a staging DB before production rollout.

**Security:** The existing broad Internal User ACLs are retained as requested in earlier versions. Menu hiding is not a security boundary; use model-level ACLs when tightening access later.
