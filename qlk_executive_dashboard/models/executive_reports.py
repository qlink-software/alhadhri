# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class ExecutiveCaseReport(models.Model):
    _name = "qlk.executive.case.report"
    _description = "Executive Case Report"
    _auto = False
    _rec_name = "case_id"

    case_id = fields.Many2one("qlk.case", readonly=True)
    status = fields.Char(readonly=True)
    case_group_id = fields.Many2one("qlk.casegroup", readonly=True)
    litigation_flow = fields.Char(readonly=True)
    state = fields.Char(readonly=True)
    date = fields.Date(readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, "qlk_executive_case_report")
        self.env.cr.execute(
            """
            CREATE VIEW qlk_executive_case_report AS (
                SELECT
                    c.id AS id,
                    c.id AS case_id,
                    c.status AS status,
                    c.case_group AS case_group_id,
                    c.litigation_flow AS litigation_flow,
                    c.state AS state,
                    c.date AS date
                FROM qlk_case c
            )
            """
        )


class ExecutiveFinanceReport(models.Model):
    _name = "qlk.executive.finance.report"
    _description = "Executive Finance Report"
    _auto = False
    _rec_name = "move_id"

    move_id = fields.Many2one("account.move", readonly=True)
    move_type = fields.Char(readonly=True)
    state = fields.Char(readonly=True)
    payment_state = fields.Char(readonly=True)
    amount_total = fields.Monetary(readonly=True)
    amount_residual = fields.Monetary(readonly=True)
    invoice_date = fields.Date(readonly=True)
    invoice_date_due = fields.Date(readonly=True)
    date = fields.Date(readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    invoice_user_id = fields.Many2one("res.users", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, "qlk_executive_finance_report")
        self.env.cr.execute(
            """
            CREATE VIEW qlk_executive_finance_report AS (
                SELECT
                    m.id AS id,
                    m.id AS move_id,
                    m.move_type AS move_type,
                    m.state AS state,
                    m.payment_state AS payment_state,
                    m.amount_total AS amount_total,
                    m.amount_residual AS amount_residual,
                    m.invoice_date AS invoice_date,
                    m.invoice_date_due AS invoice_date_due,
                    m.date AS date,
                    m.currency_id AS currency_id,
                    m.invoice_user_id AS invoice_user_id
                FROM account_move m
                WHERE m.state = 'posted'
            )
            """
        )
