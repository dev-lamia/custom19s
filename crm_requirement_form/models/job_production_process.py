from odoo import fields, models


class JobProductionProcess(models.Model):
    _name = 'crm.job.production.process'
    _description = 'Job Production Process Option'
    _order = 'sequence, id'

    name = fields.Char(string='Process', required=True, translate=False)
    sequence = fields.Integer(string='Sequence', default=10)

    def init(self):
        """Merge legacy duplicate process options when the module is upgraded.

        Preserve the earliest option and transfer M2M selections before
        removing duplicates. No sale.order.line production data is discarded.
        """
        self.env.cr.execute(
            'SELECT id, name FROM crm_job_production_process ORDER BY id'
        )
        rows = self.env.cr.fetchall()
        canonical = {}
        for record_id, name in rows:
            key = (name or '').strip().casefold()
            if not key:
                continue
            if key not in canonical:
                canonical[key] = record_id
                continue
            keep_id = canonical[key]
            # The relation has a unique pair constraint: skip existing pairs.
            self.env.cr.execute('''
                INSERT INTO crm_job_process_sale_line_rel (sale_line_id, process_id)
                SELECT sale_line_id, %s
                FROM crm_job_process_sale_line_rel
                WHERE process_id = %s
                ON CONFLICT DO NOTHING
            ''', (keep_id, record_id))
            self.env.cr.execute(
                'DELETE FROM crm_job_process_sale_line_rel WHERE process_id = %s',
                (record_id,),
            )
            self.env.cr.execute(
                'DELETE FROM crm_job_production_process WHERE id = %s',
                (record_id,),
            )
