# Artwork Project Flow (Odoo 19)

## Overview
From a confirmed and invoiced Sales Order, click **Create Artwork**. Select one or more **Job Codes** belonging to the Sales Order, choose a **Project Template**, and click **Create Projects**. A separate project and one task are created for each selected Job Code.

## Key behavior
- Only Job Codes from the active Sales Order appear in the wizard.
- Job Codes already linked to artwork tasks cannot be created again.
- The Create Artwork button stays available while unprocessed Job Codes remain.
- Each new project stores `artwork_template_id`, displayed on Project Kanban cards.
- Copied sample tasks from the template are removed and replaced by one task linked to the source Sales Order Line.

## Installation
Place the `artwork_project` directory on the addons path, update Apps, and upgrade **Artwork Project Flow**. Confirm that the `crm_requirement_form` SQL view `sale.job.code.configuration` is installed and populated.

## Verification
1. Confirm a Sales Order containing two Job Codes and post a customer invoice.
2. Click Create Artwork. Choose just one Job Code and a template.
3. Verify only one project/task is created, and its Kanban card shows the template.
4. Reopen Create Artwork for the remaining Job Code, and verify no duplicates.

## Notes
The wizard uses `sale.job.code.configuration`, a SQL view whose records must map to the source Sales Order Line. Existing artwork projects created before this feature will not have a template value unless assigned separately.
