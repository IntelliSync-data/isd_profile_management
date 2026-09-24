import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Packages that existed before the Demo/Live type are real business, so mark
    them Live. Only new packages start as Demo."""
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'profile_management' AND column_name = 'package_type'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        UPDATE profile_management
        SET package_type = 'live'
        WHERE package_type IS NULL OR package_type = 'demo'
    """)
    _logger.info(
        "isd_profile_management: marked %s existing packages as Live", cr.rowcount)
