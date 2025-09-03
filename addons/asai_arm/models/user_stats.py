from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    arm_hours = fields.Float(string="АРМ: часы", default=0.0)
    arm_tasks_done = fields.Integer(string="АРМ: выполнено", default=0)
    arm_tasks_scrap = fields.Integer(string="АРМ: брак", default=0)

    @api.model
    def arm_apply_counters(self, user_id: int, hours_delta: float = 0.0, done_delta: int = 0, scrap_delta: int = 0):
        if not user_id:
            return
        user = self.sudo().browse(user_id)
        vals = {}
        if hours_delta:
            vals["arm_hours"] = (user.arm_hours or 0.0) + float(hours_delta)
        if done_delta:
            vals["arm_tasks_done"] = (user.arm_tasks_done or 0) + int(done_delta)
        if scrap_delta:
            vals["arm_tasks_scrap"] = (user.arm_tasks_scrap or 0) + int(scrap_delta)
        if vals:
            user.write(vals)


