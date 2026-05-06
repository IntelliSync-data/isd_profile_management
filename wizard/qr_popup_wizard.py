from odoo import models, fields


class QRPopup(models.TransientModel):
    _name = 'qr.popup.wizard'
    _description = 'QR Popup Wizard'

    qr_image = fields.Binary("QR Code", readonly=True)
    transaction_id = fields.Char("Transaction ID", readonly=True)
