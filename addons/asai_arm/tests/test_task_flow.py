from odoo.tests.common import TransactionCase

class TestArmTask(TransactionCase):
    """Тесты бизнес-логики ARM на модели arm.task."""
    def setUp(self):
        super().setUp()
        self.Task = self.env["arm.task"]
        self.Users = self.env["res.users"]
        operator_group = self.env.ref("asai_arm.group_arm_operator")
        manager_group = self.env.ref("asai_arm.group_arm_manager")
        self.op1 = self.Users.create({
            "name": "Op 1",
            "login": "op1@example.com",
            "groups_id": [(6, 0, [operator_group.id])],
        })
        self.op2 = self.Users.create({
            "name": "Op 2",
            "login": "op2@example.com",
            "groups_id": [(6, 0, [operator_group.id])],
        })
        self.manager = self.Users.create({
            "name": "Manager",
            "login": "m1@example.com",
            "groups_id": [(6, 0, [manager_group.id])],
        })

    def test_flow_take_done(self):
        """Оператор берёт задачу и завершает её; время и длительность считаются."""
        task = self.Task.create({"name": "T1"})
        self.assertEqual(task.state, "ready")
        task.action_take()
        self.assertEqual(task.state, "in_progress")
        self.assertTrue(task.started_at)
        task.action_done()
        self.assertEqual(task.state, "done")
        self.assertTrue(task.finished_at)
        self.assertGreaterEqual(task.duration_minutes, 0)

    def test_flow_scrap(self):
        """Пометка брака с причиной переводит задачу в scrap."""
        task = self.Task.create({"name": "T2"})
        task.action_scrap("Дефект поверхности")
        self.assertEqual(task.state, "scrap")
        self.assertTrue(task.scrap_reason)

    def test_operator_cannot_steal_task(self):
        """Нельзя взять задачу, если она назначена другому оператору."""
        task = self.Task.create({"name": "T3", "operator_id": self.op1.id})
        with self.assertRaisesRegex(Exception, "уже назначено другому оператору"):
            task.with_user(self.op2).action_take()

    def test_operator_one_task_limit(self):
        """Оператор не может вести >1 активной задачи одновременно."""
        t1 = self.Task.create({"name": "A"})
        t2 = self.Task.create({"name": "B"})
        t1.with_user(self.op1).action_take()
        self.assertEqual(t1.state, "in_progress")
        with self.assertRaisesRegex(Exception, "У вас уже есть задание в работе"):
            t2.with_user(self.op1).action_take()

    def test_manager_actions_protected(self):
        """Менеджер может вернуть в ready; оператор — нет."""
        t = self.Task.create({"name": "X", "state": "scrap", "scrap_reason": "r"})
        with self.assertRaisesRegex(Exception, "Недостаточно прав"):
            t.with_user(self.op1).action_reset_to_ready()
        t.with_user(self.manager).action_reset_to_ready()
        self.assertEqual(t.state, "ready")

    def test_my_tasks_domain(self):
        """В разделе "Мои" оператор видит только свои задачи."""
        a = self.Task.create({"name": "A", "operator_id": self.op1.id})
        b = self.Task.create({"name": "B", "operator_id": self.op2.id})
        mine = self.Task.with_user(self.op1).search([["operator_id", "=", self.op1.id]])
        self.assertIn(a, mine)
        self.assertNotIn(b, mine)

    def test_flow_cannot_perform(self):
        """Пометка как 'невозможно выполнить' с причиной переводит в blocked."""
        task = self.Task.create({"name": "T3"})
        task.action_cannot_perform("Недостаточно материалов")
        self.assertEqual(task.state, "blocked")
        self.assertTrue(task.fail_reason)