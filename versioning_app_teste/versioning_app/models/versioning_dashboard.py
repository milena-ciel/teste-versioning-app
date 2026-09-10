from odoo import api, fields, models


class VersioningDashboard(models.Model):
    _name = "versioning.dashboard"
    _description = "Painel de Versionamento"

    name = fields.Char(default="Painel de Versionamento", readonly=True)
    latest_update_date = fields.Datetime(
        string="Última atualização",
        compute="_compute_dashboard_data",
    )
    latest_version = fields.Char(
        string="Versão",
        compute="_compute_dashboard_data",
    )
    latest_module_display_name = fields.Char(
        string="Último aplicativo atualizado",
        compute="_compute_dashboard_data",
    )

    @api.depends_context("uid")
    def _compute_dashboard_data(self):
        latest = self.env["versioning.changelog"].search(
            [],
            order="commit_date desc, id desc",
            limit=1,
        )

        for rec in self:
            if latest:
                rec.latest_update_date = latest.commit_date
                rec.latest_version = latest.version or "-"
                rec.latest_module_display_name = (
                    latest.module_display_name
                    or latest.module_name
                    or "-"
                )
            else:
                rec.latest_update_date = False
                rec.latest_version = "-"
                rec.latest_module_display_name = "Nenhuma atualização registrada"
