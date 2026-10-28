from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class RmQcPurchaseRequest(models.Model):
    _name = 'rm.qc.purchase.request'
    _description = 'RM / Consumable Purchase Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='PR Reference', default='New', required=True,
                       readonly=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, string='Company',
                                 default=lambda s: s.env.company)
    requested_by = fields.Many2one('res.users', string='Requested by',
                                   default=lambda s: s.env.user, required=True)
    requested_on = fields.Date(string='Request Date', default=fields.Date.context_today)
    origin_department = fields.Char(string='Department / Planner')
    partner_id = fields.Many2one('res.partner', string='Vendor',
                                 domain="[('supplier_rank','>',0)]")
    state = fields.Selection([
        ('draft', 'Draft'), ('submitted', 'Submitted for Approval'),
        ('approved', 'Manager Approved'), ('ordered', 'RFQ Created'),
        ('cancelled', 'Cancelled')], default='draft', required=True,
        string='Status', tracking=True)
    line_ids = fields.One2many('rm.qc.purchase.request.line', 'request_id',
                               string='Purchase Requisition Lines')
    approved_by = fields.Many2one('res.users', string='Approved by', readonly=True)
    approved_on = fields.Datetime(string='Approved On', readonly=True)
    purchase_order_id = fields.Many2one('purchase.order', string='Generated RFQ', readonly=True)
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('rm.qc.purchase.request') or 'New'
        return super().create(vals_list)

    def _can_approve_pr(self):
        """Allow PR approvers and Odoo administrators to approve requisitions."""
        return (
            self.env.is_admin()
            or self.env.is_system()
            or self.env.user.has_group(
                'quality_rm_spec_sampling.group_rm_qc_pr_approver'
            )
        )

    def write(self, vals):
        if vals.get('state') == 'approved' and not self._can_approve_pr():
            raise UserError(_(
                'Only a PR Approver or an Administrator may approve a requisition.'
            ))
        if {'line_ids'}.intersection(vals) and any(r.state != 'draft' for r in self):
            raise UserError(_('Requisition lines cannot change after submission.'))
        return super().write(vals)

    def _check_approved_rm(self):
        Spec = self.env['rm.qc.specification']
        for rec in self:
            for line in rec.line_ids:
                if line.product_id.rm_qc_required and not Spec.with_company(rec.company_id)._find_approved(line.product_id):
                    raise UserError(_('RM %s requires QC Manager confirmed TDS / Sampling '
                                      'before PR approval.') % line.product_id.display_name)

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft' or not rec.line_ids:
                raise UserError(_('Only nonempty draft PRs may be submitted.'))
        self._check_approved_rm()
        self.write({'state': 'submitted'})
        return True

    def action_approve(self):
        if not self._can_approve_pr():
            raise UserError(_(
                'Only a PR Approver or an Administrator may approve a requisition.'
            ))
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Submit the PR before approving.'))
        self._check_approved_rm()
        self.write({'state': 'approved', 'approved_by': self.env.user.id,
                    'approved_on': fields.Datetime.now()})
        return True

    def action_create_rfq(self):
        if not self.env.user.has_group('purchase.group_purchase_user'):
            raise UserError(_('Purchase User permission is required to create an RFQ.'))
        self.ensure_one()
        if self.state != 'approved' or self.purchase_order_id:
            raise UserError(_('The PR must be approved and not yet ordered.'))
        if not self.partner_id:
            raise UserError(_('Select a Vendor before generating the RFQ.'))
        self._check_approved_rm()
        lines = []
        for line in self.line_ids:
            lines.append(fields.Command.create({
                'product_id': line.product_id.id,
                'name': line.product_id.display_name,
                'product_qty': line.quantity,
                'product_uom_id': line.uom_id.id,
                'price_unit': line.price_unit,
                'date_planned': fields.Datetime.now(),
            }))
        po = self.env['purchase.order'].create({
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'origin': self.name,
            'order_line': lines,
        })
        self.write({'purchase_order_id': po.id, 'state': 'ordered'})
        return {'type': 'ir.actions.act_window', 'res_model': 'purchase.order',
                'res_id': po.id, 'view_mode': 'form', 'target': 'current'}

    def action_cancel(self):
        if any(rec.state == 'ordered' for rec in self):
            raise UserError(_('Cancel the RFQ manually before cancelling this PR.'))
        self.write({'state': 'cancelled'})
        return True


class RmQcPurchaseRequestLine(models.Model):
    _name = 'rm.qc.purchase.request.line'
    _description = 'Purchase Requisition Material Line'

    request_id = fields.Many2one('rm.qc.purchase.request', required=True,
                                 ondelete='cascade', string='PR')
    product_id = fields.Many2one('product.product', required=True, string='Material')
    quantity = fields.Float(string='Quantity', default=1, required=True)
    uom_id = fields.Many2one('uom.uom', string='UOM', required=True)
    price_unit = fields.Float(string='Estimated Unit Price', digits='Product Price')
    qc_required = fields.Boolean(related='product_id.rm_qc_required',
                                 string='QC Required', readonly=True)

    @api.onchange('product_id')
    def _onchange_product(self):
        for rec in self:
            if rec.product_id:
                rec.uom_id = rec.product_id.uom_id

    @api.constrains('quantity')
    def _check_qty(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError(_('Requested quantity must be positive.'))

    def write(self, vals):
        if any(rec.request_id.state != 'draft' for rec in self):
            raise UserError(_('PR lines can only be edited in Draft.'))
        return super().write(vals)

    def unlink(self):
        if any(rec.request_id.state != 'draft' for rec in self):
            raise UserError(_('PR lines can only be removed in Draft.'))
        return super().unlink()


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_confirm(self):
        Spec = self.env['rm.qc.specification']
        for order in self:
            for line in order.order_line.filtered(lambda l: not l.display_type and l.product_id.rm_qc_required):
                if not Spec.with_company(order.company_id)._find_approved(line.product_id):
                    raise UserError(_('Cannot confirm PO %s: %s has no QC Manager-confirmed '
                                      'Incoming RM Specification.')
                                    % (order.name, line.product_id.display_name))
        return super().button_confirm()
