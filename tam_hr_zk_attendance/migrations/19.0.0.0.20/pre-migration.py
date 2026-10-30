def migrate(cr, version):
    """Preserve legacy data while giving old device rows immutable serials."""
    cr.execute("""
        UPDATE ir_ui_view SET active = FALSE
         WHERE id IN (
             SELECT res_id FROM ir_model_data
              WHERE module = &apos;tam_hr_zk_attendance&apos;
                AND name = &apos;zk_device_user_sync_wizard_view_form&apos;
                AND model = &apos;ir.ui.view&apos;
         )
    """.replace("&apos;", chr(39)))
    cr.execute("""
        DELETE FROM ir_model_access
         WHERE model_id IN (
             SELECT id FROM ir_model
              WHERE model = &apos;zk.device.user.sync.wizard&apos;
         )
    """.replace("&apos;", chr(39)))
