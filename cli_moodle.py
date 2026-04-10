#!/usr/bin/env python3
"""CLI-Anything harness for Moodle LMS.

Wraps the Moodle Web Services REST API into a Click-based CLI with JSON output,
enabling AI agents (Claude Code, etc.) to interact with Moodle programmatically.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import click
import requests

# ---------------------------------------------------------------------------
# Config & State
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".config" / "cli-anything-moodle"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def _save_config(cfg: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def _require_config(keys: list[str]) -> dict:
    cfg = _load_config()
    missing = [k for k in keys if k not in cfg]
    if missing:
        click.echo(json.dumps({"error": f"Missing config: {', '.join(missing)}. Run `moodle login` first."}))
        sys.exit(1)
    return cfg


# ---------------------------------------------------------------------------
# Moodle API Client
# ---------------------------------------------------------------------------

class MoodleAPIError(Exception):
    def __init__(self, message: str, errorcode: str = ""):
        self.message = message
        self.errorcode = errorcode
        super().__init__(message)


class MoodleAPI:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.token = token
        self.endpoint = f"{self.url}/webservice/rest/server.php"

    def call(self, function: str, **params) -> dict | list:
        payload = {
            "wstoken": self.token,
            "wsfunction": function,
            "moodlewsrestformat": "json",
            **params,
        }
        r = requests.post(self.endpoint, data=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "exception" in data:
            raise MoodleAPIError(data.get("message", "Unknown API error"), data.get("errorcode", ""))
        return data

    def download_file(self, fileurl: str, dest: str):
        sep = "&" if "?" in fileurl else "?"
        r = requests.get(f"{fileurl}{sep}token={self.token}", stream=True, timeout=60)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


def _get_api() -> MoodleAPI:
    cfg = _require_config(["url", "token"])
    return MoodleAPI(cfg["url"], cfg["token"])


def _get_userid() -> int:
    cfg = _require_config(["userid"])
    return cfg["userid"]


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _out(data, human_fn=None):
    """Print JSON (default) or human-readable output."""
    ctx = click.get_current_context()
    if ctx.find_root().params.get("output") == "human" and human_fn:
        human_fn(data)
    else:
        click.echo(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _ts(epoch: int) -> str:
    if not epoch:
        return "-"
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# CLI Group
# ---------------------------------------------------------------------------

@click.group()
@click.option("--output", "-o", type=click.Choice(["json", "human"]), default="json", help="Output format.")
@click.version_option("1.0.0")
def cli(output):
    """Moodle CLI — agent-native interface to your Moodle LMS."""
    pass


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--url", prompt="Moodle site URL", help="e.g. https://moodle.school.edu")
@click.option("--username", prompt="Username", help="Moodle username")
@click.option("--password", prompt=True, hide_input=True, help="Moodle password")
@click.option("--service", default="moodle_mobile_app", help="Web service shortname.")
def login(url, username, password, service):
    """Authenticate with a Moodle site and store token locally."""
    url = url.rstrip("/")
    r = requests.get(
        f"{url}/login/token.php",
        params={"username": username, "password": password, "service": service},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()

    if "token" not in data:
        _out({"error": data.get("error", "Login failed")})
        sys.exit(1)

    token = data["token"]
    api = MoodleAPI(url, token)
    info = api.call("core_webservice_get_site_info")

    cfg = {
        "url": url,
        "token": token,
        "userid": info["userid"],
        "username": info["username"],
        "fullname": f"{info.get('firstname', '')} {info.get('lastname', '')}".strip(),
        "sitename": info.get("sitename", ""),
    }
    _save_config(cfg)

    _out({
        "status": "ok",
        "sitename": cfg["sitename"],
        "fullname": cfg["fullname"],
        "userid": cfg["userid"],
        "config_path": str(CONFIG_FILE),
    })


@cli.command("site-info")
def site_info():
    """Show current site and user info."""
    api = _get_api()
    info = api.call("core_webservice_get_site_info")

    def _human(d):
        click.echo(f"Site:     {d.get('sitename')}")
        click.echo(f"URL:      {d.get('siteurl')}")
        click.echo(f"User:     {d.get('fullname')} ({d.get('username')})")
        click.echo(f"UserID:   {d.get('userid')}")
        click.echo(f"Release:  {d.get('release')}")
        click.echo(f"Lang:     {d.get('lang')}")

    _out(info, _human)


@cli.command()
def whoami():
    """Show stored login info."""
    cfg = _load_config()
    if not cfg:
        _out({"error": "Not logged in. Run `moodle login`."})
        sys.exit(1)
    _out({k: v for k, v in cfg.items() if k != "token"})


@cli.command()
def logout():
    """Remove stored credentials."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
    _out({"status": "ok", "message": "Logged out."})


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--userid", type=int, default=None, help="User ID (default: self)")
def courses(userid):
    """List enrolled courses."""
    api = _get_api()
    uid = userid or _get_userid()
    data = api.call("core_enrol_get_users_courses", userid=uid)

    def _human(courses):
        for c in courses:
            vis = "" if c.get("visible") else " [hidden]"
            click.echo(f"  [{c['id']}] {c['fullname']}{vis}")

    _out(data, _human)


