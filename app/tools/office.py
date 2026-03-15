from __future__ import annotations


class SendEmailTool:
    name = "send_email"
    description = "Send an email via enterprise email gateway."
    required_roles = ["employee", "manager", "admin"]
    idempotent = True

    def run(self, params: dict[str, str]) -> dict[str, str]:
        to = params.get("to", "")
        subject = params.get("subject", "")
        body = params.get("body", "")
        return {"status": "sent", "to": to, "subject": subject, "body": body}


class CreateCalendarEventTool:
    name = "create_calendar_event"
    description = "Create a calendar event via enterprise calendar gateway."
    required_roles = ["employee", "manager", "admin"]
    idempotent = True

    def run(self, params: dict[str, str]) -> dict[str, str]:
        title = params.get("title", "Untitled")
        when = params.get("when", "unspecified")
        return {"status": "created", "title": title, "when": when}

