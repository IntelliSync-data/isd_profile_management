from odoo import models, fields


class QRPopup(models.TransientModel):
    _name = 'qr.popup.wizard'
    _description = 'QR Popup Wizard'

    qr_image = fields.Binary("QR Code", readonly=True)
    transaction_id = fields.Char("Transaction ID", readonly=True)
    # Link to the public order page plus its validity note, copied as one block
    order_link_text = fields.Text("Order Link", readonly=True)
    amount = fields.Float("Amount", readonly=True)
    payment_method_name = fields.Char("Payment Method", readonly=True)