@cli.command("course-content")
@click.argument("course_id", type=int)
def course_content(course_id):
    """Get sections and modules for a course."""
    api = _get_api()
    data = api.call("core_course_get_contents", courseid=course_id)

    def _human(sections):
        for sec in sections:
            click.echo(f"\n=== {sec.get('name', 'Untitled')} ===")
            for mod in sec.get("modules", []):
                icon = {"assign": "HW", "forum": "FORUM", "resource": "FILE", "url": "LINK", "quiz": "QUIZ", "page": "PAGE"}.get(mod.get("modname"), mod.get("modname", "?").upper())
                click.echo(f"  [{icon}] {mod['name']}  (id={mod['id']})")
                for f in mod.get("contents", []):
                    click.echo(f"        -> {f['filename']}  ({f.get('filesize', 0)} bytes)")

    _out(data, _human)


@cli.command("search-courses")
@click.argument("query")
@click.option("--page", default=0)
@click.option("--perpage", default=20)
def search_courses(query, page, perpage):
    """Search courses by keyword."""
    api = _get_api()
    data = api.call("core_course_search_courses", criterianame="search", criteriavalue=query, page=page, perpage=perpage)
    _out(data)


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--course-id", type=int, multiple=True, help="Course IDs to filter (repeatable).")
def assignments(course_id):
    """List assignments (optionally filtered by course)."""
    api = _get_api()
    params = {}
    for i, cid in enumerate(course_id):
        params[f"courseids[{i}]"] = cid

    data = api.call("mod_assign_get_assignments", **params)

    def _human(d):
        for course in d.get("courses", []):
            click.echo(f"\n--- {course['fullname']} ---")
            for a in course.get("assignments", []):
                due = _ts(a.get("duedate", 0))
                click.echo(f"  [{a['id']}] {a['name']}  (due: {due})")

    _out(data, _human)


@cli.command("assignment-status")
@click.argument("assignment_id", type=int)
def assignment_status(assignment_id):
    """Get submission status for an assignment."""
    api = _get_api()
    data = api.call("mod_assign_get_submissions", **{
        "assignmentids[0]": assignment_id,
    })
    _out(data)


@cli.command("submit-assignment")
@click.argument("assignment_id", type=int)
@click.option("--text", help="Online text submission content.")
@click.option("--accept-statement", is_flag=True, default=True, help="Accept submission statement.")
def submit_assignment(assignment_id, text, accept_statement):
    """Submit an assignment for grading."""
    api = _get_api()
    if text:
        api.call("mod_assign_save_submission",
                 assignmentid=assignment_id,
                 **{"plugindata[onlinetext_editor][text]": text,
                    "plugindata[onlinetext_editor][format]": 1})

    data = api.call("mod_assign_submit_for_grading",
                    assignmentid=assignment_id,
                    acceptsubmissionstatement=1 if accept_statement else 0)
    _out({"status": "submitted", "assignment_id": assignment_id, "warnings": data.get("warnings", [])})


# ---------------------------------------------------------------------------
# Grades
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("course_id", type=int)
@click.option("--userid", type=int, default=None)
def grades(course_id, userid):
    """Get grade report for a course."""
    api = _get_api()
    uid = userid or _get_userid()
    data = api.call("gradereport_user_get_grades_table", courseid=course_id, userid=uid)

    def _human(d):
        for table in d.get("tables", []):
            click.echo(f"\nGrades for course {table.get('courseid')}:")
            for row in table.get("tabledata", []):
                if not isinstance(row, dict):
                    continue
                item = row.get("itemname", {})
                grade = row.get("grade", {})
                name = item.get("content", "") if isinstance(item, dict) else str(item)
                val = grade.get("content", "") if isinstance(grade, dict) else str(grade)
                if name:
                    # Strip HTML tags for human output
                    import re
                    name = re.sub(r"<[^>]+>", "", name).strip()
                    val = re.sub(r"<[^>]+>", "", val).strip() if val else "-"
                    click.echo(f"  {name}: {val}")

    _out(data, _human)


