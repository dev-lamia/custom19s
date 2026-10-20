# Flexible Chatter Panel

Odoo 19 backend UI module for form chatter.

Features:

- Responsive mode: form + chatter side by side; when a PDF/attachment preview is open, chatter stacks below the form inside the left pane.
- Bottom mode: moves the chatter below the form sheet at runtime.
- Drag resize in side/responsive mode.
- Floating hide/show button.
- When hidden, the chatter is removed from layout so the form fills the full available pane (full form pane normally, left pane while PDF preview is open).
- Browser localStorage saves mode, width, and hidden state.

This module is frontend-only and does not add models, menus, or database tables.


## 19.0.1.0.11
- Keep the responsive chatter toggle inside the left form pane while a PDF preview is open.
- Remove horizontal overflow from the PDF-preview left form pane.
- Bottom mode behavior remains unchanged.

- PDF preview split: form/chatter pane 75%, PDF pane 25% (3:1).
