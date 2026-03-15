"""FakeGitHub: in-memory GitHub state for testing.

Extracted from scripts/test_lifecycle.py and extended with:
- PR create/review/merge
- Issue edit/close
- Run list with --branch filter
- Release create with full flag parsing
- dump_state() for test assertions
- Dispatch-dict routing in handle()
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone


class FakeGitHub:
    """Simulate GitHub API responses for gh CLI calls."""

    def __init__(self):
        self.labels: dict[str, dict] = {}
        self.milestones: list[dict] = []
        self.issues: list[dict] = []
        self.releases: list[dict] = []
        self.runs: list[dict] = []
        self.prs: list[dict] = []
        self.reviews: list[dict] = []
        self.timeline_events: dict[int, list[dict]] = {}  # issue# -> events
        self.comparisons: dict[str, dict] = {}  # branch -> {behind_by, ahead_by}
        self.commits_data: list[dict] = []       # commit objects for /commits endpoint
        self._next_issue = 1
        self._next_ms = 1
        self._next_pr = 1

    # -- Dispatch ------------------------------------------------------------

    _DISPATCH: dict[str, str] = {
        "label": "_handle_label",
        "api": "_handle_api",
        "issue": "_handle_issue",
        "run": "_handle_run",
        "pr": "_handle_pr",
        "release": "_handle_release",
        "auth": "_handle_auth",
        "--version": "_handle_version",
    }

    def handle(self, args: list[str]) -> subprocess.CompletedProcess:
        """Dispatch gh CLI args to the appropriate handler."""
        if not args:
            return self._fail("no args")

        cmd = args[0]
        method_name = self._DISPATCH.get(cmd)
        if method_name is None:
            return self._fail(f"unknown command: {cmd}")

        method = getattr(self, method_name)
        # auth and --version take no sub-args
        if cmd in ("auth", "--version"):
            return method()
        return method(args[1:])

    # -- Helpers --------------------------------------------------------------

    def _ok(self, stdout: str) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=stdout, stderr="",
        )

    def _fail(self, msg: str) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=msg,
        )

    @staticmethod
    def _filter_json_fields(items: list[dict], fields: str | None) -> list[dict]:
        """Filter each dict to only the requested --json fields.

        If *fields* is None or empty, return items unchanged.
        *fields* is a comma-separated string like ``"number,title"``.
        """
        if not fields:
            return items
        keys = [f.strip() for f in fields.split(",") if f.strip()]
        if not keys:
            return items
        return [{k: item.get(k) for k in keys} for item in items]

    # Flags that are accepted but ignored (no-op in test context).
    # --paginate: FakeGitHub returns all data, so pagination is implicit.
    # --jq: FakeGitHub returns full JSON; callers must handle both formats.
    # --notes-file: release notes content not needed by most tests.
    _ACCEPTED_NOOP_FLAGS = frozenset(("paginate", "notes-file"))

    # Known flags per handler, mapping handler name -> set of recognized flags.
    # Flags in this registry + _ACCEPTED_NOOP_FLAGS are allowed.
    # Anything else raises NotImplementedError.
    _KNOWN_FLAGS: dict[str, frozenset[str]] = {
        "issue_create": frozenset(("title", "body", "label", "milestone")),
        "issue_list": frozenset(("state", "milestone", "json", "limit", "label")),
        "issue_edit": frozenset(("add-label", "remove-label", "milestone")),
        "issue_close": frozenset(),
        "run_list": frozenset(("branch", "json", "limit", "status")),
        "pr_list": frozenset(("json", "state", "limit", "search")),
        "pr_create": frozenset(("title", "body", "base", "head", "label", "milestone")),
        "pr_review": frozenset(("body", "approve", "request-changes")),
        "pr_merge": frozenset(("squash", "merge", "rebase")),
        "release_create": frozenset(("tag", "title", "notes", "notes-file", "target")),
        "release_view": frozenset(("json", "jq")),
        "label_create": frozenset(("color", "description", "force")),
        # NOTE: --jq is accepted but NOT evaluated. FakeGitHub returns
        # pre-shaped data that matches what production jq filters would produce.
        # Tests using jq-dependent endpoints verify the fixture shape, not jq
        # filter correctness. Endpoints that rely on jq filtering:
        #   - /issues/{N}/timeline (| first) → returns first linked PR
        #   - /commits (.[].sha, .[].commit.message) → returns commits_data
        # If jq fidelity becomes critical, implement pyjq or basic expression eval.
        "api": frozenset(("paginate", "f", "X", "jq")),
    }

    # Flags that always consume the next argument as their value,
    # even if it starts with a dash (e.g., --title "-1 Fix bug").
    _VALUE_BEARING_FLAGS = frozenset((
        "title", "body", "milestone", "jq", "json", "label", "state",
        "limit", "branch", "base", "head", "notes", "notes-file",
        "tag", "target", "color", "description", "add-label",
        "remove-label", "status",
    ))

    @classmethod
    def _parse_flags(cls, args: list[str], start: int = 1) -> dict[str, list[str]]:
        """Parse --flag/​-f value pairs into a dict.

        Flags that appear multiple times get multiple values in the list.
        Bare flags (no value) get ["true"].
        Supports both long flags (--flag) and short flags (-f, -X).
        """
        flags: dict[str, list[str]] = {}
        i = start
        while i < len(args):
            a = args[i]
            if a.startswith("--"):
                key = a[2:]  # strip leading --
                # Handle --flag=value syntax
                if "=" in key:
                    key, eq_val = key.split("=", 1)
                    flags.setdefault(key, []).append(eq_val)
                    i += 1
                    continue
                # Value-bearing flags always consume next arg regardless of prefix
                if key in cls._VALUE_BEARING_FLAGS and i + 1 < len(args):
                    flags.setdefault(key, []).append(args[i + 1])
                    i += 2
                elif i + 1 < len(args) and not args[i + 1].startswith("-"):
                    flags.setdefault(key, []).append(args[i + 1])
                    i += 2
                else:
                    flags.setdefault(key, []).append("true")
                    i += 1
            elif len(a) == 2 and a.startswith("-") and a[1].isalpha():
                key = a[1]  # strip leading -
                # Short flags with values: -f "title=val", -X PATCH
                if i + 1 < len(args) and not args[i + 1].startswith("-"):
                    flags.setdefault(key, []).append(args[i + 1])
                    i += 2
                else:
                    flags.setdefault(key, []).append("true")
                    i += 1
            else:
                i += 1
        return flags

    @classmethod
    def _check_flags(cls, handler_name: str, flags: dict[str, list[str]]) -> None:
        """Raise NotImplementedError for flags not in the known registry.

        This prevents tests from silently passing when production code
        sends flags that FakeGitHub doesn't handle.
        """
        known = cls._KNOWN_FLAGS.get(handler_name, frozenset())
        allowed = known | cls._ACCEPTED_NOOP_FLAGS
        for flag in flags:
            if flag not in allowed:
                raise NotImplementedError(
                    f"FakeGitHub handler '{handler_name}' does not handle "
                    f"flag '--{flag}'. Add it to _KNOWN_FLAGS['{handler_name}'] "
                    f"or _ACCEPTED_NOOP_FLAGS if it's intentionally ignored."
                )

    # -- Handlers: auth / version ---------------------------------------------

    def _handle_auth(self) -> subprocess.CompletedProcess:
        return self._ok("")

    def _handle_version(self) -> subprocess.CompletedProcess:
        return self._ok("gh version 2.40.0 (fake)")

    # -- Handler: label -------------------------------------------------------

    def _handle_label(self, args: list[str]) -> subprocess.CompletedProcess:
        if not args or args[0] != "create":
            return self._fail("only label create supported")
        name = args[1] if len(args) > 1 else ""
        color = ""
        desc = ""
        i = 2
        while i < len(args):
            if args[i] == "--color" and i + 1 < len(args):
                color = args[i + 1]
                i += 2
            elif args[i] == "--description" and i + 1 < len(args):
                desc = args[i + 1]
                i += 2
            elif args[i] == "--force":
                i += 1
            else:
                i += 1
        self.labels[name] = {"name": name, "color": color, "description": desc}
        return self._ok("")

    # -- Handler: api ---------------------------------------------------------

    def _handle_api(self, args: list[str]) -> subprocess.CompletedProcess:
        if not args:
            return self._fail("no api path")
        path = args[0]
        # Validate known flags (api uses -f and -X as short flags)
        flags = self._parse_flags(args, start=1)
        self._check_flags("api", flags)
        # Create milestone
        if "milestones" in path and "-f" in args:
            title = ""
            description = ""
            for i, a in enumerate(args):
                if a == "-f" and i + 1 < len(args):
                    kv = args[i + 1]
                    if kv.startswith("title="):
                        title = kv[6:]
                    elif kv.startswith("description="):
                        description = kv[12:]
            # Reject duplicate milestone titles
            for existing_ms in self.milestones:
                if existing_ms["title"] == title:
                    return self._fail(
                        f"Validation Failed: milestone title '{title}' already exists"
                    )
            ms = {
                "number": self._next_ms,
                "title": title,
                "description": description,
                "state": "open",
                "open_issues": 0,
                "closed_issues": 0,
            }
            self._next_ms += 1
            self.milestones.append(ms)
            return self._ok(json.dumps(ms))

        # List milestones
        if "milestones" in path and "-f" not in args and "-X" not in args:
            return self._ok(json.dumps(self.milestones))

        # PATCH milestone (close)
        if "milestones" in path and "-X" in args:
            return self._ok("{}")

        # Compare endpoint: repos/{owner}/{repo}/compare/{base}...{branch}
        if "/compare/" in path:
            # Extract branch from path like repos/o/r/compare/main...feat-branch
            compare_part = path.split("/compare/")[-1]
            if "..." in compare_part:
                _base, branch = compare_part.split("...", 1)
                data = self.comparisons.get(
                    branch, {"behind_by": 0, "ahead_by": 0},
                )
                return self._ok(json.dumps(data))
            return self._fail(f"FakeGitHub: malformed compare path: {path}")

        # Commits endpoint: repos/{owner}/{repo}/commits
        if path.endswith("/commits"):
            # Filter by -f since= if provided
            since_val = None
            for fval in flags.get("f", []):
                if fval.startswith("since="):
                    since_val = fval[6:]
            data = self.commits_data
            if since_val:
                from datetime import datetime as _dt
                try:
                    since_dt = _dt.fromisoformat(since_val.replace("Z", "+00:00"))
                    data = [
                        c for c in data
                        if _dt.fromisoformat(
                            c.get("commit", {}).get("author", {}).get("date", "9999-12-31")
                            .replace("Z", "+00:00")
                        ) >= since_dt
                    ]
                except (ValueError, TypeError):
                    pass  # Unparseable date — return all
            return self._ok(json.dumps(data))

        # Timeline endpoint: repos/{owner}/{repo}/issues/{N}/timeline
        # Production code uses --jq to filter to first linked PR.
        # FakeGitHub returns the pre-filtered single object (what jq | first
        # would produce) so callers can json.loads() directly.
        if "/timeline" in path:
            import re as _re
            m = _re.search(r"/issues/(\d+)/timeline", path)
            if m:
                issue_num = int(m.group(1))
                events = self.timeline_events.get(issue_num)
                if events:
                    # Mimic --jq '[... | first]': find first event with
                    # source.issue.pull_request and return that issue object
                    for ev in events:
                        src = ev.get("source", {}).get("issue", {})
                        if src.get("pull_request"):
                            return self._ok(json.dumps(src))
                    # Events exist but none have pull_request
                    return self._ok("null")
                # No timeline events registered for this issue
                return self._fail(
                    f"FakeGitHub: no timeline events for issue {issue_num}"
                )

        # Fail loudly on unhandled API paths instead of silently returning []
        # so new API calls in production don't get free "green bar" (BH-008)
        return self._fail(f"FakeGitHub: unhandled API path: {path}")

    # -- Handler: issue -------------------------------------------------------

    def _handle_issue(self, args: list[str]) -> subprocess.CompletedProcess:
        if not args:
            return self._fail("no issue subcommand")
        sub = args[0]

        if sub == "create":
            return self._issue_create(args)
        elif sub == "list":
            return self._issue_list(args)
        elif sub == "edit":
            return self._issue_edit(args)
        elif sub == "close":
            return self._issue_close(args)
        return self._fail(f"issue {sub} not supported")

    def _issue_create(self, args: list[str]) -> subprocess.CompletedProcess:
        title = ""
        body = ""
        labels: list[str] = []
        milestone = ""
        i = 1
        while i < len(args):
            if args[i] == "--title" and i + 1 < len(args):
                title = args[i + 1]
                i += 2
            elif args[i] == "--body" and i + 1 < len(args):
                body = args[i + 1]
                i += 2
            elif args[i] == "--label" and i + 1 < len(args):
                labels.append(args[i + 1])
                i += 2
            elif args[i] == "--milestone" and i + 1 < len(args):
                milestone = args[i + 1]
                i += 2
            else:
                i += 1
        # Validate milestone exists (matches real GitHub API behavior)
        if milestone:
            ms_exists = any(ms["title"] == milestone for ms in self.milestones)
            if not ms_exists:
                return self._fail(
                    f"Validation Failed: milestone '{milestone}' not found"
                )

        issue = {
            "number": self._next_issue,
            "title": title,
            "body": body,
            "state": "open",
            "labels": [{"name": l} for l in labels],
            "milestone": {"title": milestone} if milestone else None,
            "closedAt": None,
        }
        self._next_issue += 1
        self.issues.append(issue)
        url = f"https://github.com/testowner/testrepo/issues/{issue['number']}"
        return self._ok(url)

    def _issue_list(self, args: list[str]) -> subprocess.CompletedProcess:
        flags = self._parse_flags(args, start=1)
        self._check_flags("issue_list", flags)
        state_filter = "open"
        milestone_filter = ""
        label_filter = ""
        json_fields: str | None = None
        limit: int | None = None
        i = 1
        while i < len(args):
            if args[i] == "--state" and i + 1 < len(args):
                state_filter = args[i + 1]
                i += 2
            elif args[i] == "--milestone" and i + 1 < len(args):
                milestone_filter = args[i + 1]
                i += 2
            elif args[i] == "--label" and i + 1 < len(args):
                label_filter = args[i + 1]
                i += 2
            elif args[i] == "--json" and i + 1 < len(args):
                json_fields = args[i + 1]
                i += 2
            elif args[i] == "--limit" and i + 1 < len(args):
                limit = int(args[i + 1])
                i += 2
            else:
                i += 1
        filtered = self.issues
        if state_filter != "all":
            filtered = [
                iss for iss in filtered
                if iss.get("state") == state_filter
            ]
        if milestone_filter:
            filtered = [
                iss for iss in filtered
                if (iss.get("milestone") or {}).get("title") == milestone_filter
            ]
        if label_filter:
            filtered = [
                iss for iss in filtered
                if any(l["name"] == label_filter for l in iss.get("labels", []))
            ]
        if limit is not None:
            filtered = filtered[:limit]
        filtered = self._filter_json_fields(filtered, json_fields)
        return self._ok(json.dumps(filtered))

    def _issue_edit(self, args: list[str]) -> subprocess.CompletedProcess:
        """Handle: gh issue edit <number> --add-label X --remove-label Y --milestone Z."""
        if len(args) < 2:
            return self._fail("issue edit requires issue number")
        try:
            issue_num = int(args[1])
        except ValueError:
            return self._fail(f"invalid issue number: {args[1]}")

        issue = self._find_issue(issue_num)
        if issue is None:
            return self._fail(f"issue {issue_num} not found")

        flags = self._parse_flags(args, start=2)
        self._check_flags("issue_edit", flags)

        for label_name in flags.get("add-label", []):
            existing = [l["name"] for l in issue["labels"]]
            if label_name not in existing:
                issue["labels"].append({"name": label_name})

        for label_name in flags.get("remove-label", []):
            issue["labels"] = [
                l for l in issue["labels"] if l["name"] != label_name
            ]

        if "milestone" in flags:
            ms_title = flags["milestone"][0]
            issue["milestone"] = {"title": ms_title} if ms_title else None

        return self._ok("")

    def _issue_close(self, args: list[str]) -> subprocess.CompletedProcess:
        """Handle: gh issue close <number>."""
        if len(args) < 2:
            return self._fail("issue close requires issue number")
        try:
            issue_num = int(args[1])
        except ValueError:
            return self._fail(f"invalid issue number: {args[1]}")

        issue = self._find_issue(issue_num)
        if issue is None:
            return self._fail(f"issue {issue_num} not found")

        issue["state"] = "closed"
        issue["closedAt"] = datetime.now(timezone.utc).isoformat()
        return self._ok("")

    def _find_issue(self, number: int) -> dict | None:
        for iss in self.issues:
            if iss["number"] == number:
                return iss
        return None

    # -- Handler: run ---------------------------------------------------------

    def _handle_run(self, args: list[str]) -> subprocess.CompletedProcess:
        if not args:
            return self._fail("no run subcommand")
        sub = args[0]
        if sub == "list":
            return self._run_list(args)
        elif sub == "view":
            return self._ok("no logs")
        return self._fail(f"run {sub} not supported")

    def _run_list(self, args: list[str]) -> subprocess.CompletedProcess:
        """Handle: gh run list [--branch <branch>] [--json ...] [--limit ...] [--status ...]."""
        flags = self._parse_flags(args, start=1)
        self._check_flags("run_list", flags)
        branch_filter = ""
        status_filter = ""
        json_fields: str | None = None
        limit: int | None = None
        i = 1
        while i < len(args):
            if args[i] == "--branch" and i + 1 < len(args):
                branch_filter = args[i + 1]
                i += 2
            elif args[i] == "--json" and i + 1 < len(args):
                json_fields = args[i + 1]
                i += 2
            elif args[i] == "--limit" and i + 1 < len(args):
                limit = int(args[i + 1])
                i += 2
            elif args[i] == "--status" and i + 1 < len(args):
                status_filter = args[i + 1]
                i += 2
            else:
                i += 1

        filtered = self.runs
        if branch_filter:
            filtered = [
                r for r in filtered
                if r.get("headBranch") == branch_filter
            ]
        if status_filter:
            filtered = [
                r for r in filtered
                if r.get("status") == status_filter
            ]
        if limit is not None:
            filtered = filtered[:limit]
        filtered = self._filter_json_fields(filtered, json_fields)
        return self._ok(json.dumps(filtered))

    # -- Handler: pr ----------------------------------------------------------

    def _handle_pr(self, args: list[str]) -> subprocess.CompletedProcess:
        if not args:
            return self._fail("no pr subcommand")
        sub = args[0]
        if sub == "list":
            return self._pr_list(args)
        elif sub == "create":
            return self._pr_create(args)
        elif sub == "review":
            return self._pr_review(args)
        elif sub == "merge":
            return self._pr_merge(args)
        return self._fail(f"pr {sub} not supported")

    def _pr_list(self, args: list[str]) -> subprocess.CompletedProcess:
        """Handle: gh pr list [--json ...] [--state ...] [--limit ...]."""
        flags = self._parse_flags(args, start=1)
        self._check_flags("pr_list", flags)
        json_fields: str | None = None
        state_filter = "open"
        limit: int | None = None
        i = 1
        while i < len(args):
            if args[i] == "--json" and i + 1 < len(args):
                json_fields = args[i + 1]
                i += 2
            elif args[i] == "--state" and i + 1 < len(args):
                state_filter = args[i + 1]
                i += 2
            elif args[i] == "--limit" and i + 1 < len(args):
                limit = int(args[i + 1])
                i += 2
            else:
                i += 1
        filtered = list(self.prs)
        if state_filter != "all":
            filtered = [
                pr for pr in filtered
                if pr.get("state") == state_filter
            ]
        if limit is not None:
            filtered = filtered[:limit]
        filtered = self._filter_json_fields(filtered, json_fields)
        return self._ok(json.dumps(filtered))

    def _pr_create(self, args: list[str]) -> subprocess.CompletedProcess:
        """Handle: gh pr create --title T --body B --base main --head feat --label L --milestone M."""
        flags = self._parse_flags(args, start=1)
        self._check_flags("pr_create", flags)

        title = flags.get("title", [""])[0]
        body = flags.get("body", [""])[0]
        base = flags.get("base", ["main"])[0]
        head = flags.get("head", [""])[0]
        labels = flags.get("label", [])
        milestone = flags.get("milestone", [""])[0]

        pr = {
            "number": self._next_pr,
            "title": title,
            "body": body,
            "state": "open",
            "baseRefName": base,
            "headRefName": head,
            "labels": [{"name": l} for l in labels],
            "milestone": {"title": milestone} if milestone else None,
            "merged": False,
            "mergedAt": None,
            "reviewDecision": "",
            "closedAt": None,
        }
        self._next_pr += 1
        self.prs.append(pr)
        url = f"https://github.com/testowner/testrepo/pull/{pr['number']}"
        return self._ok(url)

    def _pr_review(self, args: list[str]) -> subprocess.CompletedProcess:
        """Handle: gh pr review <number> --approve/--request-changes [--body B]."""
        if len(args) < 2:
            return self._fail("pr review requires PR number")
        try:
            pr_num = int(args[1])
        except ValueError:
            return self._fail(f"invalid PR number: {args[1]}")

        pr = self._find_pr(pr_num)
        if pr is None:
            return self._fail(f"PR {pr_num} not found")

        flags = self._parse_flags(args, start=2)
        self._check_flags("pr_review", flags)
        body = flags.get("body", [""])[0]

        if "approve" in flags:
            decision = "APPROVED"
        elif "request-changes" in flags:
            decision = "CHANGES_REQUESTED"
        else:
            decision = "COMMENTED"

        review = {
            "pr_number": pr_num,
            "state": decision,
            "body": body,
        }
        self.reviews.append(review)
        # Store review on the PR object itself for per-PR querying
        pr.setdefault("reviews", []).append(review)
        pr["reviewDecision"] = decision
        return self._ok("")

    def _pr_merge(self, args: list[str]) -> subprocess.CompletedProcess:
        """Handle: gh pr merge <number> [--squash|--merge|--rebase]."""
        if len(args) < 2:
            return self._fail("pr merge requires PR number")
        try:
            pr_num = int(args[1])
        except ValueError:
            return self._fail(f"invalid PR number: {args[1]}")

        pr = self._find_pr(pr_num)
        if pr is None:
            return self._fail(f"PR {pr_num} not found")

        now = datetime.now(timezone.utc).isoformat()
        pr["state"] = "closed"
        pr["merged"] = True
        pr["mergedAt"] = now
        pr["closedAt"] = now
        return self._ok("")

    def _find_pr(self, number: int) -> dict | None:
        for pr in self.prs:
            if pr["number"] == number:
                return pr
        return None

    # -- Handler: release -----------------------------------------------------

    def _handle_release(self, args: list[str]) -> subprocess.CompletedProcess:
        if not args:
            return self._fail("no release subcommand")
        sub = args[0]
        if sub == "create":
            return self._release_create(args)
        elif sub == "view":
            tag = args[1] if len(args) > 1 else ""
            return self._ok(json.dumps({
                "url": f"https://github.com/testowner/testrepo/releases/tag/{tag}"
            }))
        return self._fail(f"release {sub} not supported")

    def _release_create(self, args: list[str]) -> subprocess.CompletedProcess:
        """Handle: gh release create <tag> --title T --notes N [--target ...]."""
        # The tag can be a positional arg right after "create"
        tag = ""
        title = ""
        notes = ""

        # First positional arg after "create" is the tag
        i = 1
        if i < len(args) and not args[i].startswith("--"):
            tag = args[i]
            i += 1

        flags = self._parse_flags(args, start=i)
        self._check_flags("release_create", flags)
        if "tag" in flags:
            tag = flags["tag"][0]
        title = flags.get("title", [tag])[0]
        notes = flags.get("notes", [""])[0]

        release = {
            "tag_name": tag,
            "name": title,
            "body": notes,
        }
        self.releases.append(release)
        return self._ok(
            f"https://github.com/testowner/testrepo/releases/tag/{tag}"
        )

    # -- State dump -----------------------------------------------------------

    def dump_state(self) -> dict:
        """Return a dict with all state for test assertions."""
        return {
            "labels": dict(self.labels),
            "milestones": list(self.milestones),
            "issues": list(self.issues),
            "prs": list(self.prs),
            "reviews": list(self.reviews),
            "releases": list(self.releases),
            "runs": list(self.runs),
            "comparisons": dict(self.comparisons),
            "commits_data": list(self.commits_data),
        }


def make_patched_subprocess(fake_gh: FakeGitHub, verbose: bool = False):
    """Create a subprocess.run replacement that intercepts gh calls.

    When verbose=True, prints each intercepted gh command as it would
    appear on the command line, so test output shows the real API calls.
    """
    import shlex
    _real_run = subprocess.run

    def patched_run(args, *a, **kw):
        if isinstance(args, list) and args and args[0] == "gh":
            if verbose:
                print(f"  $ {shlex.join(args)}")
            return fake_gh.handle(args[1:])
        return _real_run(args, *a, **kw)

    return patched_run
