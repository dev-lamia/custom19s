from odoo import models, fields


class RmQcConsumableAllocation(models.Model):
    _name = 'rm.qc.consumable.allocation'
    _description = 'Department Consumable Allocation Matrix (Reference)'
    _order = 'name'

    name = fields.Char(string='Consumable / Material', required=True)
    cadence = fields.Selection([
        ('rop', 'As per ROP'), ('once', 'Single time'), ('mixed', 'Mixed')
    ], string='Allocation Cadence', required=True)
    printing = fields.Boolean(string='Printing')
    lamination = fields.Boolean(string='Lamination')
    slitting = fields.Boolean(string='Slitting')
    pouching = fields.Boolean(string='Pouching')
    valving = fields.Boolean(string='Valving')
    production = fields.Boolean(string='Production')
    planning = fields.Boolean(string='Planning')
    quality = fields.Boolean(string='Quality')
    sales = fields.Boolean(string='Sales')
    stores = fields.Boolean(string='Stores')
    inks = fields.Boolean(string='Inks')
    prepress = fields.Boolean(string='Prepress')
    note = fields.Char(string='Notes', default='Reference matrix only; 1/0 values are applicability flags.')
