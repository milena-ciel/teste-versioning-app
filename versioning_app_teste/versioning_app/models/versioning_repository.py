import logging
from datetime import datetime

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
REQUEST_TIMEOUT = 20


class VersioningRepository(models.Model):
    _name = "versioning.repository"
    _description = "Repositório GitHub monitorado"
    _order = "repo_kind, name"

    name = fields.Char(required=True)
    github_owner = fields.Char(required=True, string="Owner/Organização")
    github_repo = fields.Char(required=True, string="Repositório")
    branch = fields.Char(default="main", required=True)
    access_token = fields.Char(string="Token de acesso", groups="base.group_system")
    repo_kind = fields.Selection(
        [("own", "Repositório do cliente"), ("shared", "Localização compartilhada")],
        default="own",
        required=True,
    )
    poll_interval_minutes = fields.Selection(
        [("15", "15 minutos"), ("30", "30 minutos"), ("60", "1 hora")],
        default="30",
        required=True,
    )
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ("draft", "Não testado"),
            ("connected", "Conectado"),
            ("error", "Erro de conexão"),
        ],
        default="draft",
    )
    last_error = fields.Char(readonly=True)
    current_version = fields.Char(default="1.0.0", readonly=True)
    last_checked = fields.Datetime(readonly=True)
    last_commit_sha = fields.Char(readonly=True)
    changelog_ids = fields.One2many(
        "versioning.changelog", "repository_id", string="Atualizações"
    )
    changelog_count = fields.Integer(compute="_compute_changelog_count")

    @api.depends("changelog_ids")
    def _compute_changelog_count(self):
        for rec in self:
            rec.changelog_count = len(rec.changelog_ids)

    def _github_headers(self):
        self.ensure_one()
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.access_token:
            headers["Authorization"] = "Bearer %s" % self.access_token
        return headers

    def action_test_connection(self):
        for rec in self:
            url = "%s/repos/%s/%s" % (GITHUB_API, rec.github_owner, rec.github_repo)
            try:
                resp = requests.get(
                    url, headers=rec._github_headers(), timeout=REQUEST_TIMEOUT
                )
                if resp.status_code == 200:
                    rec.write({"state": "connected", "last_error": False})
                else:
                    rec.write(
                        {
                            "state": "error",
                            "last_error": "HTTP %s: %s"
                            % (resp.status_code, resp.text[:200]),
                        }
                    )
            except requests.RequestException as exc:
                rec.write({"state": "error", "last_error": str(exc)[:200]})
        return True

    def action_check_now(self):
        for rec in self:
            rec._poll_repository()
        return True

    @api.model
    def _cron_poll_repositories(self):
        repos = self.search([("active", "=", True)])
        for rec in repos:
            try:
                rec._poll_repository()
            except Exception:
                _logger.exception("Falha ao verificar o repositório %s", rec.name)

    def _poll_repository(self):
        self.ensure_one()
        params = {"sha": self.branch, "per_page": 50}
        if self.last_checked:
            params["since"] = self.last_checked.strftime("%Y-%m-%dT%H:%M:%SZ")

        url = "%s/repos/%s/%s/commits" % (
            GITHUB_API,
            self.github_owner,
            self.github_repo,
        )
        try:
            resp = requests.get(
                url,
                headers=self._github_headers(),
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            self.write(
                {
                    "state": "error",
                    "last_error": str(exc)[:200],
                    "last_checked": fields.Datetime.now(),
                }
            )
            return

        if resp.status_code != 200:
            self.write(
                {
                    "state": "error",
                    "last_error": "HTTP %s: %s" % (resp.status_code, resp.text[:200]),
                    "last_checked": fields.Datetime.now(),
                }
            )
            return

        commits = resp.json()
        commits = [c for c in commits if c.get("sha") != self.last_commit_sha]
        commits.reverse()  # processa do mais antigo para o mais novo

        Changelog = self.env["versioning.changelog"]
        new_changelogs = Changelog

        for commit in commits:
            sha = commit["sha"]
            if Changelog.search_count(
                [("repository_id", "=", self.id), ("commit_sha", "=", sha)]
            ):
                continue

            detail = self._fetch_commit_detail(sha)
            files_changed = [f["filename"] for f in (detail.get("files") or [])]
            module_name = self._guess_module_name(files_changed)
            new_version = self._bump_version(self.current_version)
            commit_info = commit.get("commit", {})

            changelog = Changelog.create(
                {
                    "repository_id": self.id,
                    "commit_sha": sha,
                    "author_name": commit_info.get("author", {}).get("name"),
                    "author_email": commit_info.get("author", {}).get("email"),
                    "committer_name": commit_info.get("committer", {}).get("name"),
                    "message": commit_info.get("message"),
                    "module_name": module_name,
                    "files_changed": "\n".join(files_changed),
                    "version": new_version,
                    "commit_date": self._parse_github_datetime(
                        commit_info.get("author", {}).get("date")
                    ),
                    "github_url": commit.get("html_url"),
                }
            )
            self.current_version = new_version
            new_changelogs |= changelog

        vals = {"state": "connected", "last_error": False, "last_checked": fields.Datetime.now()}
        if commits:
            vals["last_commit_sha"] = commits[-1]["sha"]
        self.write(vals)

        for changelog in new_changelogs:
            changelog._notify_recipients()

    def _fetch_commit_detail(self, sha):
        self.ensure_one()
        url = "%s/repos/%s/%s/commits/%s" % (
            GITHUB_API,
            self.github_owner,
            self.github_repo,
            sha,
        )
        try:
            resp = requests.get(
                url, headers=self._github_headers(), timeout=REQUEST_TIMEOUT
            )
            if resp.status_code == 200:
                return resp.json()
        except requests.RequestException:
            _logger.exception("Falha ao buscar detalhes do commit %s", sha)
        return {}

    @staticmethod
    def _guess_module_name(files_changed):
        if not files_changed:
            return False
        first_path = files_changed[0]
        return first_path.split("/")[0] if "/" in first_path else first_path

    @staticmethod
    def _parse_github_datetime(value):
        if not value:
            return False
        try:
            dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            return fields.Datetime.to_string(dt)
        except ValueError:
            return False

    @staticmethod
    def _bump_version(current_version):
        try:
            major, minor, patch = (int(p) for p in (current_version or "1.0.0").split("."))
        except ValueError:
            major, minor, patch = 1, 0, 0
        patch += 1
        return "%s.%s.%s" % (major, minor, patch)
