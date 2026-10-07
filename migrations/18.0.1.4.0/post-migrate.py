import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Give every package the payment methods it was already being paid with.

    The list used to live in Settings and applied to everything. Moving it onto
    the package would otherwise leave each one with nothing selected, and the
    fallback would hide the move rather than complete it.
    """
    cr.execute("""
        SELECT to_regclass('profile_management_payment_method_rel')
    """)
    if not cr.fetchone()[0]:
        return

    cr.execute("""
        SELECT value FROM ir_config_parameter
        WHERE key = 'isd_profile_management.pm_payment_method_ids'
    """)
    row = cr.fetchone()
    if not row or not row[0]:
        _logger.info("isd_profile_management: no payment methods in settings to copy")
        return

    method_ids = [int(i) for i in row[0].split(',') if i.strip().isdigit()]
    if not method_ids:
        return

    cr.execute("""
        INSERT INTO profile_management_payment_method_rel (profile_id, method_id)
        SELECT p.id, m.id
          FROM profile_management p
          CROSS JOIN isd_payment_method m
         WHERE m.id = ANY(%s)
           AND NOT EXISTS (
               SELECT 1 FROM profile_management_payment_method_rel r
                WHERE r.profile_id = p.id AND r.method_id = m.id
           )
    """, (method_ids,))
    _logger.info(
        "isd_profile_management: copied the settings payment methods onto %s package rows",
        cr.rowcount)
