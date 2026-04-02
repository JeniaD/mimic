import html as html_module
import smtplib
from email.mime.text import MIMEText

from jinja2 import BaseLoader, Environment


def render_personalization(template_str: str, target) -> str:
    if not template_str:
        return ""
    env = Environment(loader=BaseLoader(), autoescape=True)
    return env.from_string(str(template_str)).render(
        name=(target.name or "").strip(),
        text=(target.personal_text or "").strip(),
    )


def build_html_body(raw):
    if not raw:
        return ""
    s = str(raw)
    if "<" in s and ">" in s:
        return s
    lines = s.splitlines() or [s]
    esc = "<br/>".join(html_module.escape(line) for line in lines)
    return f"<p>{esc}</p>"


def append_tracking_footer(html_inner, open_url, click_url):
    footer = (
        f'<p><a href="{click_url}">Click here</a></p>'
        f'<img src="{open_url}" width="1" height="1" alt="" />'
    )
    return html_inner + footer


def send_smtp_html(asset, to_addr, subject, html_body):
    port = int(asset.port or 587)
    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = asset.email
    msg["To"] = to_addr
    if port == 465:
        with smtplib.SMTP_SSL(asset.server, port, timeout=30) as smtp:
            smtp.login(asset.email, asset.password)
            smtp.sendmail(asset.email, [to_addr], msg.as_string())
        return
    with smtplib.SMTP(asset.server, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(asset.email, asset.password)
        smtp.sendmail(asset.email, [to_addr], msg.as_string())
