from odoo import http, _
from odoo.http import request
import io
import csv
from datetime import datetime


class ArmExportController(http.Controller):
    @http.route(['/asai_arm/export/performance', '/asai_arm/export/performance/'], type='http', auth='user', methods=['GET'], csrf=False)
    def export_performance(self, **kwargs):
        if not request.env.user.has_group('asai_arm.group_arm_manager'):
            return request.not_found()

        Users = request.env['res.users'].sudo().search([])

        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=';')
        writer.writerow(['Оператор', 'Выполнено задач', 'Брак задач', 'Процент брака', 'Часы'])
        for u in Users:
            done = u.arm_tasks_done or 0
            scrap = u.arm_tasks_scrap or 0
            total = done + scrap
            defect_pct = (scrap / total * 100.0) if total else 0.0
            writer.writerow([
                u.name or '',
                done,
                scrap,
                f"{defect_pct:.2f}",
                f"{(u.arm_hours or 0.0):.2f}",
            ])

        content = buf.getvalue().encode('utf-8-sig')
        filename = f"performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        headers = [
            ('Content-Type', 'text/csv; charset=utf-8'),
            ('Content-Disposition', f"attachment; filename={filename}"),
        ]
        return request.make_response(content, headers)
