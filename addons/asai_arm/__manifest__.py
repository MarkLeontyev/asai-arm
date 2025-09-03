# -*- coding: utf-8 -*-
{
    'name': "АСАИ – Тестовое задание – АРМ",

    'summary': "Автоматизированное рабочее место оператора",

    'description': """
Модуль для работы оператора: взять/выполнить/брак, учёт времени.
    """,

    'author': "Mark Leontev",
    'website': "http://localhost:8069/asai/arm",

    'category': 'Manufacturing',
    'version': '18.0.1.0.0',

    'depends': ['base', 'web', 'mail', 'uom'],

    'data': [
        'security/asai_arm_security.xml',
        'security/ir.model.access.csv',
        'views/menu.xml',
        'views/arm_task_views.xml',
        'data/arm_task_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'asai_arm/static/src/css/arm.css',
        ],
    },
    'application': True,
    'license': 'LGPL-3',
}

