{
    "name": "Versionamento de Customizações (GitHub)",
    "version": "19.0.1.0.0",
    "summary": "Acompanha automaticamente as atualizações dos repositórios GitHub de cada cliente e da localização compartilhada",
    "description": """
Versionamento de Customizações
===============================

Monitora, via polling na API do GitHub, os repositórios vinculados a esta base:
- Repositório próprio do cliente (customizações exclusivas)
- Repositório(s) compartilhado(s), como a localização BR

A cada verificação, novos commits viram registros de changelog, a versão é
incrementada automaticamente, e os destinatários cadastrados são notificados
por e-mail e/ou notificação interna do Odoo.
    """,
    "author": "Sua Empresa",
    "category": "Extra Tools",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "data/versioning_dashboard_data.xml",
        "views/versioning_repository_views.xml",
        "views/versioning_changelog_views.xml",
        "views/versioning_notification_recipient_views.xml",
        "views/versioning_menus.xml",
        "views/versioning_dashboard_views.xml",
    ],
    "installable": True,
    "application": True,
}
