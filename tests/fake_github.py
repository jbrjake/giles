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
    def _parse_flags(args: list[str], start: int = 1) -> dict[str, list[str]]:
        """Parse --flag value pairs into a dict.

        Flags that appear multiple times get multiple values in the list.
        Bare flags (no value) get ["true"].
        """
        flags: dict[str, list[str]] = {}
        i = start
        while i < len(args):
            a = args[i]
            if a.startswith("--"):
                key = a.lstrip("-")
                # Check if next arg is a value (not another flag) or end
                if i + 1 < len(args) and not args[i + 1].startswith("--"):
                    flags.setdefault(key, []).append(args[i + 1])
                    i += 2
                else:
                    flags.setdefault(key, []).append("true")
                    i += 1
            else:
                i += 1
        return flags

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

        return self._ok("[]")

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
        state_filter = "open"
        milestone_filter = ""
        i = 1
        while i < len(args):
            if args[i] == "--state" and i + 1 < len(args):
                state_filter = args[i + 1]
                i += 2
            elif args[i] == "--milestone" and i + 1 < len(args):
                milestone_filter = args[i + 1]
                i += 2
            elif args[i] == "--json" and i + 1 < len(args):
                i += 2
            elif args[i] == "--limit" and i + 1 < len(args):
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
        """Handle: gh run list [--branch <branch>] [--json ...]."""
        branch_filter = ""
        i = 1
        while i < len(args):
            if args[i] == "--branch" and i + 1 < len(args):
                branch_filter = args[i + 1]
                i += 2
            elif args[i] in ("--json", "--limit", "--status") and i + 1 < len(args):
                i += 2
            else:
                i += 1

        filtered = self.runs
        if branch_filter:
            filtered = [
                r for r in filtered
                if r.get("headBranch") == branch_filter
            ]
        return self._ok(json.dumps(filtered))

    # -- Handler: pr ----------------------------------------------------------

    def _handle_pr(self, args: list[str]) -> subprocess.CompletedProcess:
        if not args:
            return self._fail("no pr subcommand")
        sub = args[0]
        if sub == "list":
            return self._ok(json.dumps(self.prs))
        elif sub == "create":
            return self._pr_create(args)
        elif sub == "review":
            return self._pr_review(args)
        elif sub == "merge":
            return self._pr_merge(args)
        return self._fail(f"pr {sub} not supported")

    def _pr_create(self, args: list[str]) -> subprocess.CompletedProcess:
        """Handle: gh pr create --title T --body B --base main --head feat --label L --milestone M."""
        flags = self._parse_flags(args, start=1)

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
