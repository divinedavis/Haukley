#!/usr/bin/env python3
"""Send Haukley business email FROM hello@haukley.com (Namecheap Private Email).

    python3 scripts/send_mail.py --to someone@studio.com --subject "..." --body-file pitch.txt
    python3 scripts/send_mail.py --to a@x.com --cc b@x.com --subject "..." --body "..." [--dry-run]

Owner rule (2026-10-09): Haukley outreach goes out from the haukley.com mailbox, never the
owner's personal Gmail (the Gmail connector can't set a From address). The message is sent
over SMTP (mail.privateemail.com:465) and a copy is appended to the mailbox's Sent folder
over IMAP, so the thread lives in hello@haukley.com where replies land.

Credentials: ~/.config/haukley/smtp.json (mode 600; app password "Haukley scripts").
"""
import argparse
import imaplib
import json
import smtplib
import sys
import time
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

CONF = Path.home() / ".config" / "haukley" / "smtp.json"
SIGNATURE = "\n\nDivine Davis\nFounder, Haukley · hello@haukley.com · https://haukley.com\n"


def build(args, user):
    body = Path(args.body_file).read_text() if args.body_file else args.body
    if "hello@haukley.com" not in body:
        body = body.rstrip() + SIGNATURE
    m = EmailMessage()
    m["From"] = formataddr(("Divine Davis (Haukley)", user))
    m["To"] = ", ".join(args.to)
    if args.cc:
        m["Cc"] = ", ".join(args.cc)
    m["Reply-To"] = user
    m["Subject"] = args.subject
    m["Message-ID"] = make_msgid(domain="haukley.com")
    m.set_content(body)
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--to", action="append", required=True)
    ap.add_argument("--cc", action="append", default=[])
    ap.add_argument("--subject", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--body")
    g.add_argument("--body-file")
    ap.add_argument("--dry-run", action="store_true", help="print the message, send nothing")
    a = ap.parse_args()
    c = json.loads(CONF.read_text())
    msg = build(a, c["user"])
    if a.dry_run:
        print(msg)
        return
    with smtplib.SMTP_SSL(c["host"], c["smtp_port"], timeout=60) as s:
        s.login(c["user"], c["password"])
        s.send_message(msg)
    with imaplib.IMAP4_SSL(c["host"], c["imap_port"]) as i:
        i.login(c["user"], c["password"])
        i.append("Sent", r"(\Seen)", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
    print(f"sent from {c['user']} to {', '.join(a.to + a.cc)}: {a.subject} ({msg['Message-ID']})")


if __name__ == "__main__":
    sys.exit(main())
