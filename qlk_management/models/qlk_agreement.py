# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Managementgreement(models.Model):
    _name = 'managment.agreement'
    _description = 'Agreement'
    _rec_name="agrement_seq"


    is_agreement = fields.Boolean('Is Agreement',default=False)
    agrement_seq = fields.Char('Agreemnet Name',  default=lambda self: _('New Agreement'))
    client_id = fields.Many2one('res.partner', string='Client', required=True)
    proposal_id = fields.Many2one('sale.order', string='Linked Proposal')
    agreement_date = fields.Date(string='Date', default=fields.Date.today)
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date')
    content = fields.Html(string='Content')
   
    fees = fields.Float(string='Fees')
    expenses = fields.Float(string='Estimated Expenses')
    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)
    # agreement status
    agreement_state = fields.Selection(
        selection=[
            ('ag_draft', "Draft"),
            ('age_approve', "MP Approval"),
            ('ag_sent', "Send CL"),
            ('ag_sale', "CL Approved"),
            ('ag_done', "Done"), 
            ('ag_reject', "Reject"), 
            ('ag_cancel', "Cancelled"),
        ],
        string="Agreement Status",
        readonly=True, copy=False, index=True,
        tracking=3,
        default='ag_draft')
    signed_by_client = fields.Boolean(string='Signed by Client', default=False)
    signed_date = fields.Date(string='Signed Date')
    # attachment_ids = fields.Many2many('ir.attachment', string='Documents')
    to_be_approve = fields.Selection([
        ('manager', 'By Manager'),
        ('assistance', 'Assistance'),
    ], string='To Be Approve By')

    task_ids = fields.One2many('task', 'agreement_id', string='Tasks')
    # agreement fields
    date = fields.Date("Date")
    agreement_date = fields.Date("Agreement Date", tracking=True)
    reference_no = fields.Char('Reference No', tracking=True)
    #first party arabic fields
    first_party_name = fields.Char("اسم الطرف الاول: " , tracking=True, default="الحضـــــــــري وشركاه للمحاماة")
    name = fields.Char('Name', tracking=True)
    license_number = fields.Char('رقم الترخيص ', tracking=True, default="212506")
    address = fields.Char('العنوان', tracking=True, default="بناية كتارا للضيافة، الطابق الخامس – لوسيل مارينا")
    pox_office_address = fields.Char('ص.ب:', default="18022، الدوحة – قطر")
    phone = fields.Char('رقم الهاتف', tracking=True, default="(+974) 40473576")
    email = fields.Char(' البريد الالكتروني', tracking=True, default="dev@alhadhrilawfirm.com")
    #first party english fields
    first_party_name_en = fields.Char('Name(F-P)', tracking=True, default="Al Hadhri & Partners Law Firm")
    license_number_en = fields.Char('License NO(F-P)', tracking=True, default="212506")
    address_en = fields.Char('Address(F-P)', tracking=True, default="Katara Hospitality Tower, 5th Floor, Lusail Marina")
    pox_office_address_en = fields.Char('P.O. Box', default="18022, Doha, Qatar")
    phone_en = fields.Char('Phone(F-P)', tracking=True, default="(+974) 40473576")
    email_en = fields.Char('Email(F-P)', tracking=True, default="dev@alhadhrilawfirm.com")
    #second party arabic fields
    second_party_name = fields.Char('اسم الطرف الثاني', tracking=True)
    id_number = fields.Char('رقم الهوية', tracking=True)
    second_party_address = fields.Char('العنوان', tracking=True)
    first_pox_office_address = fields.Char('ص.ب:')
    second_party_phone = fields.Char('رقم الهاتف', tracking=True)
    second_party_email = fields.Char('البريد الالكتروني', tracking=True)
    #second party english fields
    second_party_name_en = fields.Char('Name(S-P)', tracking=True)
    id_number_en = fields.Char('ID Number', tracking=True)
    second_party_address_en = fields.Char('Address(S-P)', tracking=True)
    second_pox_office_address_en = fields.Char('P.O. Box')
    second_party_phone_en = fields.Char('Tel(S-P)', tracking=True)
    second_party_email_en = fields.Char('Email(S-P)', tracking=True)

    scope_of_work = fields.Char('Scope of Work', tracking=True)
    scope_of_work_ar = fields.Char('نطاق الاعمال الموكله من قبلكم', tracking=True)
    fees = fields.Char('Fees', tracking=True)
    fees_details = fields.Char('Fees Details', tracking=True)
    terms_conditions = fields.Char('Terms and Conditions', tracking=True)
    # display_name = fields.Char(compute="_compute_display_name")
    weekday_ar = fields.Char(string="Weekday (Arabic)", compute="_compute_weekday")
    weekday_en = fields.Char(string="Weekday (English)", compute="_compute_weekday")


    # constraint for task_ids to check the use enter at least one task
    @api.constrains('task_ids')
    def _check_tasks(self):
        for record in self:
            if not any(record.task_ids):
                raise ValidationError("You Have to enter at least one task for ' %s '" %record.agrement_seq)


    @api.depends('date')
    def _compute_weekday(self):
        weekday_mapping = {
            'Monday': 'الاثنين',
            'Tuesday': 'الثلاثاء',
            'Wednesday': 'الأربعاء',
            'Thursday': 'الخميس',
            'Friday': 'الجمعة',
            'Saturday': 'السبت',
            'Sunday': 'الأحد'
        }
        for record in self:
            if record.date:
                weekday_name = record.date.strftime('%A')
                # english weekday
                record.weekday_en = weekday_name
                # arabic weekday
                record.weekday_ar = weekday_mapping.get(weekday_name, '')
            else:
                record.weekday_ar = ''
                record.weekday_en = ''
    


    @api.depends('fees', 'expenses')
    def _compute_total_amount(self):
        for agreement in self:
            agreement.total_amount = agreement.fees + agreement.expenses


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
        # create agreement sequence
            if vals.get('agrement_seq', _("New Agreement")) == _("New Agreement"):
                
                vals['agrement_seq'] = self.env['ir.sequence'].with_company(
                    vals.get('company_id')
                ).next_by_code('agreement.sequence') or _("New")
            return super().create(vals_list)


    # agreement  buttons
    def action_agree_approve(self):
        for record in self:
            if not record.to_be_approve:
                # Trigger JS frontend notification & sound
                return {
                    'type': 'ir.actions.client',
                    'tag': 'play_sound_with_notification',  # your JS action
                    'params': {
                        'title': "test",
                        'message': f"Dear {record.env.user.name}, you need to select Who 'To Be Approved By' for :{record.agrement_seq}.",
                        'sticky': True,
                    },
                    'target': 'new',
                }
            if record.to_be_approve == 'manager':
                title = "Manager Approval"
                message = f"Dear {record.env.user.name}, Agreement {record.agrement_seq} requires manager approval."
            elif record.to_be_approve == 'assistance':
                title = "Assistance Approval"
                message = f"Dear {record.env.user.name}, Agreement {record.agrement_seq} requires assistance approval."

            # Update state
            record.agreement_state = 'age_approve'

            # Trigger JS frontend notification & sound
            return {
                'type': 'ir.actions.client',
                'tag': 'play_sound_with_notification',  # your JS action
                'params': {
                    'title': title,
                    'message': message,
                    'sticky': True,
                },
                'target': 'new',
            }


    def action_agree_mp_approval(self):
        for record in self:
            record.agreement_state = 'ag_sent'


    def action_agree_approve_by(self):
        for record in self:
            record.agreement_state = 'ag_sale'


    def action_agree_done(self):
        for record in self:
            record.agreement_state = 'ag_done'


    def action_agree_reset_to_draft(self):
        for record in self:
            record.agreement_state = 'ag_draft'

    def action_agree_cancel(self):
        for record in self:
            record.agreement_state = 'ag_cancel'
            

    