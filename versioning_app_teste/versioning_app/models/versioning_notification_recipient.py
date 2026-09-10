from odoo import fields, models


class VersioningNotificationRecipient(models.Model):
    _name = "versioning.notification.recipient"
    _description = "Destinatário de notificações de atualização"

    partner_id = fields.Many2one("res.partner", string="Usuário/Contato")
    email = fields.Char(string="E-mail (se não for um contato cadastrado)")
    notify_email = fields.Boolean(default=True, string="Notificar por e-mail")
    notify_odoo = fields.Boolean(default=True, string="Notificar no Odoo")
    repository_ids = fields.Many2many(
        "versioning.repository",
        string="Repositórios acompanhados",
        help="Deixe vazio para acompanhar todos os repositórios",
    )

    _sql_constraints = [
        (
            "partner_or_email",
            "CHECK(partner_id IS NOT NULL OR email IS NOT NULL)",
            "Informe um contato cadastrado ou um e-mail.",
        ),
    ]
