# cli-anything-moodle

Agent-native CLI for Moodle LMS. Wraps the Moodle Web Services REST API into structured commands with JSON output.

## Install

```bash
cd cli-anything-moodle && pip install -e .
```

## Auth

```bash
moodle login --url https://moodle.school.edu --username USER --password PASS
moodle whoami          # show stored login
moodle site-info       # full site metadata
moodle logout          # remove credentials
```

## Commands

| Command | Description | Key Options |
|---|---|---|
| `moodle courses` | List enrolled courses | `--userid` |
| `moodle course-content COURSE_ID` | Sections, modules, files in a course | |
| `moodle search-courses QUERY` | Search courses by keyword | `--page`, `--perpage` |
| `moodle assignments` | List assignments | `--course-id` (repeatable) |
| `moodle assignment-status ASSIGN_ID` | Submission status | |
| `moodle submit-assignment ASSIGN_ID` | Submit for grading | `--text` |
| `moodle grades COURSE_ID` | Grade report for a course | `--userid` |
| `moodle grades-overview` | Grades across all courses | |
| `moodle calendar` | Upcoming events | `--course-id`, `--days` |
| `moodle notifications` | Popup notifications | `--limit`, `--unread-only` |
| `moodle mark-read NOTIF_ID` | Mark notification read | |
| `moodle conversations` | Message conversations | `--type`, `--limit` |
| `moodle send-message USER_ID TEXT` | Send direct message | |
| `moodle forums COURSE_ID` | List forums | |
| `moodle forum-discussions FORUM_ID` | List discussions | `--sort`, `--limit` |
| `moodle forum-reply POST_ID MSG` | Reply to a post | `--subject` |
| `moodle download FILE_URL` | Download a file | `--dest` |
| `moodle dashboard` | Quick overview (deadlines, notifications, courses) | |

## Output

All commands default to `--output json`. Use `--output human` for readable output.

```bash
moodle --output json courses         # for agents
moodle --output human dashboard      # for humans
```

## Typical Agent Workflow

```bash
# 1. Login
moodle login --url https://moodle.school.edu --username stu --password ***

# 2. Dashboard overview
moodle dashboard

# 3. Drill into a course
moodle course-content 42

# 4. Check assignments & grades
moodle assignments --course-id 42
moodle grades 42

# 5. Download a resource
moodle download "https://moodle.school.edu/pluginfile.php/..." --dest ./

# 6. Check messages
moodle conversations
moodle send-message 15 "Hi, about the group project..."
```
