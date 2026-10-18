from __future__ import annotations

import secrets
from html import escape
from typing import Any, Dict


class ApprovalSkill:
    def __init__(self):
        self.tokens: Dict[str, Dict[str, Any]] = {}

    def create_token(self, outreach_id: str) -> str:
        token = secrets.token_urlsafe(16)
        self.tokens[token] = {"outreach_id": outreach_id, "status": "PENDING_APPROVAL", "used": False}
        return token

    def validate_token(self, token: str) -> bool:
        record = self.tokens.get(token)
        return bool(record and not record["used"])

    def approve(self, token: str) -> bool:
        record = self.tokens.get(token)
        if not record or record["used"]:
            return False
        record["used"] = True
        record["status"] = "APPROVED"
        return True

    def reject(self, token: str) -> bool:
        record = self.tokens.get(token)
        if not record or record["used"]:
            return False
        record["used"] = True
        record["status"] = "REJECTED"
        return True

    def build_review_email(
        self,
        target_name: str,
        company: str,
        score: int,
        message: str,
        approval_token: str,
        base_url: str = "http://127.0.0.1:8000",
        *,
        target_title: str = "",
        target_email: str = "",
        linkedin_url: str = "",
        job_title: str = "",
        job_url: str = "",
        outreach_subject: str = "",
    ) -> Dict[str, str]:
        base_url = base_url.rstrip("/")
        approve_url = f"{base_url}/api/approvals/{approval_token}/approve"
        reject_url = f"{base_url}/api/approvals/{approval_token}/reject"
        subject = f"[ReachAI] Approve outreach to {target_name} ({company}) ref {approval_token}"
        details = [
            f"Person: {target_name}" + (f" — {target_title}" if target_title else ""),
            f"Company: {company}",
            *([f"Will be sent to: {target_email}"] if target_email else []),
            *([f"LinkedIn: {linkedin_url}"] if linkedin_url else []),
            *([f"Job: {job_title}" + (f" ({job_url})" if job_url else "")] if job_title else []),
            f"Score: {score}/100",
        ]
        body = (
            "ReachAI outreach review\n\n"
            + "\n".join(details)
            + (f"\n\nSubject: {outreach_subject}" if outreach_subject else "")
            + f"\n\nDraft:\n{message}\n\n"
            f"Approve: {approve_url}\n"
            f"Reject: {reject_url}\n\n"
            "Or reply to this email with just APPROVE or REJECT."
        )

        def link(url: str, label: str) -> str:
            return f'<a href="{escape(url, quote=True)}" style="color:#155d3a">{escape(label)}</a>'

        rows = [
            ("Person", escape(target_name) + (f" — {escape(target_title)}" if target_title else "")),
            ("Company", escape(company)),
            *([("Sends to", escape(target_email))] if target_email else []),
            *([("LinkedIn", link(linkedin_url, "View profile"))] if linkedin_url else []),
            *([("Job", link(job_url, job_title) if job_url else escape(job_title))] if job_title else []),
            ("Score", f"{int(score)}/100"),
        ]
        button = (
            'display:inline-block;padding:12px 22px;border-radius:10px;font:600 15px system-ui,sans-serif;'
            "text-decoration:none;margin-right:10px"
        )
        html = (
            '<div style="font:15px/1.5 system-ui,sans-serif;color:#17231d;max-width:600px">'
            '<h2 style="margin:0 0 12px">Approve this outreach?</h2>'
            '<table style="border-collapse:collapse;margin-bottom:16px">'
            + "".join(
                f'<tr><td style="padding:3px 14px 3px 0;color:#5b6660">{label}</td><td style="padding:3px 0">{value}</td></tr>'
                for label, value in rows
            )
            + "</table>"
            + (f'<p style="margin:0 0 6px"><b>Subject:</b> {escape(outreach_subject)}</p>' if outreach_subject else "")
            + '<div style="white-space:pre-wrap;border:1px solid #d8d3c7;border-radius:10px;padding:14px;background:#fffdf7">'
            + escape(message)
            + "</div>"
            '<p style="margin:20px 0">'
            f'<a href="{escape(approve_url, quote=True)}" style="{button};background:#155d3a;color:#fff">Approve &amp; send</a>'
            f'<a href="{escape(reject_url, quote=True)}" style="{button};background:#eee;color:#17231d">Reject</a>'
            "</p>"
            '<p style="color:#5b6660;font-size:13px">Buttons need ReachAI running and reachable at '
            f"{escape(base_url)}. Or reply to this email with just <b>APPROVE</b> or <b>REJECT</b>.</p>"
            "</div>"
        )
        return {"subject": subject, "body": body, "html": html, "approve_url": approve_url, "reject_url": reject_url}
