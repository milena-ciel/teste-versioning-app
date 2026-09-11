# -*- coding: utf-8 -*-

from collections import Counter
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models


class VersioningDashboard(models.Model):
    _name = "versioning.dashboard"
    _description = "Painel de Versionamento"

    name = fields.Char(
        default="Painel de Versionamento",
        readonly=True,
    )

    # ---------------------------------------------------------
    # Última atualização
    # ---------------------------------------------------------

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

    latest_author_name = fields.Char(
        string="Última pessoa que atualizou",
        compute="_compute_dashboard_data",
    )

    latest_commit_message = fields.Text(
        string="Mensagem do último commit",
        compute="_compute_dashboard_data",
    )

    # ---------------------------------------------------------
    # Indicadores
    # ---------------------------------------------------------

    total_updates = fields.Integer(
        string="Total de atualizações",
        compute="_compute_dashboard_data",
    )

    updates_last_7_days = fields.Integer(
        string="Atualizações nos últimos 7 dias",
        compute="_compute_dashboard_data",
    )

    active_repositories = fields.Integer(
        string="Repositórios ativos",
        compute="_compute_dashboard_data",
    )

    connected_repositories = fields.Integer(
        string="Repositórios conectados",
        compute="_compute_dashboard_data",
    )

    error_repositories = fields.Integer(
        string="Repositórios com erro",
        compute="_compute_dashboard_data",
    )

    # ---------------------------------------------------------
    # Gráficos / visualizações
    # ---------------------------------------------------------

    updates_chart_html = fields.Html(
        string="Atualizações",
        compute="_compute_dashboard_data",
        sanitize=False,
    )

    modules_chart_html = fields.Html(
        string="Aplicativos",
        compute="_compute_dashboard_data",
        sanitize=False,
    )

    authors_chart_html = fields.Html(
        string="Desenvolvedores",
        compute="_compute_dashboard_data",
        sanitize=False,
    )

    latest_updates_html = fields.Html(
        string="Últimas atualizações",
        compute="_compute_dashboard_data",
        sanitize=False,
    )

    # ---------------------------------------------------------
    # Compute principal
    # ---------------------------------------------------------

    @api.depends_context("uid", "tz")
    def _compute_dashboard_data(self):
        Changelog = self.env["versioning.changelog"]
        Repository = self.env["versioning.repository"]

        latest = Changelog.search(
            [],
            order="commit_date desc, id desc",
            limit=1,
        )

        total_updates = Changelog.search_count([])

        active_repositories = Repository.search_count([
            ("active", "=", True),
        ])

        connected_repositories = Repository.search_count([
            ("active", "=", True),
            ("state", "=", "connected"),
        ])

        error_repositories = Repository.search_count([
            ("active", "=", True),
            ("state", "=", "error"),
        ])

        # -----------------------------------------------------
        # Atualizações últimos 7 dias
        # -----------------------------------------------------

        today = fields.Date.context_today(self)
        start_date = today - timedelta(days=6)

        recent_updates = Changelog.search([
            ("commit_date", ">=", fields.Datetime.to_string(
                fields.Datetime.now() - timedelta(days=7)
            )),
        ])

        daily_counter = Counter()

        for changelog in recent_updates:
            if not changelog.commit_date:
                continue

            local_datetime = fields.Datetime.context_timestamp(
                self,
                changelog.commit_date,
            )

            daily_counter[local_datetime.date()] += 1

        daily_rows = []

        current_date = start_date

        while current_date <= today:
            daily_rows.append(
                (
                    current_date.strftime("%d/%m"),
                    daily_counter.get(current_date, 0),
                )
            )
            current_date += timedelta(days=1)

        # -----------------------------------------------------
        # Aplicativos mais atualizados
        # -----------------------------------------------------

        module_counter = Counter()

        all_changelogs = Changelog.search(
            [],
            order="commit_date desc, id desc",
        )

        for changelog in all_changelogs:
            module_name = (
                changelog.module_display_name
                or changelog.module_name
                or "Não identificado"
            )

            module_counter[module_name] += 1

        module_rows = module_counter.most_common(5)

        # -----------------------------------------------------
        # Desenvolvedores
        # -----------------------------------------------------

        author_counter = Counter()

        for changelog in all_changelogs:
            author = (
                changelog.author_name
                or changelog.committer_name
                or "Não identificado"
            )

            author_counter[author] += 1

        author_rows = author_counter.most_common(5)

        # -----------------------------------------------------
        # Últimas atualizações
        # -----------------------------------------------------

        latest_updates = Changelog.search(
            [],
            order="commit_date desc, id desc",
            limit=8,
        )

        latest_updates_html = self._build_latest_updates_html(
            latest_updates
        )

        updates_chart_html = self._build_bar_chart(
            daily_rows,
            color="#714B67",
        )

        modules_chart_html = self._build_bar_chart(
            module_rows,
            color="#017E84",
        )

        authors_chart_html = self._build_bar_chart(
            author_rows,
            color="#875A7B",
        )

        # -----------------------------------------------------
        # Preenchimento
        # -----------------------------------------------------

        for rec in self:

            if latest:
                rec.latest_update_date = latest.commit_date
                rec.latest_version = latest.version or "-"

                rec.latest_module_display_name = (
                    latest.module_display_name
                    or latest.module_name
                    or "-"
                )

                rec.latest_author_name = (
                    latest.author_name
                    or latest.committer_name
                    or "-"
                )

                rec.latest_commit_message = (
                    latest.message
                    or "-"
                )

            else:
                rec.latest_update_date = False
                rec.latest_version = "-"
                rec.latest_module_display_name = (
                    "Nenhuma atualização registrada"
                )
                rec.latest_author_name = "-"
                rec.latest_commit_message = "-"

            rec.total_updates = total_updates
            rec.updates_last_7_days = len(recent_updates)

            rec.active_repositories = active_repositories
            rec.connected_repositories = connected_repositories
            rec.error_repositories = error_repositories

            rec.updates_chart_html = updates_chart_html
            rec.modules_chart_html = modules_chart_html
            rec.authors_chart_html = authors_chart_html

            rec.latest_updates_html = latest_updates_html

    # ---------------------------------------------------------
    # Gráfico horizontal
    # ---------------------------------------------------------

    @staticmethod
    def _build_bar_chart(rows, color="#714B67"):
        if not rows:
            return Markup(
                """
                <div style="
                    padding:30px;
                    text-align:center;
                    color:#777;
                ">
                    Nenhuma informação disponível.
                </div>
                """
            )

        max_value = max(
            [value for _, value in rows] or [1]
        )

        if max_value <= 0:
            max_value = 1

        html = """
            <div style="padding:10px 5px;">
        """

        for label, value in rows:

            percentage = (
                (value / max_value) * 100
                if max_value
                else 0
            )

            html += """
                <div style="margin-bottom:16px;">

                    <div style="
                        display:flex;
                        justify-content:space-between;
                        margin-bottom:5px;
                        font-size:14px;
                    ">
                        <span>
                            %s
                        </span>

                        <strong>
                            %s
                        </strong>
                    </div>

                    <div style="
                        height:12px;
                        background:#E9ECEF;
                        border-radius:8px;
                        overflow:hidden;
                    ">

                        <div style="
                            width:%s%%;
                            height:100%%;
                            background:%s;
                            border-radius:8px;
                        ">
                        </div>

                    </div>

                </div>
            """ % (
                escape(label),
                value,
                percentage,
                color,
            )

        html += "</div>"

        return Markup(html)

    # ---------------------------------------------------------
    # Últimas atualizações
    # ---------------------------------------------------------

    def _build_latest_updates_html(self, updates):

        if not updates:
            return Markup(
                """
                <div style="
                    padding:30px;
                    text-align:center;
                    color:#777;
                ">
                    Nenhuma atualização registrada.
                </div>
                """
            )

        html = """
            <div style="overflow-x:auto;">

                <table style="
                    width:100%;
                    border-collapse:collapse;
                ">

                    <thead>

                        <tr style="
                            border-bottom:2px solid #E5E5E5;
                            text-align:left;
                        ">

                            <th style="padding:12px;">
                                Data
                            </th>

                            <th style="padding:12px;">
                                Aplicativo
                            </th>

                            <th style="padding:12px;">
                                Versão
                            </th>

                            <th style="padding:12px;">
                                Desenvolvedor
                            </th>

                            <th style="padding:12px;">
                                Alteração
                            </th>

                        </tr>

                    </thead>

                    <tbody>
        """

        for changelog in updates:

            date_text = "-"

            if changelog.commit_date:
                local_datetime = fields.Datetime.context_timestamp(
                    self,
                    changelog.commit_date,
                )

                date_text = local_datetime.strftime(
                    "%d/%m/%Y %H:%M"
                )

            module_name = (
                changelog.module_display_name
                or changelog.module_name
                or "-"
            )

            author = (
                changelog.author_name
                or changelog.committer_name
                or "-"
            )

            message = changelog.message or "-"

            if len(message) > 100:
                message = message[:100] + "..."

            html += """
                <tr style="
                    border-bottom:1px solid #EEEEEE;
                ">

                    <td style="
                        padding:12px;
                        white-space:nowrap;
                    ">
                        %s
                    </td>

                    <td style="padding:12px;">
                        <strong>%s</strong>
                    </td>

                    <td style="padding:12px;">
                        <span style="
                            background:#EDE7F6;
                            padding:4px 9px;
                            border-radius:12px;
                            font-size:12px;
                        ">
                            %s
                        </span>
                    </td>

                    <td style="padding:12px;">
                        %s
                    </td>

                    <td style="padding:12px;">
                        %s
                    </td>

                </tr>
            """ % (
                escape(date_text),
                escape(module_name),
                escape(changelog.version or "-"),
                escape(author),
                escape(message),
            )

        html += """
                    </tbody>

                </table>

            </div>
        """

        return Markup(html)
