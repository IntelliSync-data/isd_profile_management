import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Move the single print_code_type selection to the print_barcode / print_qrcode flags,
    and the single tracking_number value to barcode_value / qrcode_value."""
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'profile_step' AND column_name = 'print_code_type'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        UPDATE profile_step
        SET print_barcode = (print_code_type = 'barcode'),
            print_qrcode = (print_code_type = 'qrcode')
        WHERE print_code_type IN ('barcode', 'qrcode')
    """)
    _logger.info("isd_profile_management: migrated print code type for %s steps", cr.rowcount)

    for code_type, column in (('barcode', 'barcode_value'), ('qrcode', 'qrcode_value')):
        cr.execute("""
            UPDATE user_step us
            SET {column} = us.tracking_number
            FROM profile_step ps
            WHERE us.step_id = ps.id
              AND ps.print_code_type = %s
              AND us.tracking_number IS NOT NULL
              AND us.{column} IS NULL
        """.format(column=column), (code_type,))
        _logger.info("isd_profile_management: copied %s tracking numbers to %s", cr.rowcount, column)
