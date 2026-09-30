"""Statically inventory a third-party agent extension without executing, installing, or extracting it.

Accepts a directory, a single file, or a zip/tar archive. Walks without following
links, reads bounded text, classifies files and manifests, and reports rule-family
findings with coverage. Emits JSON evidence; never prints matched secret values.
Exit codes: 0 no Blocker or Important finding and complete coverage; 1 Blocker
or Important findings; 2 usage error or incomplete coverage.
"""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE.parent / "references", _HERE.parents[2] / "references"):
    if (_candidate / "cw_scan.py").is_file():
        sys.path.insert(0, str(_candidate))
        break
import cw_scan  # noqa: E402


TOOL = "skill-supply-audit/scan_extension"
FAMILIES = (
    "fetch-and-execute",
    "external-endpoint",
    "credential-access",
    "persistence",
    "permission-escalation",
    "hook-execution",
    "mcp-launch",
    "package-lifecycle",
    "obfuscation",
    "prompt-authority",
    "routing-hijack",
    "secret-material",
    "binary-content",
    "link-escape",
)
CONTENT_FAMILIES = frozenset(FAMILIES) - {"binary-content", "link-escape"}
EXECUTABLE_SUFFIXES = frozenset(
    {".sh", ".bash", ".zsh", ".fish", ".ps1", ".psm1", ".bat", ".cmd", ".py", ".js", ".mjs", ".cjs", ".ts",
     ".rb", ".pl", ".php", ".lua"}
)
CONFIG_SUFFIXES = frozenset({".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf"})
INSTRUCTION_NAMES = frozenset({"skill.md", "agents.md", "claude.md", "gemini.md"})
INSTRUCTION_DIRECTORIES = frozenset({"agents", "commands", "references", "prompts", "rules"})
TAR_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")
MEDIA_KINDS = frozenset({"png-image", "gif-image", "jpeg-image", "pdf-document"})
DOWNGRADE = {"Blocker": "Important", "Important": "Minor", "Minor": "Minor"}


Rule = tuple[str, re.Pattern[str], str | None]


def _rules(*entries: tuple[str, ...]) -> tuple[Rule, ...]:
    """Compile (name, pattern[, severity]) entries; a missing severity uses the family default."""

    return tuple(
        (entry[0], re.compile(entry[1], re.IGNORECASE), entry[2] if len(entry) > 2 else None) for entry in entries
    )


# Rules that only make sense in code, not in prose that may legitimately mention them.
EXECUTABLE_ONLY_RULES = frozenset({"dynamic-evaluation", "environment-dump"})

