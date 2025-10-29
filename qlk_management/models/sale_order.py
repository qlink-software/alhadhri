# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"
    _rec_name = "proposal_seq"
    _description = "Proposal"

    is_proposal = fields.Boolean('Is Propopsal',default=False)
    is_proposal_agreement = fields.Boolean('Is Proposal Agreement',default=False)
    proposal_seq = fields.Char('Proposal Name', default=lambda self: _('New Proposal'))
    state = fields.Selection(
        selection=[
            ('draft', "Draft"),
            ('approve', "MP Approval"),
            ('sent', "Send CL"),
            ('sale', "CL Approved"),
            ('done', "Done"), 
            ('reject', "Reject"), 
            ('cancel', "Cancelled"),
        ],
        string="Status",
        readonly=True, copy=False, index=True,
        tracking=3,
        default='draft')
    
    to_be_approve = fields.Selection([
        ('manager', 'By Manager'),
        ('assistance', 'Assistance'),
    ], string='To Be Approve By')

    proposal_ref = fields.Char('Reference')
    reject_reason = fields.Char('Reject Reason')
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Client",
        required=True, change_default=True, index=True,
        tracking=1,
        check_company=True)
    
    date_order = fields.Datetime(
        string="Date",
        required=True, copy=False,
        help="Creation date of draft/sent orders,\nConfirmation date of confirmed orders.",
        default=fields.Datetime.now)
    task_ids = fields.One2many('task', 'proposal_id', string='Tasks')
    scope_work_ids = fields.One2many('scope.work', 'sale_order_id', string='Scope Of Work')
    legal_fees_ids = fields.One2many('legal.fees', 'sale_order_id', string='Legal Fees')
    term_condtion_ids = fields.One2many('term.condtion', 'sale_order_id', string='Term Of Conditions')
    count_agreement = fields.Char(compute='_compute_agreement', string='Count Agreement')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    cost_calculation_id = fields.Many2one('cost.calculation', string='Cost Calculation',store=True)
    mactech = fields.Float('Mactech',store=True)
    email_charge = fields.Float('Email Charge',store=True)
    office_rent = fields.Float('Office Rent',store=True)
    printer_rent = fields.Float('Printer Rent',store=True)
    telephone = fields.Float('Telephone',store=True)
    salary = fields.Float('Salary',store=True)
    total = fields.Float('Total',store=True)
    cost_per_hour = fields.Float('Cost Per Hour',store=True)


    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for rec in records:
            # create proposal sequence
            if rec.is_proposal and rec.proposal_seq == _("New Proposal"):
                seq_date = fields.Datetime.context_timestamp(
                    rec, rec.date_order
                ) if rec.date_order else None
                rec.proposal_seq = (
                    self.env['ir.sequence']
                    .with_company(rec.company_id)
                    .next_by_code('proposal.sequence', sequence_date=seq_date)
                    or _("New")
                )

            # update cost calculation if employee exists
            if rec.employee_id:
                rec._update_cost_calculation()

        return records
    


    def write(self, vals):
        """When updating employee, automatically refresh cost calculation"""
        res = super().write(vals)
        if 'employee_id' in vals:
            self._update_cost_calculation()
        return res
    


    def _update_cost_calculation(self):
        """Find and set cost_calculation_id based on employee"""
        for rec in self:
            if rec.employee_id:
                cost_calc = self.env['cost.calculation'].search([
                    ('employee_id', '=', rec.employee_id.id)
                ], limit=1)
                if cost_calc:
                    rec.cost_calculation_id = cost_calc.id
                    rec.mactech = cost_calc.mactech
                    rec.email_charge = cost_calc.email_charge
                    rec.office_rent = cost_calc.office_rent
                    rec.printer_rent = cost_calc.printer_rent
                    rec.telephone = cost_calc.telephone
                    rec.salary = cost_calc.salary
                    rec.total = cost_calc.total
                    rec.cost_per_hour = cost_calc.cost_per_hour


    
    def _compute_agreement(self):
        for rec in self:
            rec.count_agreement = self.env['managment.agreement'].search_count([('proposal_id','=', rec.id)])



    # constraint for task_ids to check the use enter at least one task
    @api.constrains('task_ids')
    def _check_tasks(self):
        for record in self:
            if not any(record.task_ids):
                raise ValidationError("You Have to enter at least one task for ' %s '" %record.proposal_seq)
            


    def action_open_agreement(self):
        return {
            'name': 'name',
            'type': 'ir.actions.act_window',
            'view_mode': 'list',
            'views': [(False, 'list')],
            'res_model': 'managment.agreement',
            'target': 'current',
            'views': [[False, 'list'], [False, 'form']],
                'domain': [('proposal_id', '=', self.id)],
                'context': {
                    'create': False,
                    'edit': False,
                },
            
        }

    
    
    # @api.depends('proposal_seq', 'agrement_seq')
    # def _compute_display_name(self):
    #     for record in self:
    #         record.display_name = ""
    #         if record.is_proposal:
    #             parts = filter(None, [record.proposal_seq, record.agrement_seq])
    #             record.display_name = " / ".join(parts)
    #         if record.is_agreement:
    #             record.display_name  = record.agrement_seq
            


    def to_approve(self):
        for record in self:
            if not record.to_be_approve:
                # Trigger JS frontend notification & sound
                return {
                    'type': 'ir.actions.client',
                    'tag': 'play_sound_with_notification',  # your JS action
                    'params': {
                        'title': "test",
                        'message': f"Dear {record.env.user.name}, you need to select Who 'To Be Approved By' for :{record.proposal_seq}.",
                        'sticky': True,
                    },
                    'target': 'new',
                }
            if record.to_be_approve == 'manager':
                title = "Manager Approval"
                message = f"Dear {record.env.user.name}, Proposal {record.proposal_seq} requires manager approval."
            elif record.to_be_approve == 'assistance':
                title = "Assistance Approval"
                message = f"Dear {record.env.user.name}, Proposal {record.proposal_seq} requires assistance approval."

            # Update state
            record.state = 'approve'

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

        
       
    def proposal_sent(self):
        for record in self:
            record.state = 'sent'
        # """ Opens a wizard to compose an email, with relevant mail template loaded by default """
        # # self.filtered(lambda so: so.state in ('draft', 'sent')).order_line._validate_analytic_distribution()
        # lang = self.env.context.get('lang')
        # self.state = 'sent'
        # ctx = {
        #     'default_model': 'sale.order',
        #     'default_res_ids': self.ids,
        #     'default_composition_mode': 'comment',
        #     'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
        #     # 'proforma': self.env.context.get('proforma', False),
        # }

        # if len(self) > 1:
        #     ctx['default_composition_mode'] = 'mass_mail'
        # else:
        #     ctx.update({
        #         'force_email': True,
        #         'model_description': self.with_context(lang=lang).type_name,
        #     })
        #     if not self.env.context.get('hide_default_template'):
        #         mail_template = self.env.ref('qlk_management.email_proposal_template', raise_if_not_found=False)
        #         if mail_template:
        #             ctx.update({
        #                 'default_template_id': mail_template.id,
        #                 'mark_so_as_sent': True,
        #             })
        #         if mail_template and mail_template.lang:
        #             lang = mail_template._render_lang(self.ids)[self.id]
        #     else:
        #         for order in self:
        #             order._portal_ensure_token()

        # return {
        #     'type': 'ir.actions.act_window',
        #     'view_mode': 'form',
        #     'res_model': 'mail.compose.message',
        #     'views': [(False, 'form')],
        #     'view_id': False,
        #     'target': 'new',
        #     'context': ctx,
        # }


    def action_sale(self):
        for record in self:
            record.state = 'sale'

            
    def action_done(self):
        for record in self:
            record.state = 'done'

    
    # create seq for agreement from the proposal view
    def create_agreement(self):
        for rec in self:
            rec.is_proposal_agreement = True
            # rec.state = 'sale'
            if rec.state == 'done':
                # here should review the code to open the agreement action 
                agreement = rec.env.ref('qlk_management.managment_agreement_action')
                # if rec.agrement_seq == _("New Agreement"):
                #     rec.agrement_seq = self.env['ir.sequence'].with_company(rec.company_id).next_by_code('agreement.sequence') or _("New")



    def action_reject(self):
        for record in self:
            if record.reject_reason:
                record.state = 'reject'
            else:
                title = "Reject Reason"
                message = f"Dear {record.env.user.name} The Rejection Reason Is required."
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

    
    def action_reset_to_draft(self):
        for record in self:
            record.state = 'draft'


    

class ScopeOfWork(models.Model):
    _name = "scope.work"

    name = fields.Char('description')
    sale_order_id = fields.Many2one('sale.order', string='Proposal')

class LegalFees(models.Model):
    _name = "legal.fees"

    name = fields.Char('description')
    amount_fee = fields.Float('Amount Fee')
    sale_order_id = fields.Many2one('sale.order', string='Proposal')


class TermOfCondtions(models.Model):
    _name = "term.condtion"

    name = fields.Char('description')
    amount = fields.Float('Amount')
    payment_date = fields.Date('Payment Date')
    sale_order_id = fields.Many2one('sale.order', string='Proposal')
