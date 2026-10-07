import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Keep the 50% option on for the packages that were already using it.

    Paying in halves used to be open to every package, so turning the new flag
    on only for new ones would quietly refuse a deposit on a package whose
    checkout page has been offering it all along. A package that has an order
    sitting at half paid is proof the option is in use, so it keeps it; the
    rest start closed, which is what the flag is for.
    """
    cr.execute("""
        UPDATE profile_management p
           SET allow_half_payment = TRUE
         WHERE EXISTS (
               SELECT 1 FROM user_profile o
                WHERE o.profile_id = p.id
                  AND o.payment_status = 'half_paid'
         )
    """)
    _logger.info(
        "isd_profile_management: kept the 50%% option on for %s package rows",
        cr.rowcount)