@cli.command("grades-overview")
def grades_overview():
    """Get grade overview across all courses."""
    api = _get_api()
    uid = _get_userid()
    data = api.call("gradereport_overview_get_course_grades", userid=uid)

    def _human(d):
        for g in d.get("grades", []):
            click.echo(f"  Course {g['courseid']}: {g.get('grade', '-')}")

    _out(data, _human)


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--course-id", type=int, multiple=True, help="Filter by course (repeatable).")
@click.option("--days", type=int, default=30, help="Look ahead N days.")
def calendar(course_id, days):
    """Get upcoming calendar events."""
    api = _get_api()
    now = int(time.time())
    end = now + days * 86400

    params = {
        "options[userevents]": 1,
        "options[siteevents]": 1,
        "options[timestart]": now,
        "options[timeend]": end,
    }
    for i, cid in enumerate(course_id):
        params[f"events[courseids][{i}]"] = cid

    data = api.call("core_calendar_get_calendar_events", **params)

    def _human(d):
        events = d.get("events", [])
        if not events:
            click.echo("  No upcoming events.")
            return
        for e in sorted(events, key=lambda x: x.get("timestart", 0)):
            ts = _ts(e.get("timestart"))
            click.echo(f"  [{e['id']}] {ts}  {e['name']}  ({e.get('eventtype', '')})")

    _out(data, _human)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--limit", type=int, default=20, help="Max notifications to fetch.")
@click.option("--unread-only", is_flag=True, help="Only show unread.")
def notifications(limit, unread_only):
    """Get notifications (compatible with Moodle 3.7+)."""
    api = _get_api()
    uid = _get_userid()

    # Try modern API first, fall back to core_message_get_messages for Moodle 3.x
    try:
        data = api.call("message_popup_get_popup_notifications",
                        useridto=uid, newestfirst=1, limitfrom=0, limitnum=limit)
        notifs = data.get("notifications", [])
        if unread_only:
            notifs = [n for n in notifs if not n.get("read")]
            data["notifications"] = notifs
    except MoodleAPIError:
        # Moodle 3.x fallback
        data = api.call("core_message_get_messages",
                        useridto=uid, useridfrom=0, type="notifications",
                        read=0, limitfrom=0, limitnum=limit)
        if not unread_only:
            read_msgs = api.call("core_message_get_messages",
                                 useridto=uid, useridfrom=0, type="notifications",
                                 read=1, limitfrom=0, limitnum=limit)
            data["messages"] = data.get("messages", []) + read_msgs.get("messages", [])
            data["messages"].sort(key=lambda m: m.get("timecreated", 0), reverse=True)
            data["messages"] = data["messages"][:limit]
        notifs = data.get("messages", [])

    def _human(d):
        items = d.get("notifications", d.get("messages", []))
        for n in items:
            read_mark = " " if n.get("read") or n.get("timeread") else "*"
            ts = _ts(n.get("timecreated"))
            subject = n.get("subject", "(no subject)")
            nid = n.get("id")
            click.echo(f"  {read_mark} [{nid}] {ts}  {subject}")

    _out(data, _human)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--type", "conv_type", type=click.Choice(["all", "individual", "group"]), default="all")
@click.option("--limit", type=int, default=20)
def conversations(conv_type, limit):
    """List message conversations."""
    api = _get_api()
    uid = _get_userid()
    type_map = {"all": 0, "individual": 1, "group": 2}
    params = {"userid": uid, "limitfrom": 0, "limitnum": limit}
    if conv_type != "all":
        params["type"] = type_map[conv_type]

    data = api.call("core_message_get_conversations", **params)

    def _human(d):
        for c in d.get("conversations", []):
            unread = f" ({c['unreadcount']} unread)" if c.get("unreadcount") else ""
            name = c.get("name") or ", ".join(m.get("fullname", "?") for m in c.get("members", []))
            click.echo(f"  [{c['id']}] {name}{unread}")

    _out(data, _human)


@cli.command("send-message")
@click.argument("to_user_id", type=int)
@click.argument("text")
def send_message(to_user_id, text):
    """Send a direct message to a user."""
    api = _get_api()
    data = api.call("core_message_send_instant_messages", **{
        "messages[0][touserid]": to_user_id,
        "messages[0][text]": text,
        "messages[0][textformat]": 1,
    })
    _out(data)


