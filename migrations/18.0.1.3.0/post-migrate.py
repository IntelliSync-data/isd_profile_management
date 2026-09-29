import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Give every existing order a public code.

    The customer order page looks orders up by this code, so orders created
    before the field existed would be unreachable without it. Built in SQL from
    md5(random()) rather than the Python generator, to fill a whole table in one
    statement.
    """
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'user_profile' AND column_name = 'order_code'
    """)
    if not cr.fetchone():
        return

    # Same alphabet as the Python side: no 0/O or 1/I to misread
    cr.execute("""
        UPDATE user_profile
        SET order_code = upper(
            translate(
                substr(md5(random()::text || id::text || clock_timestamp()::text), 1, 12),
                '01',
                'XY'
            )
        )
        WHERE order_code IS NULL OR order_code = ''
    """)
    _logger.info(
        "isd_profile_management: generated an order code for %s orders", cr.rowcount)
