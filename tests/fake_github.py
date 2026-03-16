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
import warnings
from datetime import datetime, timezone


class FakeGitHub:
    """Simulate GitHub API responses for gh CLI calls."""

    def __init__(self, strict: bool = True):
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
        self.strict = strict
        self._strict_warnings: list[str] = []    # collected warnings
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

    # Cache jq availability check
    _jq_available: bool | None = None

    @classmethod
    def _check_jq(cls) -> bool:
        """Check if the jq Python package is available (dev dependency).

        The jq package is required for full-fidelity testing of --jq filters.
        Without it, FakeGitHub falls back to pre-filtered data, which means
        tests pass but don't actually verify jq expressions (P13-005).
        """
        if cls._jq_available is None:
            try:
                import jq as _jq  # noqa: F401
                cls._jq_available = True
            except ImportError:
                cls._jq_available = False
                warnings.warn(
                    "jq Python package not installed. FakeGitHub jq filters "
                    "will use pre-filtered fallbacks. Install with: "
                    "pip install jq  (P13-005)",
                    stacklevel=2,
                )
        return cls._jq_available

    def _maybe_apply_jq(self, json_str: str, flags: dict[str, list[str]]) -> str:
        """Apply --jq filter to JSON output if the jq package is available.

        Matches ``gh --jq`` behavior: applies the jq expression to the
        JSON data and returns the result.  If the result is a plain string,
        returns it unquoted (matching gh CLI output).  Otherwise returns JSON.

        Falls back to returning unfiltered data if jq is not installed.
        """
        jq_exprs = flags.get("jq", [])
        if not jq_exprs:
            return json_str
        if not self._check_jq():
            return json_str  # graceful fallback

        import jq as _jq
        jq_expr = jq_exprs[0]
        data = json.loads(json_str)
        result = _jq.first(jq_expr, data)

        if result is None:
            return "null"
        if isinstance(result, str):
            return result  # raw string (matches gh --jq behavior)
        return json.dumps(result)

    @staticmethod
    def _extract_search_milestone(search: str) -> str | None:
        """Extract milestone title from a --search string like 'milestone:"Sprint 1"'.

        Returns the milestone title if found, or None.  Only handles the
        ``milestone:`` predicate (sprint_analytics.compute_review_rounds).
        Warns if other predicates are present so test authors know their
        search filters aren't being exercised (P13-019).
        """
        if not search:
            return None
        import re as _re
        # Extract and remove milestone predicate
        m = _re.search(r'milestone:"([^"]+)"', search)
        milestone = m.group(1) if m else None
        if not milestone:
            m = _re.search(r"milestone:(\S+)", search)
            milestone = m.group(1) if m else None
        # Check for other predicates beyond milestone
        remaining = _re.sub(r'milestone:"[^"]+"', '', search)
        remaining = _re.sub(r'milestone:\S+', '', remaining).strip()
        if remaining:
            warnings.warn(
                f"FakeGitHub: search predicate(s) beyond milestone are "
                f"silently ignored: '{remaining}'. Only milestone: is "
                f"evaluated. (P13-019)",
                stacklevel=3,
            )
        return milestone

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
        "issue_list": frozenset(("state", "milestone", "json", "limit", "label", "search")),
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
        # filter correctness. Each handler documents its assumed jq shape inline.
        # Endpoints that rely on jq filtering:
        #   - /issues/{N}/timeline: '[... | select(.source.issue.pull_request)
        #     | .source.issue] | first' → returns first linked PR object
        #   - /commits: '.[].sha', '.[].commit.message' → returns full objects
        #   - release view: '.url' → returns {url: ...} object
        # If jq fidelity becomes critical, implement pyjq or basic expression eval.
        "api": frozenset(("paginate", "f", "X", "jq")),
    }

    # Flags that each handler actually evaluates to filter or shape results.
    # Subset of _KNOWN_FLAGS.  Flags in _KNOWN_FLAGS but NOT here are accepted
    # without error but do NOT affect handler behavior.
    # In strict mode (default), passing such a flag triggers a warning so test
    # authors know their query filter isn't actually being exercised.
    _IMPLEMENTED_FLAGS: dict[str, frozenset[str]] = {
        "issue_create": frozenset(("title", "body", "label", "milestone")),
        # search: only milestone:"X" pattern is evaluated; other predicates are silently ignored
        "issue_list": frozenset(("state", "milestone", "json", "limit", "label", "search")),
        "issue_edit": frozenset(("add-label", "remove-label", "milestone")),
        "issue_close": frozenset(),
        "run_list": frozenset(("branch", "json", "limit", "status")),
        "pr_list": frozenset(("json", "state", "limit", "search")),
        "pr_create": frozenset(("title", "body", "base", "head", "label", "milestone")),
        "pr_review": frozenset(("body", "approve", "request-changes")),
        "pr_merge": frozenset(("squash", "merge", "rebase")),
        "release_create": frozenset(("tag", "title", "notes")),  # target: accepted, not used
        "release_view": frozenset(("json", "jq")),  # jq evaluated when package available
        "label_create": frozenset(("color", "description", "force")),
        "api": frozenset(("f", "X", "jq")),  # jq evaluated when package available
    }

    # Flags that always consume the next argument as their value,
    # even if it starts with a dash (e.g., --title "-1 Fix bug").
    _VALUE_BEARING_FLAGS = frozenset((
        "title", "body", "milestone", "jq", "json", "label", "state",
        "limit", "branch", "base", "head", "notes", "notes-file",
        "tag", "target", "color", "description", "add-label",
        "remove-label", "status", "search",
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

    def _check_flags(self, handler_name: str, flags: dict[str, list[str]]) -> None:
        """Raise NotImplementedError for unknown flags; warn for unimplemented ones.

        Unknown flags (not in _KNOWN_FLAGS or _ACCEPTED_NOOP_FLAGS) always raise.
        In strict mode, flags that are known but not in _IMPLEMENTED_FLAGS emit
        a warning so test authors know their filter isn't being exercised.
        """
        known = self._KNOWN_FLAGS.get(handler_name, frozenset())
        allowed = known | self._ACCEPTED_NOOP_FLAGS
        implemented = self._IMPLEMENTED_FLAGS.get(handler_name, frozenset())
        for flag in flags:
            if flag not in allowed:
                raise NotImplementedError(
                    f"FakeGitHub handler '{handler_name}' does not handle "
                    f"flag '--{flag}'. Add it to _KNOWN_FLAGS['{handler_name}'] "
                    f"or _ACCEPTED_NOOP_FLAGS if it's intentionally ignored."
                )
            if self.strict and flag in known and flag not in implemented:
                if flag not in self._ACCEPTED_NOOP_FLAGS:
                    msg = (
                        f"FakeGitHub strict mode: handler '{handler_name}' "
                        f"accepts '--{flag}' but does NOT use it to filter "
                        f"results. Your test is not exercising this filter. "
                        f"Either implement the flag in FakeGitHub and add it "
                        f"to _IMPLEMENTED_FLAGS, or use FakeGitHub(strict=False)."
                    )
                    self._strict_warnings.append(msg)
                    warnings.warn(msg, stacklevel=3)

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
        # PATCH milestone (update state) — check before CREATE since both have -f
        if "milestones" in path and "-X" in args:
            import re as _re
            # Extract milestone number from path
            ms_match = _re.search(r"/milestones/(\d+)", path)
            if ms_match:
                ms_num = int(ms_match.group(1))
                for ms in self.milestones:
                    if ms.get("number") == ms_num:
                        # Apply field updates from -f flags
                        for fval in flags.get("f", []):
                            if "=" in fval:
                                key, val = fval.split("=", 1)
                                ms[key] = val
                        if ms.get("state") == "closed" and not ms.get("closed_at"):
                            ms["closed_at"] = "2026-01-01T00:00:00Z"
                        return self._ok(json.dumps(ms))
            return self._ok("{}")

        # Create milestone (POST with -f title=...)
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
                # BH-011: Include created_at for check_status milestone-date path
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            self._next_ms += 1
            self.milestones.append(ms)
            return self._ok(json.dumps(ms))

        # List milestones
        if "milestones" in path:
            json_str = json.dumps(self.milestones)
            return self._ok(self._maybe_apply_jq(json_str, flags))

        # Compare endpoint: repos/{owner}/{repo}/compare/{base}...{branch}
        if "/compare/" in path:
            # Extract branch from path like repos/o/r/compare/main...feat-branch
            compare_part = path.split("/compare/")[-1]
            if "..." in compare_part:
                _base, branch = compare_part.split("...", 1)
                data = self.comparisons.get(
                    branch, {"behind_by": 0, "ahead_by": 0},
                )
                json_str = json.dumps(data)
                return self._ok(self._maybe_apply_jq(json_str, flags))
            return self._fail(f"FakeGitHub: malformed compare path: {path}")

        # Commits endpoint: repos/{owner}/{repo}/commits
        # --jq filter shape assumed (from release_gate.py parse_commits_since):
        #   --jq '.[].sha' or --jq '.[].commit.message'
        # FakeGitHub returns the full commit objects; callers extract fields.
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
            json_str = json.dumps(data)
            return self._ok(self._maybe_apply_jq(json_str, flags))

        # Timeline endpoint: repos/{owner}/{repo}/issues/{N}/timeline
        # Production jq filter (sync_tracking.py):
        #   '[.[] | select(.source?.issue?.pull_request?) | .source.issue]'
        # With jq package: returns all events, jq filters to matching PRs.
        # Without jq: falls back to manual pre-filtering.
        if "/timeline" in path:
            import re as _re
            m = _re.search(r"/issues/(\d+)/timeline", path)
            if m:
                issue_num = int(m.group(1))
                events = self.timeline_events.get(issue_num)
                if not events:
                    return self._fail(
                        f"FakeGitHub: no timeline events for issue {issue_num}"
                    )
                jq_exprs = flags.get("jq", [])
                if jq_exprs and self._check_jq():
                    # Full fidelity: return all events, let jq filter
                    json_str = json.dumps(events)
                    return self._ok(self._maybe_apply_jq(json_str, flags))
                # Fallback: pre-filter (when jq package unavailable)
                for ev in events:
                    src = ev.get("source", {}).get("issue", {})
                    if src.get("pull_request"):
                        return self._ok(json.dumps(src))
                return self._ok("null")

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
        # BH-002: Update milestone open_issues counter
        if milestone:
            for ms in self.milestones:
                if ms["title"] == milestone:
                    ms["open_issues"] = ms.get("open_issues", 0) + 1
                    break
        url = f"https://github.com/testowner/testrepo/issues/{issue['number']}"
        return self._ok(url)

    def _issue_list(self, args: list[str]) -> subprocess.CompletedProcess:
        flags = self._parse_flags(args, start=1)
        self._check_flags("issue_list", flags)
        state_filter = "open"
        milestone_filter = ""
        label_filter = ""
        search_filter = ""
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
            elif args[i] == "--search" and i + 1 < len(args):
                search_filter = args[i + 1]
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
        # --search milestone:"X" support (same as _pr_list)
        ms_from_search = self._extract_search_milestone(search_filter)
        if ms_from_search:
            filtered = [
                iss for iss in filtered
                if (iss.get("milestone") or {}).get("title") == ms_from_search
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
        # BH-002: Update milestone counters
        ms_title = (issue.get("milestone") or {}).get("title")
        if ms_title:
            for ms in self.milestones:
                if ms["title"] == ms_title:
                    ms["open_issues"] = max(0, ms.get("open_issues", 0) - 1)
                    ms["closed_issues"] = ms.get("closed_issues", 0) + 1
                    break
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
        """Handle: gh pr list [--json ...] [--state ...] [--limit ...] [--search ...]."""
        flags = self._parse_flags(args, start=1)
        self._check_flags("pr_list", flags)
        json_fields: str | None = None
        state_filter = "open"
        search_filter = ""
        limit: int | None = None
        i = 1
        while i < len(args):
            if args[i] == "--json" and i + 1 < len(args):
                json_fields = args[i + 1]
                i += 2
            elif args[i] == "--state" and i + 1 < len(args):
                state_filter = args[i + 1]
                i += 2
            elif args[i] == "--search" and i + 1 < len(args):
                search_filter = args[i + 1]
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
        # Basic --search support: filter by milestone title when the search
        # string contains milestone:"X".  This handles the sprint_analytics
        # use case (compute_review_rounds) without needing full search parsing.
        ms_title = self._extract_search_milestone(search_filter)
        if ms_title:
            filtered = [
                pr for pr in filtered
                if (pr.get("milestone") or {}).get("title") == ms_title
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
            # --jq filter shape assumed (from release_gate.py do_release):
            #   --jq '.url' — FakeGitHub returns the full {url: ...} object.
            # Extract tag (first positional arg after "view")
            tag = ""
            i = 1
            if i < len(args) and not args[i].startswith("-"):
                tag = args[i]
                i += 1
            flags = self._parse_flags(args, start=i)
            self._check_flags("release_view", flags)
            json_str = json.dumps({
                "url": f"https://github.com/testowner/testrepo/releases/tag/{tag}"
            })
            return self._ok(self._maybe_apply_jq(json_str, flags))
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
