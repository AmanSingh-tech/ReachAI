from __future__ import annotations

from pathlib import Path


class ReportGenerator:
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _summary_cards(self, summary: dict) -> str:
        cards = [
            ("Jobs discovered", summary.get("jobs_discovered", 0)),
            ("Pending approval", summary.get("pending_approval", 0)),
            ("Approved", summary.get("approved", 0)),
            ("Sent", summary.get("sent", 0)),
        ]
        rendered = "\n".join(
            f"<div class='card'><div class='label'>{label}</div><div class='value'>{value}</div></div>"
            for label, value in cards
        )
        return rendered

    def build(self, summary: dict) -> str:
        html = f"""
<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>ReachAI Dashboard</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 0; background: #f5f7fb; color: #122033; }}
      .container {{ max-width: 1100px; margin: 32px auto; padding: 24px; }}
      .header {{ margin-bottom: 24px; }}
      .header h1 {{ margin: 0 0 8px; }}
      .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin: 24px 0; }}
      .card {{ background: white; border-radius: 12px; border: 1px solid #dfe7f5; padding: 20px; box-shadow: 0 4px 12px rgba(18,32,51,.05); }}
      .label {{ color: #60718f; font-size: 13px; text-transform: uppercase; letter-spacing: .04em; }}
      .value {{ font-size: 32px; font-weight: bold; margin-top: 10px; }}
      .panel {{ background: white; border-radius: 12px; border: 1px solid #dfe7f5; padding: 20px; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ text-align: left; padding: 12px 10px; border-bottom: 1px solid #edf1f7; }}
      th {{ color: #60718f; font-size: 12px; text-transform: uppercase; }}
    </style>
  </head>
  <body>
    <div class=\"container\">
      <div class=\"header\">
        <h1>ReachAI Dashboard</h1>
        <p>Local-first outreach performance summary.</p>
      </div>
      <div class=\"cards\">
        {self._summary_cards(summary)}
      </div>
      <div class=\"panel\">
        <h2>Summary</h2>
        <table>
          <thead>
            <tr>
              <th>Metric</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Jobs discovered</td><td>{summary.get('jobs_discovered', 0)}</td></tr>
            <tr><td>Pending approval</td><td>{summary.get('pending_approval', 0)}</td></tr>
            <tr><td>Approved</td><td>{summary.get('approved', 0)}</td></tr>
            <tr><td>Sent</td><td>{summary.get('sent', 0)}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
    <p>Jobs discovered: {summary.get('jobs_discovered', 0)}</p>
    <p>Pending approval: {summary.get('pending_approval', 0)}</p>
    <p>Approved: {summary.get('approved', 0)}</p>
    <p>Sent: {summary.get('sent', 0)}</p>
  </body>
</html>
"""
        path = self.output_dir / "reachai-dashboard.html"
        path.write_text(html, encoding="utf-8")
        return str(path)

    def build_report(self, summary: dict) -> str:
        return self.build(summary)