# ---------------------------------------------------------------------------
# Forums
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("course_id", type=int)
def forums(course_id):
    """List forums in a course."""
    api = _get_api()
    data = api.call("mod_forum_get_forums_by_courses", **{"courseids[0]": course_id})

    def _human(forums):
        for f in forums:
            click.echo(f"  [{f['id']}] {f['name']}  ({f.get('type', '')})")

    _out(data, _human)


@cli.command("forum-discussions")
@click.argument("forum_id", type=int)
@click.option("--sort", type=click.Choice(["lastpost", "created", "replies"]), default="lastpost")
@click.option("--limit", type=int, default=20)
def forum_discussions(forum_id, sort, limit):
    """List discussions in a forum."""
    api = _get_api()
    data = api.call("mod_forum_get_forum_discussions",
                    forumid=forum_id, sortby=sort, sortdirection="DESC", page=0, perpage=limit)

    def _human(d):
        for disc in d.get("discussions", []):
            ts = _ts(disc.get("timemodified"))
            click.echo(f"  [{disc['id']}] {disc['name']}  (replies: {disc.get('numreplies', 0)}, updated: {ts})")

    _out(data, _human)


@cli.command("forum-reply")
@click.argument("post_id", type=int)
@click.argument("message")
@click.option("--subject", default="Re:", help="Reply subject.")
def forum_reply(post_id, message, subject):
    """Reply to a forum post."""
    api = _get_api()
    data = api.call("mod_forum_add_discussion_post",
                    postid=post_id, subject=subject, message=message, messageformat=1)
    _out(data)


# ---------------------------------------------------------------------------
# File Download
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("file_url")
@click.option("--dest", "-d", default=".", help="Destination directory or file path.")
def download(file_url, dest):
    """Download a file from Moodle using its fileurl."""
    api = _get_api()
    dest_path = Path(dest)
    if dest_path.is_dir():
        # Extract filename from URL
        from urllib.parse import urlparse, unquote
        parsed = urlparse(file_url)
        fname = unquote(parsed.path.split("/")[-1]) or "download"
        dest_path = dest_path / fname

    api.download_file(file_url, str(dest_path))
    _out({"status": "ok", "path": str(dest_path), "size": dest_path.stat().st_size})


# ---------------------------------------------------------------------------
# Bulk / Convenience
# ---------------------------------------------------------------------------

@cli.command()
def dashboard():
    """Quick overview: upcoming deadlines, unread notifications, recent grades."""
    api = _get_api()
    uid = _get_userid()

    # Upcoming calendar (7 days)
    now = int(time.time())
    cal = api.call("core_calendar_get_calendar_events", **{
        "options[userevents]": 1,
        "options[siteevents]": 1,
        "options[timestart]": now,
        "options[timeend]": now + 7 * 86400,
    })

    # Unread notifications (with Moodle 3.x fallback)
    try:
        notifs = api.call("message_popup_get_popup_notifications",
                          useridto=uid, newestfirst=1, limitfrom=0, limitnum=5)
        unread_notifs = [n for n in notifs.get("notifications", []) if not n.get("read")]
    except MoodleAPIError:
        notifs = api.call("core_message_get_messages",
                          useridto=uid, useridfrom=0, type="notifications",
                          read=0, limitfrom=0, limitnum=5)
        unread_notifs = notifs.get("messages", [])

    # Courses
    courses = api.call("core_enrol_get_users_courses", userid=uid)

    result = {
        "upcoming_events": cal.get("events", []),
        "unread_notifications": unread_notifs,
        "enrolled_courses": [{"id": c["id"], "fullname": c["fullname"]} for c in courses],
    }

    def _human(d):
        click.echo("=== Upcoming (7 days) ===")
        for e in sorted(d["upcoming_events"], key=lambda x: x.get("timestart", 0)):
            click.echo(f"  {_ts(e.get('timestart'))}  {e['name']}")
        if not d["upcoming_events"]:
            click.echo("  (none)")

        click.echo(f"\n=== Unread Notifications ({len(d['unread_notifications'])}) ===")
        for n in d["unread_notifications"][:5]:
            click.echo(f"  * {n.get('subject', '(no subject)')}")

        click.echo(f"\n=== Courses ({len(d['enrolled_courses'])}) ===")
        for c in d["enrolled_courses"]:
            click.echo(f"  [{c['id']}] {c['fullname']}")

    _out(result, _human)


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