LINE_RULES: dict[str, tuple[str, tuple[Rule, ...]]] = {
    "fetch-and-execute": ("Blocker", _rules(
        ("download-piped-to-shell", r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z|da|k)?sh\b"),
        ("download-piped-to-powershell", r"\b(?:iwr|irm|invoke-webrequest|invoke-restmethod)\b[^\n|]*\|\s*(?:iex|invoke-expression)\b"),
        ("shell-process-substitution-download", r"\b(?:ba)?sh\s+<\(\s*(?:curl|wget)"),
        ("powershell-invoke-expression", r"\binvoke-expression\b|\biex\s*\("),
        ("python-exec-remote", r"\bexec\s*\(\s*(?:urllib|requests|urlopen)"),
        ("pip-install-from-url", r"\bpip3?\s+install\s+(?:git\+|https?://)"),
    )),
    "credential-access": ("Important", _rules(
        ("ssh-key-path", r"(?:~|\$home|%userprofile%)?[/]\.ssh/(?:id_|authorized_keys|config)|\bid_(?:rsa|ed25519|ecdsa)\b"),
        ("cloud-credential-path", r"\.aws/credentials|\.config/gcloud|\.azure/|\.kube/config|\.docker/config\.json"),
        ("netrc-or-npmrc", r"\.netrc\b|\.npmrc\b|\.pypirc\b"),
        ("named-secret-variable", r"\b(?:GITHUB_TOKEN|GH_TOKEN|ANTHROPIC_API_KEY|OPENAI_API_KEY|AWS_SECRET_ACCESS_KEY|NPM_TOKEN|GOOGLE_APPLICATION_CREDENTIALS)\b", "Minor"),
        ("keychain-access", r"\bsecurity\s+find-(?:generic|internet)-password\b|\bsecret-tool\s+lookup\b|\bcmdkey\s+/list\b"),
        ("browser-profile-data", r"(?:login data|cookies\.sqlite|/cookies\b).{0,80}(?:chrome|chromium|firefox|edge)|(?:chrome|firefox).{0,80}(?:login data|cookies)"),
        ("environment-dump", r"\b(?:printenv|env)\s*(?:\||>)|os\.environ\.(?:items|copy)\(|process\.env\)|json\.dumps\(\s*(?:dict\()?os\.environ"),
    )),
    "persistence": ("Important", _rules(
        ("shell-profile-write", r"(?:>>|>|tee\s+-a)\s*[\"']?(?:~|\$home)?/?\.(?:bashrc|zshrc|profile|bash_profile|zprofile|config/fish)"),
        ("scheduled-task", r"\bcrontab\b|\bschtasks\b|\blaunchctl\s+(?:load|bootstrap)\b|launchagents|launchdaemons"),
        ("service-install", r"\bsystemctl\s+(?:--user\s+)?enable\b|\.config/systemd/"),
        ("registry-autorun", r"\breg(?:\.exe)?\s+add\b.{0,120}currentversion.run"),
        ("git-hook-install", r"\.git/hooks/|core\.hookspath|git\s+config\s+--global"),
        ("agent-config-write", r"\.claude/settings(?:\.local)?\.json|\.codex/config\.toml|\.cursor/mcp\.json|\.gemini/settings\.json"),
        ("path-modification", r"\bsetx\s+path\b|export\s+path=|\$env:path\s*="),
    )),
    "permission-escalation": ("Important", _rules(
        ("bypass-permissions-mode", r"bypasspermissions|dangerously-?skip-?permissions|--dangerously|--yolo"),
        ("full-access-sandbox", r"danger-full-access|sandbox_mode\s*=\s*[\"']danger"),
        ("never-ask-approval", r"approval_policy\s*=\s*[\"']never|\"autoapprove\"|alwaysallow|\"trust\"\s*:\s*true"),
        ("wildcard-shell-permission", r"bash\(\s*\*\s*\)|\"allow\"\s*:\s*\[[^\]]*\"bash\b"),
    )),
    "obfuscation": ("Important", _rules(
        ("decode-and-execute", r"(?:base64\s+(?:-d|--decode)|b64decode|atob\s*\(|frombase64string).{0,80}(?:\|\s*(?:ba)?sh|exec|eval|iex|invoke-expression)"),
        ("execute-decoded", r"\b(?:exec|eval)\s*\(\s*(?:base64\.)?(?:b64decode|decodebytes|atob)\s*\("),
        ("dynamic-evaluation", r"\beval\s*\(|\bnew\s+function\s*\(", "Minor"),
    )),
    "prompt-authority": ("Important", _rules(
        ("override-instructions", r"\b(?:ignore|disregard|forget)\b.{0,30}\b(?:previous|prior|above|earlier|system|user)\b.{0,20}\b(?:instructions?|messages?|rules?|prompts?)"),
        ("conceal-from-user", r"\b(?:do not|don't|never)\s+(?:tell|inform|show|mention|alert|notify)\b.{0,20}\buser\b"),
        ("act-without-consent", r"\bwithout\s+(?:asking|confirmation|confirming|approval|telling\s+the\s+user|the\s+user'?s?\s+(?:knowledge|permission|consent))"),
        ("silent-action", r"\b(?:silently|quietly|secretly)\s+(?:run|install|execute|send|upload|download|delete|modify|write|post|copy)"),
        ("self-granted-authority", r"\byou\s+(?:are|have\s+been)\s+(?:now\s+)?(?:authori[sz]ed|permitted|allowed|granted)\b"),
        ("instruction-precedence-claim", r"\b(?:these|this|following)\s+instructions?\s+(?:override|supersede|take\s+precedence)"),
        ("impersonated-system-message", r"^\s*(?:\[|<)?\s*(?:system|developer)\s*(?:prompt|message)?\s*(?:\]|>|:)"),
        ("remote-instruction-fetch", r"\b(?:fetch|download|read|load)\b.{0,60}\b(?:and|then)\s+(?:follow|obey|execute|run)\b"),
        ("disable-safety", r"\b(?:disable|turn\s+off|bypass|skip)\s+(?:the\s+)?(?:safety|sandbox|permission|approval|confirmation)s?\b"),
    )),
}
URL_PATTERN = re.compile(r"\bhttps?://[^\s'\"<>)\]`]+", re.IGNORECASE)
SUSPICIOUS_HOSTS = (
    "pastebin.com", "paste.ee", "hastebin", "gist.githubusercontent.com", "raw.githubusercontent.com",
    "ngrok", "webhook.site", "requestbin", "pipedream.net", "discord.com/api/webhooks", "discordapp.com/api/webhooks",
    "api.telegram.org", "transfer.sh", "bit.ly", "tinyurl.com", "t.co", "is.gd", "0x0.st", "trycloudflare.com",
)
IP_HOST = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
BASE64_RUN = re.compile(r"[A-Za-z0-9+/]{160,}={0,2}")
HEX_ESCAPE_RUN = re.compile("(?:" + re.escape(chr(92)) + "x[0-9a-fA-F]{2}){12,}")
HTML_COMMENT = re.compile(r"<!--(.*?)-->", re.DOTALL)
FENCE = re.compile(r"^\s*(```|~~~)")
LIFECYCLE_SCRIPTS = ("preinstall", "install", "postinstall", "prepare", "prepublish", "preuninstall", "postuninstall")
HOOK_EVENTS = re.compile(
    r"\b(?:PreToolUse|PostToolUse|UserPromptSubmit|SessionStart|SessionEnd|Stop|SubagentStop|PreCompact|Notification|BeforeTool|AfterTool)\b"
)
GIT_HOOK_NAMES = frozenset({"pre-commit", "post-checkout", "post-merge", "pre-push", "commit-msg", "post-commit", "prepare-commit-msg"})
OVERBROAD_DESCRIPTION = re.compile(
    r"\b(?:always\s+use|use\s+(?:this|it)\s+for\s+(?:all|every|any)|for\s+(?:all|every|any)\s+(?:tasks?|requests?|questions?)|before\s+any\s+other\s+skill)\b",
    re.IGNORECASE,
)
FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class Member:
    relative: str
    kind: str
    size: int
    mode: int = 0
    link_target: str | None = None
    data: bytes | None = None
    truncated: bool = False


