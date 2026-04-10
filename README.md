# cli-anything-moodle

Turn your Moodle LMS into an agent-native CLI. Built with the [CLI-Anything](https://github.com/HKUDS/CLI-Anything) methodology.

This tool wraps the **Moodle Web Services REST API** into a Python Click-based CLI with dual JSON/human output, so both AI agents (Claude Code, etc.) and humans can interact with Moodle from the terminal.

Tested on **Moodle 3.7** (NTNU) with automatic fallback for older API endpoints.

## Install

```bash
git clone https://github.com/OBlack42/cli-anything-moodle.git
cd cli-anything-moodle
pip install -e .
```

Requires **Python 3.10+**, `click`, and `requests`.

## Quick Start

```bash
# 1. Login to your Moodle site
moodle login --url https://moodle.yourschool.edu --username YOUR_ID --password YOUR_PASS

# 2. See everything at a glance
moodle -o human dashboard

# 3. Explore
moodle -o human courses
moodle -o human course-content 55812
moodle -o human assignments --course-id 55812
moodle -o human grades 55812
```

## Commands

### Auth

| Command | Description |
|---|---|
| `moodle login` | Authenticate and store token locally |
| `moodle whoami` | Show stored login info (no token) |
| `moodle site-info` | Full site and user metadata |
| `moodle logout` | Remove stored credentials |

### Courses

| Command | Description |
|---|---|
| `moodle courses` | List all enrolled courses |
| `moodle course-content COURSE_ID` | Sections, modules, and files in a course |
| `moodle search-courses QUERY` | Search courses by keyword |

### Assignments & Grades

| Command | Description |
|---|---|
| `moodle assignments` | List assignments (`--course-id` to filter) |
| `moodle assignment-status ASSIGN_ID` | Check submission status |
| `moodle submit-assignment ASSIGN_ID` | Submit for grading (`--text` for inline) |
| `moodle grades COURSE_ID` | Grade report for a course |
| `moodle grades-overview` | Grade summary across all courses |

### Calendar & Notifications

| Command | Description |
|---|---|
| `moodle calendar` | Upcoming events (`--days N`, `--course-id`) |
| `moodle notifications` | Notifications (`--limit`, `--unread-only`) |

### Messages

| Command | Description |
|---|---|
| `moodle conversations` | List conversations (`--type`, `--limit`) |
| `moodle send-message USER_ID TEXT` | Send a direct message |

### Forums

| Command | Description |
|---|---|
| `moodle forums COURSE_ID` | List forums in a course |
| `moodle forum-discussions FORUM_ID` | List discussion threads |
| `moodle forum-reply POST_ID MSG` | Reply to a post |

### Files & Dashboard

| Command | Description |
|---|---|
| `moodle download FILE_URL` | Download a file (`--dest` for path) |
| `moodle dashboard` | Quick overview: deadlines, notifications, courses |

## Output Modes

```bash
moodle courses                  # JSON (default, for agents)
moodle -o human courses         # human-readable table
moodle -o json courses | jq .   # pipe to jq for processing
```

All commands output structured JSON by default, making it trivial for AI agents to parse. Use `-o human` for terminal-friendly output.

## How It Works

```
moodle CLI ──> Moodle Web Services REST API ──> Your Moodle Server
                (POST /webservice/rest/server.php)
```

The CLI authenticates via `/login/token.php` using the `moodle_mobile_app` service (same as the official Moodle mobile app), then calls standard `wsfunction` endpoints with `moodlewsrestformat=json`.

Credentials are stored locally at `~/.config/cli-anything-moodle/config.json`.

## Compatibility

- **Moodle 3.7+** — notifications use `core_message_get_messages` fallback
- **Moodle 4.x** — uses modern `message_popup_get_popup_notifications` API
- Requires the `moodle_mobile_app` web service to be enabled on the server (enabled by default on most Moodle installations)

## Agent Integration

This CLI is designed to be used by AI coding agents. See [SKILL.md](SKILL.md) for the agent discovery spec.

Example with Claude Code:
```
> Use `moodle` to check my upcoming assignments and deadlines
> Download all PDFs from my Engineering Design course
> Summarize my unread notifications
```

## License

MIT
