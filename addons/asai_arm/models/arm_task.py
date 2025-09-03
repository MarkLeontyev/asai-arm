from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ArmTask(models.Model):
    _name = "arm.task"
    _description = "ARM Task"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    state = fields.Selection(
        [
            ("ready", "Готово к работе"),
            ("in_progress", "В работе"),
            ("done", "Готово"),
            ("scrap", "Брак"),
            ("blocked", "Невозможно выполнить"),
        ],
        default="ready",
        tracking=True,
        index=True,
        group_expand="_group_expand_state",
    )
    operator_ids = fields.Many2many("res.users", string="Операторы", tracking=True)
    started_at = fields.Datetime(string="Начало", tracking=True)
    finished_at = fields.Datetime(string="Окончание", tracking=True)
    planned_start = fields.Datetime(string="Плановая дата начала")
    planned_end = fields.Datetime(string="Плановая дата окончания")
    qty = fields.Float(string="Кол-во", default=1.0)
    uom_id = fields.Many2one("uom.uom", string="Ед. изм.")
    scrap_reason = fields.Text(string="Причина брака")
    fail_reason = fields.Text(string="Причина невозможности выполнения")
    attachment_ids = fields.Many2many("ir.attachment", string="Чертежи/Материалы")

    duration_minutes = fields.Integer(
        string="Длительность, мин",
        compute="_compute_duration_minutes",
        store=True,
    )

    @api.depends("started_at", "finished_at")
    def _compute_duration_minutes(self):
        for rec in self:
            rec.duration_minutes = 0
            if rec.started_at and rec.finished_at:
                delta = fields.Datetime.to_datetime(rec.finished_at) - fields.Datetime.to_datetime(rec.started_at)
                rec.duration_minutes = int(delta.total_seconds() // 60)

    @api.model
    def _group_expand_state(self, states, domain, order=None, **kwargs):
        return [
            "ready",
            "in_progress",
            "scrap",
            "blocked",
            "done",
        ]

    def action_take(self):
        for rec in self:
            if rec.state not in ("ready",):
                raise UserError(_("Задание нельзя взять из текущего статуса."))
            rec.write({
                "state": "in_progress",
                "started_at": fields.Datetime.now(),
                "operator_ids": [(4, self.env.user.id)],
            })

    def action_done(self):
        for rec in self:
            if rec.state != "in_progress":
                raise UserError(_("Пометьте задание как 'В работе' перед завершением."))
            rec.write({
                "state": "done",
                "finished_at": fields.Datetime.now(),
            })

    def action_scrap(self, reason=None):
        for rec in self:
            if rec.state not in ("in_progress", "ready"):
                raise UserError(_("Брак возможен только из статусов 'Готово' или 'В работе'."))
            rec.write({
                "state": "scrap",
                "scrap_reason": reason or rec.scrap_reason,
                "finished_at": fields.Datetime.now() if not rec.finished_at else rec.finished_at,
            })

    def action_cannot_perform(self):
        for rec in self:
            if rec.state in ("done", "scrap"):
                raise UserError(_("Задание уже завершено."))
            rec.write({
                "state": "blocked",
                "fail_reason": rec.fail_reason,
            })

    def action_open_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Файлы задания"),
            "res_model": "ir.attachment",
            "view_mode": "list,form",
            "domain": [["id", "in", self.attachment_ids.ids]],
            "target": "current",
        }