class Scanner:
    def __init__(self, limits: cw_scan.Limits, installed_names: set[str]):
        self.limits = limits
        self.installed_names = installed_names
        self.findings: list[dict[str, object]] = []
        self.inventory: list[dict[str, object]] = []
        self.endpoints: dict[str, set[str]] = {}
        self.unread: list[str] = []
        self.limits_reached: list[str] = []
        self.total_read = 0

    def add(self, rule: str, family: str, severity: str, path: str, line: int | None, context: str, detail: str) -> None:
        self.findings.append(cw_scan.finding(rule, family, severity, path, line, context, detail))

    # -- classification -------------------------------------------------
    @staticmethod
    def role(relative: str, head: bytes, mode: int) -> str:
        path = PurePosixPath(relative)
        name = path.name.casefold()
        suffix = path.suffix.casefold()
        if suffix in EXECUTABLE_SUFFIXES or head.startswith(b"#!") or mode & 0o111:
            return "executable-file"
        if name in {"hooks.json", "package.json", "mcp.json", ".mcp.json", "settings.json", "settings.local.json"} or suffix in CONFIG_SUFFIXES:
            return "config"
        if suffix in {".md", ".mdx", ".txt", ".rst", ""}:
            parents = {part.casefold() for part in path.parts[:-1]}
            if name in INSTRUCTION_NAMES or parents & INSTRUCTION_DIRECTORIES:
                return "agent-instruction"
            return "documentation"
        return "data"

    # -- member scanning ------------------------------------------------
    def scan_member(self, member: Member) -> None:
        record: dict[str, object] = {"path": member.relative, "kind": member.kind, "size": member.size}
        self.inventory.append(record)
        if member.kind in {"symlink", "hardlink"}:
            target = member.link_target or ""
            absolute, escapes = cw_scan.link_escapes(member.relative, target)
            record["link_target"] = cw_scan.excerpt(target, 200)
            if absolute or escapes:
                self.add("escaping-link", "link-escape", "Blocker", member.relative, None, "filesystem",
                         f"{member.kind} points outside the extension root: {target}")
            else:
                self.add("internal-link", "link-escape", "Minor", member.relative, None, "filesystem",
                         f"{member.kind} inside the extension root was not followed")
            return
        if member.kind == "reparse-point":
            self.add("reparse-point", "link-escape", "Blocker", member.relative, None, "filesystem",
                     "Windows reparse point was not followed")
            return
        if member.kind in {"device", "fifo", "other"}:
            self.add("special-file", "link-escape", "Important", member.relative, None, "filesystem",
                     f"special file type {member.kind}")
            return
        if member.kind != "file":
            return
        if member.data is None:
            self.unread.append(member.relative)
            record["read"] = False
            return
        data = member.data
        record["sha256"] = cw_scan.sha256_bytes(data) if not member.truncated else None
        record["truncated"] = member.truncated
        if member.truncated:
            self.unread.append(member.relative)
            self.limits_reached.append(f"max-file-bytes {self.limits.max_file_bytes} truncated {member.relative}")
        kind = cw_scan.binary_kind(data)
        role = self.role(member.relative, data[:4], member.mode)
        record["role"] = role
        record["executable_bit"] = bool(member.mode & 0o111)
        if kind is not None:
            record["binary"] = kind
            if kind not in MEDIA_KINDS:
                self.unread.append(member.relative)
            if kind in cw_scan.EXECUTABLE_BINARY_KINDS:
                self.add("native-executable", "binary-content", "Blocker", member.relative, None, role,
                         f"{kind} cannot be reviewed statically")
            elif kind.endswith("archive"):
                self.add("nested-archive", "binary-content", "Important", member.relative, None, role,
                         f"{kind} contents were not inspected")
            else:
                self.add("opaque-binary", "binary-content", "Minor", member.relative, None, role,
                         f"{kind} was not inspected")
            return
        text = data.decode("utf-8", errors="replace")
        self.scan_text(member.relative, text, role)

    def scan_text(self, relative: str, text: str, role: str) -> None:
        name = PurePosixPath(relative).name.casefold()
        for rule, line in cw_scan.secret_hits(text):
            self.add(rule, "secret-material", "Important", relative, line, role, f"{rule} signature matched (value withheld)")
        for line in cw_scan.invisible_characters(text):
            self.add("invisible-characters", "obfuscation", "Important", relative, line, role,
                     "bidirectional or zero-width characters change how this line renders")
        in_fence = False
        for number, line in cw_scan.iter_lines(text):
            if role in {"documentation", "agent-instruction"} and FENCE.match(line):
                in_fence = not in_fence
            context = role
            if role == "documentation" and in_fence:
                context = "documentation-example"
            self.scan_line(relative, number, line, context)
        if role in {"documentation", "agent-instruction"}:
            for comment in HTML_COMMENT.finditer(text):
                body = comment.group(1)
                line_number = text.count("\n", 0, comment.start()) + 1
                for rule, pattern, _ in LINE_RULES["prompt-authority"][1]:
                    if pattern.search(body):
                        self.add(f"hidden-{rule}", "prompt-authority", "Blocker", relative, line_number, "html-comment",
                                 body)
        if name == "skill.md":
            self.scan_skill_frontmatter(relative, text)
        if name == "package.json":
            self.scan_package_json(relative, text)
        if name in {"mcp.json", ".mcp.json"} or '"mcpServers"' in text or re.search(r"^\s*\[mcp_servers\.", text, re.MULTILINE):
            self.scan_mcp(relative, text)
        if name == "hooks.json" or (role == "config" and HOOK_EVENTS.search(text) and '"command"' in text):
            self.add("agent-hook-definition", "hook-execution", "Important", relative, None, role,
                     "defines agent lifecycle hooks that run commands automatically")
        parts = [part.casefold() for part in PurePosixPath(relative).parts]
        if name in GIT_HOOK_NAMES and "hooks" in parts:
            self.add("git-hook-script", "hook-execution", "Important", relative, None, role, "git hook script")
        if name in {"setup.py", "setup.cfg"}:
            self.add("python-install-code", "package-lifecycle", "Minor", relative, None, role,
                     "Python packaging code can run at install time")

    def scan_line(self, relative: str, number: int, line: str, context: str) -> None:
        for family, (base, rules) in LINE_RULES.items():
            if family == "prompt-authority" and context not in {"agent-instruction", "documentation", "data"}:
                continue
            for rule, pattern, rule_severity in rules:
                if rule in EXECUTABLE_ONLY_RULES and context != "executable-file":
                    continue
                if pattern.search(line):
                    self.add(rule, family, self.severity(rule_severity or base, family, context), relative, number,
                             context, line)
        for match in URL_PATTERN.finditer(line):
            url = cw_scan.strip_url_credentials(match.group(0).rstrip(".,;:"))
            host = (url.split("://", 1)[1].split("/", 1)[0]).casefold()
            self.endpoints.setdefault(host, set()).add(relative)
            lowered = url.casefold()
            if any(marker in lowered for marker in SUSPICIOUS_HOSTS) or IP_HOST.match(host.split(":")[0]):
                self.add("suspicious-endpoint", "external-endpoint",
                         self.severity("Important", "external-endpoint", context), relative, number, context, url)
        if BASE64_RUN.search(line) and context not in {"documentation", "documentation-example"}:
            self.add("long-encoded-blob", "obfuscation", "Minor", relative, number, context, "long base64-like run")
        if HEX_ESCAPE_RUN.search(line):
            self.add("hex-escape-run", "obfuscation", self.severity("Important", "obfuscation", context),
                     relative, number, context, "long run of hex escapes")

    @staticmethod
    def severity(base: str, family: str, context: str) -> str:
        if context == "documentation-example":
            return "Minor"
        if context == "documentation":
            return DOWNGRADE[base]
        if family == "prompt-authority" and context in {"executable-file", "config", "data"}:
            return "Minor"
        return base

    def scan_skill_frontmatter(self, relative: str, text: str) -> None:
        match = FRONTMATTER.match(text)
        if not match:
            return
        header = match.group(1)
        fields: dict[str, str] = {}
        current = None
        for line in header.splitlines():
            if line and not line[0].isspace() and ":" in line:
                current, value = line.split(":", 1)
                current = current.strip().casefold()
                fields[current] = value.strip()
            elif current:
                fields[current] = f"{fields[current]} {line.strip()}"
        description = fields.get("description", "")
        if len(description) > 1024:
            self.add("oversized-description", "routing-hijack", "Important", relative, 1, "agent-instruction",
                     f"description is {len(description)} characters")
        if OVERBROAD_DESCRIPTION.search(description):
            self.add("overbroad-trigger", "routing-hijack", "Important", relative, 1, "agent-instruction", description)
        name = fields.get("name", "").strip("\"' ")
        if name and name in self.installed_names:
            self.add("shadows-installed-skill", "routing-hijack", "Important", relative, 1, "agent-instruction",
                     f"skill name {name} matches an installed skill")
        tools = fields.get("allowed-tools", "")
        if re.search(r"\bbash\b|\*", tools, re.IGNORECASE):
            self.add("broad-allowed-tools", "permission-escalation", "Important", relative, 1, "agent-instruction",
                     f"allowed-tools: {tools}")

    def scan_package_json(self, relative: str, text: str) -> None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            self.add("unparseable-package-json", "package-lifecycle", "Minor", relative, None, "config",
                     "package.json could not be parsed")
            return
        scripts = data.get("scripts") if isinstance(data, dict) else None
        if not isinstance(scripts, dict):
            return
        for key in LIFECYCLE_SCRIPTS:
            if isinstance(scripts.get(key), str):
                self.add(f"npm-{key}-script", "package-lifecycle", "Important", relative, None, "config",
                         f"{key}: {scripts[key]}")

    def scan_mcp(self, relative: str, text: str) -> None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            self.add("mcp-definition", "mcp-launch", "Important", relative, None, "config",
                     "MCP server definition present (not JSON; review manually)")
            return
        servers = data.get("mcpServers") if isinstance(data, dict) else None
        if not isinstance(servers, dict):
            return
        for server, spec in servers.items():
            if not isinstance(spec, dict):
                continue
            command = str(spec.get("command", ""))
            args = [str(item) for item in spec.get("args", []) if isinstance(item, (str, int))]
            joined = " ".join([command, *args])
            detail = f"server {server}: {joined or spec.get('url', '')}"
            severity = "Important"
            if re.search(r"\b(?:npx|bunx|uvx|pipx)\b", joined) and not re.search(r"@\d", joined):
                detail += " (unpinned package launcher)"
            env_keys = sorted(str(key) for key in (spec.get("env") or {}) if isinstance(spec.get("env"), dict))
            if env_keys:
                detail += f"; requests environment: {', '.join(env_keys)}"
            self.add("mcp-server-launch", "mcp-launch", severity, relative, None, "config", detail)
            url = spec.get("url")
            if isinstance(url, str):
                host = cw_scan.strip_url_credentials(url).split("://", 1)[-1].split("/", 1)[0].casefold()
                self.endpoints.setdefault(host, set()).add(relative)

    # -- inputs ----------------------------------------------------------
    def read_budget(self, size: int) -> bool:
        if self.total_read + min(size, self.limits.max_file_bytes) > self.limits.max_total_bytes:
            if not any(item.startswith("max-total-bytes") for item in self.limits_reached):
                self.limits_reached.append(f"max-total-bytes {self.limits.max_total_bytes} reached")
            return False
        return True

    def scan_directory(self, root: Path) -> None:
        result = cw_scan.walk(root, self.limits)
        self.limits_reached.extend(result.limits_reached)
        self.unread.extend(result.errors)
        for entry in result.entries:
            if entry.kind == "dir":
                continue
            member = Member(entry.relative, entry.kind, entry.size, entry.mode, entry.link_target)
            if entry.kind == "file" and self.read_budget(entry.size):
                try:
                    member.data, member.truncated = cw_scan.read_bounded(entry.path, self.limits.max_file_bytes)
                    self.total_read += len(member.data)
                except OSError as exc:
                    self.unread.append(f"{entry.relative}: {exc.strerror or exc}")
            self.scan_member(member)

    def archive_name_escapes(self, name: str) -> bool:
        normalized = name.replace(chr(92), "/")
        return normalized.startswith("/") or bool(re.match(r"^[A-Za-z]:", normalized)) or ".." in normalized.split("/")

    def scan_zip(self, path: Path) -> None:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > self.limits.max_files:
                self.limits_reached.append(f"max-files {self.limits.max_files} reached")
                infos = infos[: self.limits.max_files]
            for info in infos:
                name = info.filename
                if self.archive_name_escapes(name):
                    self.add("archive-path-escape", "link-escape", "Blocker", name, None, "archive",
                             "archive member would be written outside the extraction root")
                if info.is_dir():
                    continue
                unix_mode = info.external_attr >> 16
                if stat.S_ISLNK(unix_mode):
                    with archive.open(info) as stream:
                        target = stream.read(4096).decode("utf-8", errors="replace")
                    self.scan_member(Member(name, "symlink", info.file_size, unix_mode, target))
                    continue
                if info.flag_bits & 0x1:
                    self.unread.append(f"{name}: encrypted")
                    self.add("encrypted-member", "binary-content", "Important", name, None, "archive",
                             "encrypted archive member cannot be inspected")
                    continue
                if info.compress_size and info.file_size > info.compress_size * 100:
                    self.add("compression-ratio", "binary-content", "Important", name, None, "archive",
                             "compression ratio above 100:1")
                member = Member(name, "file", info.file_size, unix_mode)
                if self.read_budget(info.file_size):
                    with archive.open(info) as stream:
                        data = stream.read(self.limits.max_file_bytes + 1)
                    member.data, member.truncated = data[: self.limits.max_file_bytes], len(data) > self.limits.max_file_bytes
                    self.total_read += len(member.data)
                self.scan_member(member)

    def scan_tar(self, path: Path) -> None:
        with tarfile.open(path, mode="r:*") as archive:
            count = 0
            for info in archive:
                count += 1
                if count > self.limits.max_files:
                    self.limits_reached.append(f"max-files {self.limits.max_files} reached")
                    break
                name = info.name
                if self.archive_name_escapes(name):
                    self.add("archive-path-escape", "link-escape", "Blocker", name, None, "archive",
                             "archive member would be written outside the extraction root")
                if info.isdir():
                    continue
                if info.issym() or info.islnk():
                    kind = "symlink" if info.issym() else "hardlink"
                    self.scan_member(Member(name, kind, 0, info.mode, info.linkname))
                    continue
                if info.ischr() or info.isblk():
                    self.scan_member(Member(name, "device", 0, info.mode))
                    continue
                if info.isfifo():
                    self.scan_member(Member(name, "fifo", 0, info.mode))
                    continue
                member = Member(name, "file", info.size, info.mode)
                if info.isfile() and self.read_budget(info.size):
                    stream = archive.extractfile(info)
                    if stream is not None:
                        data = stream.read(self.limits.max_file_bytes + 1)
                        member.data, member.truncated = data[: self.limits.max_file_bytes], len(data) > self.limits.max_file_bytes
                        self.total_read += len(member.data)
                self.scan_member(member)

    # -- report ------------------------------------------------------------
    def coverage(self) -> dict[str, dict[str, str]]:
        flagged = {str(item["family"]) for item in self.findings}
        incomplete = bool(self.unread) or bool(self.limits_reached)
        result: dict[str, dict[str, str]] = {}
        for family in FAMILIES:
            if family in flagged:
                result[family] = cw_scan.coverage("flagged")
            elif family in CONTENT_FAMILIES and incomplete:
                reason = "; ".join(sorted(set(self.limits_reached))[:3]) or f"{len(self.unread)} file(s) not read as text"
                result[family] = cw_scan.coverage("not checked", reason)
            else:
                result[family] = cw_scan.coverage("clear")
        return result

    def report(self, target: str) -> dict[str, object]:
        counts = {severity: sum(1 for item in self.findings if item["severity"] == severity) for severity in cw_scan.SEVERITIES}
        return cw_scan.envelope(
            TOOL,
            {"target": target, "limits": vars(self.limits), "installed_names": sorted(self.installed_names)},
            summary={"files": sum(1 for item in self.inventory if item["kind"] == "file"), "findings": counts,
                     "unread": len(self.unread), "limits_reached": sorted(set(self.limits_reached))},
            coverage=self.coverage(),
            findings=sorted(self.findings, key=lambda item: (cw_scan.SEVERITIES.index(str(item["severity"])),
                                                             str(item["path"]), item["line"] or 0)),
            endpoints={host: sorted(paths) for host, paths in sorted(self.endpoints.items())},
            inventory=sorted(self.inventory, key=lambda item: str(item["path"])),
            unread=sorted(set(self.unread)),
            executed=False,
        )


