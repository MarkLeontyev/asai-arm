from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class ArmTask(models.Model):
    """Производственное задание для оператора.

    Содержит статусы жизненного цикла и основные действия: взять, завершить,
    отметить брак или невозможность выполнения.
    """
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
    operator_id = fields.Many2one("res.users", string="Оператор", tracking=True, index=True)
    started_at = fields.Datetime(string="Начало", tracking=True)
    finished_at = fields.Datetime(string="Окончание", tracking=True)
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
        """Рассчитать длительность в минутах между началом и окончанием."""
        for rec in self:
            rec.duration_minutes = 0
            if rec.started_at and rec.finished_at:
                delta = fields.Datetime.to_datetime(rec.finished_at) - fields.Datetime.to_datetime(rec.started_at)
                rec.duration_minutes = int(delta.total_seconds() // 60)

    def action_take(self):
        """Взять задание в работу текущим пользователем."""
        for rec in self:
            if rec.state not in ("ready",):
                raise UserError(_("Задание нельзя взять из текущего статуса."))
            if rec.operator_id and rec.operator_id != self.env.user:
                raise UserError(_("Задание уже назначено другому оператору."))
            active_for_user = self.search_count([
                ("state", "=", "in_progress"),
                ("operator_id", "=", self.env.user.id),
            ])
            if active_for_user:
                raise UserError(_("У вас уже есть задание в работе."))
            rec.write({
                "state": "in_progress",
                "started_at": fields.Datetime.now(),
                "operator_id": self.env.user.id,
            })

    def action_done(self):
        """Завершить задание."""
        for rec in self:
            if rec.state != "in_progress":
                raise UserError(_("Пометьте задание как 'В работе' перед завершением."))
            rec.write({
                "state": "done",
                "finished_at": fields.Datetime.now(),
            })

    def action_scrap(self, reason=None):
        """Отметить задание как брак.

        Если причина не указана, откроет модальное окно редактирования самой
        записи с требованием заполнить поле.
        """
        for rec in self:
            if rec.state not in ("in_progress", "ready"):
                raise UserError(_("Брак возможен только из статусов 'Готово' или 'В работе'."))
            if not (reason or rec.scrap_reason):
                return rec._open_reason_dialog(mode="scrap")
            rec.write({
                "state": "scrap",
                "scrap_reason": reason or rec.scrap_reason,
                "finished_at": fields.Datetime.now() if not rec.finished_at else rec.finished_at,
            })

    def action_cannot_perform(self, reason=None):
        """Отметить задание как 'невозможно выполнить'.

        При отсутствии причины откроет модальное окно на этой же модели
        для заполнения.
        """
        for rec in self:
            if rec.state in ("done", "scrap"):
                raise UserError(_("Задание уже завершено."))
            if reason:
                rec.fail_reason = reason
            if not rec.fail_reason:
                return rec._open_reason_dialog(mode="blocked")
            rec.write({
                "state": "blocked",
                "fail_reason": rec.fail_reason,
            })

    def action_open_attachments(self):
        """Открыть связанные файлы задания."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Файлы задания"),
            "res_model": "ir.attachment",
            "view_mode": "list,form",
            "domain": [["id", "in", self.attachment_ids.ids]],
            "target": "current",
        }

    def write(self, vals):
        """Валидация причин при переходе в проблемные статусы."""
        if vals.get("state") == "scrap":
            new_reason = vals.get("scrap_reason")
            if not (new_reason or any(rec.scrap_reason for rec in self)):
                raise UserError(_("Укажите причину брака"))
        if vals.get("state") == "blocked":
            new_reason = vals.get("fail_reason")
            if not (new_reason or any(rec.fail_reason for rec in self)):
                raise UserError(_("Укажите причину невозможности выполнения"))
        return super().write(vals)

    @api.constrains("state", "scrap_reason", "fail_reason")
    def _check_reasons_present(self):
        """Гарантировать, что причина заполнена для 'scrap' и 'blocked'."""
        for rec in self:
            if rec.state == "scrap" and not rec.scrap_reason:
                raise ValidationError(_("Для статуса 'Брак' необходимо указать причину."))
            if rec.state == "blocked" and not rec.fail_reason:
                raise ValidationError(_("Для статуса 'Невозможно выполнить' необходимо указать причину."))

    @api.model
    def _group_expand_state(self, states, domain, order=None, **kwargs):
        """Определить и зафиксировать порядок колонок в kanban."""
        return ["ready", "in_progress", "scrap", "blocked", "done"]

    def _open_reason_dialog(self, mode: str):
        """Открыть модальное окно редактирования причины на самой модели.

        mode: 'scrap' | 'blocked' — управляет видимостью полей в специальном
        диалоге на `arm.task`.
        """
        self.ensure_one()
        title = _("Причина брака") if mode == "scrap" else _("Причина невозможности")
        context = {
            "default_state": self.state,
            "dialog_mode": mode,
        }
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": "arm.task",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref("asai_arm.view_arm_task_reason_dialog").id,
            "target": "new",
            "context": context,
        }

    def action_open_scrap_dialog(self):
        """Открыть диалог для ввода причины брака на текущей задаче."""
        self.ensure_one()
        return self._open_reason_dialog("scrap")

    def action_open_blocked_dialog(self):
        """Открыть диалог для ввода причины невозможности выполнения."""
        self.ensure_one()
        return self._open_reason_dialog("blocked")

    def action_confirm_reason(self):
        """Подтвердить изменение статуса из модального окна причины.

        Режим берём из контекста: 'scrap' или 'blocked'. Валидируем
        обязательность поля и переводим запись в нужный статус.
        """
        self.ensure_one()
        mode = self.env.context.get("dialog_mode")
        if mode == "scrap":
            if not self.scrap_reason:
                raise ValidationError(_("Укажите причину брака"))
            self.write({
                "state": "scrap",
                "finished_at": fields.Datetime.now() if not self.finished_at else self.finished_at,
            })
        elif mode == "blocked":
            if not self.fail_reason:
                raise ValidationError(_("Укажите причину невозможности выполнения"))
            self.write({
                "state": "blocked",
            })
        return {"type": "ir.actions.act_window_close"}

    def action_reset_to_ready(self):
        """Вернуть задание в состояние 'Готово к работе' (для менеджера).

        Сбрасывает время начала/окончания. Причины сохраняем для истории.
        """
        if not self.env.user.has_group("asai_arm.group_arm_manager"):
            raise UserError(_("Недостаточно прав. Обратитесь к менеджеру."))
        for rec in self:
            if rec.state in ("scrap", "blocked"):
                rec.write({
                    "state": "ready",
                    "started_at": False,
                    "finished_at": False,
                })
        return {"type": "ir.actions.client", "tag": "reload"}
