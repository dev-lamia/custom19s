# TAM Universal Document Manager (Odoo 19)

A **single standalone module** for managing document types, nested folders, and multi-file document entries. No supplier dependency.

## Setup
1. Install this module only (`tam_document_manager`).
2. Assign **Document Manager** or **Document User** under Settings > Users > Access Rights.
3. Open **Document Manager > Document Types** and create a type.
4. Create any number of folders and nested folders within that type.
5. Open **Documents**, select a type and matching folder, and upload multiple files with the **Files** widget.

## Notes
- A document entry may contain multiple attachments. Multiple document entries can be stored per folder.
- Document User can create and edit folders/documents, but cannot delete them or configure types.
- Document Manager can manage all three models.
- Attachment visibility also follows Odoo's attachment security rules; test permissions for your deployment.
- This is a **new independent module**; it does not automatically migrate old supplier-document data.
- Source syntax and XML parsing checked; installation/runtime not verified in a running Odoo instance.