def main(argv: list[str] | None = None) -> int:
    cw_scan.require_python()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", help="extension directory, file, or zip/tar archive")
    parser.add_argument("--max-depth", type=int, default=cw_scan.Limits.max_depth)
    parser.add_argument("--max-files", type=int, default=cw_scan.Limits.max_files)
    parser.add_argument("--max-file-bytes", type=int, default=cw_scan.Limits.max_file_bytes)
    parser.add_argument("--max-total-bytes", type=int, default=cw_scan.Limits.max_total_bytes)
    parser.add_argument("--installed-name", action="append", default=[],
                        help="an installed skill name to check for shadowing; repeatable")
    parser.add_argument("--output", help="write JSON here instead of stdout")
    args = parser.parse_args(argv)
    target = Path(args.path)
    limits = cw_scan.Limits(args.max_depth, args.max_files, args.max_file_bytes, args.max_total_bytes)
    scanner = Scanner(limits, set(args.installed_name))
    lowered = target.name.casefold()
    try:
        if target.is_symlink():
            print("error: the audit target itself is a symlink; pass the real path", file=sys.stderr)
            return 2
        if target.is_dir():
            scanner.scan_directory(target)
        elif target.is_file() and zipfile.is_zipfile(target):
            scanner.scan_zip(target)
        elif target.is_file() and lowered.endswith(TAR_SUFFIXES):
            scanner.scan_tar(target)
        elif target.is_file():
            data, truncated = cw_scan.read_bounded(target, limits.max_file_bytes)
            scanner.scan_member(Member(target.name, "file", target.stat().st_size, target.stat().st_mode, None, data, truncated))
        else:
            print(f"error: not found: {target}", file=sys.stderr)
            return 2
    except (OSError, zipfile.BadZipFile, tarfile.TarError) as exc:
        print(f"error: could not read the audit target: {exc}", file=sys.stderr)
        return 2
    report = scanner.report(target.name)
    cw_scan.emit(report, args.output)
    blocking = any(item["severity"] in {"Blocker", "Important"} for item in scanner.findings)
    incomplete = bool(scanner.unread) or bool(scanner.limits_reached)
    if blocking:
        return 1
    return 2 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
