from odoo.tests.common import TransactionCase


class TestRmQcMasterData(TransactionCase):
    """Run on a staging Odoo 19 DB with --test-enable."""

    def test_workbook_seed_counts(self):
        Templates = self.env['rm.qc.parameter.template']
        self.assertGreaterEqual(Templates.search_count([('scope', '=', 'incoming')]), 21)
        self.assertGreaterEqual(Templates.search_count([('scope', '=', 'production')]), 45)
        Defects = self.env['rm.qc.defect']
        self.assertEqual(Defects.search_count([('code', 'in', [
            'RM001', 'RM002', 'RM003', 'RM004', 'RM005', 'RM006', 'RM007',
            'RM008', 'RM009', 'RM010', 'RM011', 'RM012', 'RM013', 'RM014',
            'RM015', 'RM016', 'RM017', 'RM018', 'RM019', 'RM020',
        ])]), 20)
