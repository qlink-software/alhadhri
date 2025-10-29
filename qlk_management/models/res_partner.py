# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = "res.partner"

    indust_date = fields.Date('Date')
    contact_attachment_id = fields.One2many('contact.attachments','partner_id', string='Contact Attachments')
    task_ids = fields.One2many('task', 'crm_id', string='Working Hours')



class ContactAttachments(models.Model):
    _name = "contact.attachments"

    name = fields.Char('Name')
    blue_image = fields.Image('Blue Image', max_width=1024, max_height=1024)
    qatar_id = fields.Char('Qatar ID')
    commercial_register = fields.Char('commercial register')
    partner_id = fields.Many2one('res.partner', string='Partner')



class RequestContact(models.Model):
    _name = "request.contact"

    name = fields.Char('Description')
    partner_id = fields.Many2one('res.partner', string='Client')
    new_client = fields.Char('New Client')
    state = fields.Selection([
        ('draft', 'Draft'),('pending','Pending'),('approved','Approved'),('cancel','Cancel')
    ], default="draft", string='State')
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda res: res.env.user.id)
    note = fields.Html('Note')

    def action_reset_to_draft(self):
        for record in self:
            record.state = "draft"

    def action_pending(self):
        for record in self:
            record.state = "pending"

    def action_approved(self):
        for record in self:
            record.state = "approved"

    def action_cancel(self):
        for record in self:
            record.state = "cancel"
