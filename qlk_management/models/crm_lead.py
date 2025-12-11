# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class Crm(models.Model):
    _inherit = "crm.lead"

    state = fields.Selection([
        ('new', 'New'),('interested','Interested'),('not_interested','Not Interested'),('follow_up','Follow Up'),('send','Send Proposal'),
    ],default="new", string='State')

    priority_selection = fields.Selection([
        ('high', 'High'),('medium', 'Medium'),('low', 'Low'),
    ], string='Priority', tracking=True)

    opportunity_type = fields.Selection([
        ('litigation', 'Litigation'),('corporate','Corporate'),('arbitration','Arbitration'),
    ], default="litigation", string='Opportunity Type')
    task_ids = fields.One2many('task', 'crm_id', string='Tasks')
    proposal_count = fields.Integer(compute='_compute_proposal', string="Number of Proposals")


    def _compute_proposal(self):
        for lead in self:
            lead.proposal_count = self.env['bd.proposal'].search_count([('lead_id', '=', lead.id)])


    def action_interested(self):
        for rec in self:
            rec.state = 'interested'

    def action_not_interested(self):
        for rec in self:
            rec.state = 'not_interested'

    def action_follow_up(self):
        for rec in self:
            rec.state = 'follow_up'

    def action_send(self):
        for rec in self:
            rec.state = 'send'

    def action_reset_to_new(self):
        for rec in self:
            rec.state = 'new'


    def action_create_bd_proposal(self):
        """Open the BD Proposal form with defaults taken from the lead"""
        self.ensure_one()
        form_view = self.env.ref('qlk_management.view_bd_proposal_form')
        default_client = self.partner_id.display_name or self.partner_name or self.contact_name or self.name
        context = {
            'default_lead_id': self.id,
            'default_partner_id': self.partner_id.id,
            'default_client_name': default_client,
            'default_reference': self.name,
        }
        return {
            'name': _('Create Proposal'),
            'type': 'ir.actions.act_window',
            'res_model': 'bd.proposal',
            'view_mode': 'form',
            'view_id': form_view.id,
            'target': 'current',
            'context': context,
        }


    def action_open_proposal(self):
        """Open all proposals linked to this lead"""
        self.ensure_one()
        form_view = self.env.ref('qlk_management.view_bd_proposal_form')
        kanban_view = self.env.ref('qlk_management.view_bd_proposal_kanban')
        tree_view = self.env.ref('qlk_management.view_bd_proposal_tree')
        return {
            'name': _('Proposals'),
            'type': 'ir.actions.act_window',
            'res_model': 'bd.proposal',
            'view_mode': 'kanban,list,form',
            'views': [
                (kanban_view.id, 'kanban'),
                (tree_view.id, 'list'),
                (form_view.id, 'form'),
            ],
            'domain': [('lead_id', '=', self.id)],
            'context': {
                'default_lead_id': self.id,
                'default_partner_id': self.partner_id.id,
            },
            'target': 'current',
        }






  # def action_new_proposal(self):
    #     if not self.partner_id:
    #         return self.env["ir.actions.actions"]._for_xml_id("qlk_management.action_proposal")
    #     else:
    #         return self.action_new_proposal()

    # def action_new_proposal(self):
    #     action = self.env["ir.actions.actions"]._for_xml_id("qlk_management.action_proposal")
    #     # action['context'] = self._prepare_opportunity_proposal_context()
    #     # action['context']['search_default_opportunity_id'] = self.id
    #     return action
    

    # def _prepare_opportunity_proposal_context(self):
    #     """ Prepares the context for a new proposal  by sharing the values of common fields """
    #     self.ensure_one()
    #     proposal_context = {
    #         'default_opportunity_id': self.id,
    #         'default_partner_id': self.partner_id.id,
    #         'default_campaign_id': self.campaign_id.id,
    #         'default_medium_id': self.medium_id.id,
    #         'default_origin': self.name,
    #         'default_source_id': self.source_id.id,
    #         'default_company_id': self.company_id.id or self.env.company.id,
    #         'default_tag_ids': [(6, 0, self.tag_ids.ids)]
    #     }
    #     # if self.team_id:
    #     #     proposal_context['default_team_id'] = self.team_id.id
    #     # if self.user_id:
    #     #     proposal_context['default_user_id'] = self.user_id.id
    #     return proposal_context



# class OpportunityType(models.Model):
#     _name = "opportunity.type"

#     name = fields.Char('Name')

