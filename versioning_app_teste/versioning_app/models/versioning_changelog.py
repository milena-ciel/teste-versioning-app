from odoo import fields, models


class VersioningChangelog(models.Model):
    _name = "versioning.changelog"
    _description = "Atualização registrada a partir do GitHub"
    _inherit = ["mail.thread"]
    _order = "commit_date desc, id desc"

    repository_id = fields.Many2one(
        "versioning.repository", required=True, ondelete="cascade", index=True
    )
    repo_kind = fields.Selection(related="repository_id.repo_kind", store=True)
    commit_sha = fields.Char(required=True)
    author_name = fields.Char()
    author_email = fields.Char()
    committer_name = fields.Char()
    message = fields.Text()
    module_name = fields.Char(string="Nome técnico")
    module_display_name = fields.Char(string="Aplicativo")
    files_changed = fields.Text()
    version = fields.Char()
    commit_date = fields.Datetime()
    github_url = fields.Char()

    def _notify_recipients(self):
        Recipient = self.env["versioning.notification.recipient"]
        for rec in self:
            recipients = Recipient.search(
                [
                    "|",
                    ("repository_ids", "=", False),
                    ("repository_ids", "in", rec.repository_id.ids),
                ]
            )
            if not recipients:
                continue

            odoo_partners = recipients.filtered("notify_odoo").mapped("partner_id")
            if odoo_partners:
                rec.message_post(
                    body=rec._notification_body(),
                    partner_ids=odoo_partners.ids,
                    subtype_xmlid="mail.mt_comment",
                )

            for recipient in recipients.filtered("notify_email"):
                email = recipient.email or (
                    recipient.partner_id.email if recipient.partner_id else False
                )
                if not email:
                    continue
                self.env["mail.mail"].sudo().create(
                    {
                        "subject": "[%s] Atualização para versão %s"
                        % (rec.repository_id.name, rec.version),
                        "email_to": email,
                        "body_html": rec._notification_body(),
                    }
                ).send()

    def _notification_body(self):
        self.ensure_one()
        return (
            "<p><b>%s</b> foi atualizado para a versão <b>%s</b>.</p>"
            "<p>%s</p>"
            "<p>Aplicativo: %s<br/>Commit por: %s · Commit: %s</p>"
        ) % (
            self.repository_id.name,
            self.version,
            self.message or "",
            self.module_display_name or self.module_name or "-",
            self.author_name or "-",
            (self.commit_sha or "")[:7],
        )
