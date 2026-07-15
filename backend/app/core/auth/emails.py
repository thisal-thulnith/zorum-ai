"""Dev email sender — SMTP to Mailpit (docker) at localhost:1025.

Phase 6 swaps this for Resend with the same send() signature.
View every dev email at http://localhost:8025.
"""

import smtplib
from email.message import EmailMessage

SMTP_HOST, SMTP_PORT = "localhost", 1025
FRONTEND_URL = "http://localhost:3000"


def send(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = "Zorum AI <noreply@zorum.local>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5) as smtp:
            smtp.send_message(msg)
    except OSError:
        # Dev convenience: a down mailpit shouldn't 500 the API. Log-and-continue.
        print(f"[email fallback] to={to} subject={subject}\n{body}")


def send_invitation(to: str, token: str, company: str) -> None:
    link = f"{FRONTEND_URL}/invite/{token}"
    send(
        to,
        f"You're invited to {company} on Zorum AI",
        f"You've been invited to join {company} on Zorum AI.\n\n"
        f"Accept your invitation (valid 7 days):\n{link}\n",
    )
