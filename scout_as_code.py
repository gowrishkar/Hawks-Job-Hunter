#!/usr/bin/env python3
"""
Hawks Scout-as-Code (SaC) pipeline.

Purpose:
- Use a programmable search/retrieval/filter/rank pipeline instead of prompt-only scouting.
- Source from Gowrishkar's quality allowlist.
- Validate final role pages where possible.
- Emit compact JSON for Hermes cron context; the LLM only summarizes validated candidates.

No third-party dependencies. Uses stdlib + requests if available, urllib fallback.
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import dataclasses
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None

ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "state" / "scout_as_code"
STATE_DIR.mkdir(parents=True, exist_ok=True)
SEEN_PATH = STATE_DIR / "seen_jobs.json"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36 HawksScout/1.0"
)

ALLOWLIST = [
    "wellfound.com",
    "linkedin.com/jobs",
    "aijobs.ai",
    "aijobs.net",
    "naukri.com",
    "hirist.tech",
    "ycombinator.com/jobs",
    "builtin.com",
    "theproductfolks.com/jobs",
    "otta.com",
    "remoteok.com",
    "startup.jobs",
    "levels.fyi/jobs",
]

DISCOVERY_SITE_QUERIES = {
    "wellfound.com": "site:wellfound.com/jobs (AI Product Manager OR GenAI Product Manager OR AI Solutions Consultant OR AI Operations) remote India",
    "linkedin.com/jobs": "site:linkedin.com/jobs (AI Product Manager OR GenAI Product Manager OR AI Solutions Consultant OR AI Program Manager) India remote",
    "aijobs.ai": "site:aijobs.ai (AI Product Manager OR AI Solutions OR GenAI Product OR AI Program Manager)",
    "aijobs.net": "site:aijobs.net (AI Product Manager OR AI Solutions Consultant OR AI Program Manager OR GenAI)",
    "naukri.com": "site:naukri.com (GenAI Product Manager OR AI Product Manager OR AI Solutions Architect OR AI Program Manager) India",
    "hirist.tech": "site:hirist.tech (AI Product Manager OR GenAI Product Manager OR AI Solutions Architect OR AI Program Manager)",
    "ycombinator.com/jobs": "site:ycombinator.com/jobs (AI Product Manager OR AI Solutions OR Operations Lead AI OR Chief of Staff AI) remote",
    "builtin.com": "site:builtin.com/jobs (AI Product Manager OR GenAI Product Manager OR AI Solutions Consultant) remote",
    "theproductfolks.com/jobs": "site:theproductfolks.com/jobs (AI Product Manager OR GenAI Product Manager OR Product Operations AI)",
    "otta.com": "site:otta.com/jobs (AI Product Manager OR GenAI Product Manager OR AI Solutions Consultant) remote",
    "remoteok.com": "site:remoteok.com (AI Product Manager OR AI Solutions Consultant OR AI Program Manager)",
    "startup.jobs": "site:startup.jobs (AI Product Manager OR GenAI Product Manager OR AI Solutions Consultant OR AI Operations)",
    "levels.fyi/jobs": "site:levels.fyi/jobs (AI Product Manager OR AI Program Manager OR Solutions Engineer AI) remote",
}

ROLE_QUERIES = [
    '"AI Product Manager" remote India',
    '"GenAI Product Manager" India remote',
    '"LLM Product Manager" remote',
    '"AI Product Operations" remote India',
    '"AI Solutions Consultant" India remote',
    '"AI Solutions Architect" India remote',
    '"AI Implementation Consultant" GenAI remote',
    '"AI Transformation Consultant" India',
    '"AI Strategy Operations" AI remote',
    '"AI Program Manager" India remote',
    '"Technical Program Manager" AI India remote',
    '"Customer Engineer" AI India',
    '"Solutions Engineer" AI remote India',
    '"Founder\'s Office" AI startup India',
]

POSITIVE_PATTERNS = {
    "ai_core": r"\b(ai|artificial intelligence|genai|generative ai|llm|large language model|agentic|agents?|automation|machine learning)\b",
    "ownership": r"\b(product|solution design|solutions?|implementation|deployment|adoption|transformation|workflow|program|operations?|scale|customer engineer|consultant)\b",
    "bridge": r"\b(stakeholder|business|technical|gtm|go[- ]?to[- ]?market|partnership|enablement|customer discovery|pre[- ]?sales|strategy)\b",
    "builder_operator": r"\b(startup|builder|operator|ambiguity|hands[- ]?on|consulting|cross[- ]functional|0 to 1)\b",
    "location": r"\b(india|remote|global|worldwide|asia|apac|emea|hybrid|bangalore|bengaluru|chennai|hyderabad|pune|mumbai|delhi|gurgaon|gurugram)\b",
}

HARD_REJECT_PATTERNS = {
    "pure_sales": r"\b(sdr|bdr|account executive|enterprise account executive|account director|sales director|quota|cold call|closing deals|sales development)\b",
    "deep_engineering": r"\b(ml engineer|machine learning engineer|data scientist|research scientist|backend engineer|frontend engineer|full stack engineer|devops|mlops|platform engineer|security engineer|phd|required.*python.*production|kubernetes.*terraform)\b",
    "junior": r"\b(intern|internship|fresher|campus|graduate trainee|entry level|0[-–]?[ ]?2 years|0[-–]?[ ]?3 years|associate product manager)\b",
    "local_only": r"\b(us only|u\.s\. only|security clearance|must be located in the united states|work authorization.*united states|eu only|uk only|onsite only)\b",
    "non_full_time_or_low_fit": r"\b(freelance|contract only|temporary|estimator|bookkeeper|assistant|virtual assistant)\b",
    "scam": r"\b(whatsapp only|telegram only|registration fee|training fee|pay.*equipment|purchase.*equipment|commission only|unpaid|equity only)\b",
}

TARGET_ROLE_REGEX = re.compile(
    r"\b("
    r"ai product|genai product|llm product|product manager|product operations|"
    r"solutions? consultant|solutions? architect|implementation consultant|deployment lead|"
    r"transformation consultant|strategy.*operations|operations lead|adoption lead|"
    r"program manager|technical program manager|customer engineer|solutions? engineer|"
    r"founder.?s office|chief of staff|ai partnerships|workflow automation"
    r")\b",
    re.I,
)

ATS_HINTS = [
    "greenhouse.io", "lever.co", "ashbyhq.com", "myworkdayjobs.com", "workdayjobs.com",
    "smartrecruiters.com", "workable.com", "teamtailor.com", "bamboohr.com", "recruitee.com",
    "rippling.com", "personio.com", "icims.com", "jobs.ashbyhq.com", "boards.greenhouse.io",
]


def fetch(url: str, timeout: int = 15) -> Tuple[int, str, str]:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    try:
        if requests:
            r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            return r.status_code, r.url, r.text[:1_000_000]
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec - controlled by scout allowlist/search
            body = resp.read(1_000_000).decode("utf-8", "ignore")
            return resp.status, resp.geturl(), body
    except Exception as e:
        return 0, url, f"FETCH_ERROR: {type(e).__name__}: {e}"


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: List[Tuple[str, str]] = []
        self._href: Optional[str] = None
        self._buf: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            d = dict(attrs)
            self._href = d.get("href")
            self._buf = []

    def handle_data(self, data):
        if self._href is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href:
            text = " ".join("".join(self._buf).split())
            self.links.append((self._href, text))
            self._href = None
            self._buf = []


def clean_text(s: str) -> str:
    s = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(re.sub(r"\s+", " ", s)).strip()


def title_of(html_text: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.I | re.S)
    return clean_text(m.group(1))[:180] if m else ""


def search_duckduckgo(query: str, max_results: int) -> List[Dict[str, str]]:
    url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    status, final, body = fetch(url, timeout=20)
    if status != 200:
        return []
    parser = LinkExtractor()
    parser.feed(body)
    out = []
    for href, text in parser.links:
        if not href:
            continue
        real = href
        if "uddg=" in href:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            if qs.get("uddg"):
                real = qs["uddg"][0]
        if real.startswith("//"):
            real = "https:" + real
        if not real.startswith("http"):
            continue
        if any(domain in real for domain in ["duckduckgo.com", "bing.com/yhp"]):
            continue
        if not is_allowed_discovery(real) and not is_official_ats(real):
            continue
        out.append({"url": real, "title": text[:200], "query": query, "search_status": str(status)})
        if len(out) >= max_results:
            break
    return out


def is_allowed_discovery(url: str) -> bool:
    u = url.lower()
    return any(host in u for host in ALLOWLIST)


def is_official_ats(url: str) -> bool:
    u = url.lower()
    return any(h in u for h in ATS_HINTS)


def canonical_url(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    # keep query only for ATS job ids on known domains where query can identify role
    query = p.query if any(h in p.netloc.lower() for h in ["workday", "smartrecruiters", "linkedin"]) else ""
    return urllib.parse.urlunsplit((p.scheme, p.netloc.lower().replace("www.", ""), p.path.rstrip("/"), query, ""))


def source_name(url: str) -> str:
    u = url.lower()
    for host in ALLOWLIST:
        if host in u:
            return host
    for host in ATS_HINTS:
        if host in u:
            return host
    return urllib.parse.urlparse(url).netloc.lower().replace("www.", "")


def extract_jsonld_jobs(body: str) -> List[dict]:
    jobs = []
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', body, flags=re.I | re.S):
        raw = html.unescape(m.group(1)).strip()
        try:
            data = json.loads(raw)
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                typ = x.get("@type") or x.get("type")
                if typ == "JobPosting" or (isinstance(typ, list) and "JobPosting" in typ):
                    jobs.append(x)
                for v in x.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(x, list):
                stack.extend(x)
    return jobs


def extract_apply_links(base_url: str, body: str) -> List[str]:
    parser = LinkExtractor()
    try:
        parser.feed(body)
    except Exception:
        pass
    links = []
    for href, text in parser.links:
        low = f"{href} {text}".lower()
        if any(k in low for k in ["apply", "application", "job", "greenhouse", "lever", "ashby", "workday", "smartrecruiters"]):
            links.append(urllib.parse.urljoin(base_url, href))
    # also regex visible ATS URLs
    for m in re.finditer(r'https?://[^\s"\'<>]+', body):
        u = html.unescape(m.group(0)).rstrip(').,;')
        if is_official_ats(u):
            links.append(u)
    dedup = []
    seen = set()
    for u in links:
        cu = canonical_url(u)
        if cu not in seen:
            seen.add(cu); dedup.append(u)
    return dedup[:10]


def extract_field_from_jsonld(job: dict, key: str) -> str:
    v = job.get(key)
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)[:500]
    if isinstance(v, list):
        return "; ".join(extract_field_from_jsonld(x, "name") if isinstance(x, dict) else str(x) for x in v)[:500]
    return ""


@dataclasses.dataclass
class Candidate:
    url: str
    discovery_source: str
    search_query: str = ""
    title: str = ""
    company: str = "unknown"
    role: str = "unknown"
    location: str = "unknown"
    description: str = ""
    date_posted: str = "unknown"
    valid_through: str = "unknown"
    compensation: str = "unknown"
    direct_apply_url: str = ""
    http_status: int = 0
    open_role: bool = False
    apply_found: bool = False
    location_eligible: bool = False
    positive_signals: List[str] = dataclasses.field(default_factory=list)
    reject_reasons: List[str] = dataclasses.field(default_factory=list)
    risk_gap: str = ""
    fit_score: float = 0.0
    action: str = "Monitor"
    validation_note: str = ""
    fingerprint: str = ""


def hydrate(raw: Dict[str, str]) -> Candidate:
    c = Candidate(url=raw["url"], discovery_source=source_name(raw["url"]), search_query=raw.get("query", ""), title=raw.get("title", ""))
    status, final, body = fetch(c.url)
    c.http_status = status
    c.url = final
    if status < 200 or status >= 400:
        c.reject_reasons.append(f"http_{status or 'fetch_failed'}")
        c.validation_note = "URL did not load cleanly."
        return c

    page_title = title_of(body)
    text = clean_text(body)
    lowered = text.lower()
    c.title = page_title or c.title

    jsonld_jobs = extract_jsonld_jobs(body)
    if jsonld_jobs:
        j = jsonld_jobs[0]
        c.role = extract_field_from_jsonld(j, "title") or c.role
        org = j.get("hiringOrganization") or {}
        if isinstance(org, dict):
            c.company = org.get("name") or c.company
        c.description = clean_text(extract_field_from_jsonld(j, "description"))[:4000] or text[:4000]
        c.date_posted = extract_field_from_jsonld(j, "datePosted") or c.date_posted
        c.valid_through = extract_field_from_jsonld(j, "validThrough") or c.valid_through
        c.location = extract_field_from_jsonld(j, "jobLocation") or extract_field_from_jsonld(j, "applicantLocationRequirements") or c.location
        c.compensation = extract_field_from_jsonld(j, "baseSalary") or c.compensation
        c.direct_apply_url = extract_field_from_jsonld(j, "url") or c.url
    else:
        c.description = text[:4000]
        # heuristic role/company from title
        t = page_title or raw.get("title", "")
        parts = re.split(r"\s+[-|@–—]\s+", t)
        c.role = parts[0][:120] if parts else t[:120]
        if len(parts) > 1:
            c.company = parts[-1][:100]
        # dates
        dm = re.search(r"(posted|updated|date posted)\s*[:\-]?\s*((?:\d{1,2}\s+)?[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d+\s+days?\s+ago)", text, re.I)
        if dm:
            c.date_posted = dm.group(2)

    apply_links = extract_apply_links(c.url, body)
    if not c.direct_apply_url:
        official = [u for u in apply_links if is_official_ats(u)]
        c.direct_apply_url = (official or apply_links or [c.url])[0]
    c.apply_found = bool(apply_links) or bool(re.search(r"\b(apply now|apply for this job|submit application|easy apply)\b", lowered))
    c.open_role = not bool(re.search(r"\b(no longer accepting|job is closed|position has been filled|expired|archived|not found|no longer available)\b", lowered))
    c.location_eligible = bool(re.search(POSITIVE_PATTERNS["location"], lowered))

    joined = " ".join([c.role, c.title, c.company, c.location, c.description]).lower()
    for name, pat in POSITIVE_PATTERNS.items():
        if re.search(pat, joined, re.I):
            c.positive_signals.append(name)
    for name, pat in HARD_REJECT_PATTERNS.items():
        if re.search(pat, joined, re.I):
            c.reject_reasons.append(name)

    title_role_text = " ".join([c.role, c.title]).lower()
    if not TARGET_ROLE_REGEX.search(title_role_text):
        # Prevent AI-company/generic-remote false positives. Description-only matches are not enough.
        c.reject_reasons.append("wrong_role_title")

    if not c.open_role:
        c.reject_reasons.append("closed_or_expired")
    if not c.apply_found:
        c.reject_reasons.append("no_apply_path")
    if not c.location_eligible:
        c.reject_reasons.append("location_unclear")
    if len(c.positive_signals) < 2:
        c.reject_reasons.append("weak_positive_signal")

    c.fit_score = score_candidate(c)
    # caps
    if "ai_core" not in c.positive_signals:
        c.fit_score = min(c.fit_score, 4.0)
    if any(r in c.reject_reasons for r in ["pure_sales", "deep_engineering", "non_full_time_or_low_fit", "wrong_role_title"]):
        c.fit_score = min(c.fit_score, 5.0)
    if "location_unclear" in c.reject_reasons:
        c.fit_score = min(c.fit_score, 6.0)
    if c.fit_score >= 8.7 and c.apply_found:
        c.action = "Apply now"
    elif c.fit_score >= 8.0:
        c.action = "Customize CV first"
    elif c.fit_score >= 7.0:
        c.action = "Monitor"
    else:
        c.action = "Reject"

    c.risk_gap = risk_gap(c)
    c.fingerprint = make_fingerprint(c)
    c.validation_note = make_validation_note(c)
    return c


def score_candidate(c: Candidate) -> float:
    signals = set(c.positive_signals)
    role_alignment = 3.0 if any(k in (c.role + " " + c.title).lower() for k in ["product manager", "solutions", "implementation", "transformation", "program manager", "customer engineer", "founder", "chief of staff", "operations"]) else 1.8
    ai = 2.0 if "ai_core" in signals else 0.8
    seniority = 1.2
    if re.search(r"\b(senior|lead|principal|manager|head|director)\b", (c.role + " " + c.description).lower()):
        seniority = 1.5
    if any(r in c.reject_reasons for r in ["junior"]):
        seniority = 0.3
    location = 1.5 if c.location_eligible else 0.5
    comp = 0.8
    if c.compensation != "unknown" or re.search(r"\b(senior|lead|principal|manager|director|head)\b", (c.role + " " + c.description).lower()):
        comp = 1.0
    actionability = 0.5 if c.apply_found else 0.1
    upside = 0.5 if any(k in c.description.lower() for k in ["startup", "ai platform", "agent", "llm", "enterprise ai", "automation"]) else 0.3
    score = role_alignment + ai + seniority + location + comp + actionability + upside
    # bonus for bridge/ownership
    if "ownership" in signals:
        score += 0.4
    if "bridge" in signals:
        score += 0.3
    if "builder_operator" in signals:
        score += 0.2
    # penalties
    score -= 0.7 * len([r for r in c.reject_reasons if r not in {"location_unclear"}])
    return round(max(0.0, min(10.0, score)), 1)


def risk_gap(c: Candidate) -> str:
    if c.reject_reasons:
        return ", ".join(sorted(set(c.reject_reasons)))
    gaps = []
    if c.compensation == "unknown":
        gaps.append("compensation unknown")
    if c.date_posted == "unknown":
        gaps.append("freshness weak/unknown")
    if not is_official_ats(c.direct_apply_url) and not is_allowed_discovery(c.direct_apply_url):
        gaps.append("apply domain needs manual check")
    return "; ".join(gaps) or "low visible risk"


def make_validation_note(c: Candidate) -> str:
    bits = [f"HTTP {c.http_status}"]
    bits.append("open-role text check passed" if c.open_role else "open-role check failed")
    bits.append("apply path found" if c.apply_found else "apply path missing")
    bits.append("location eligible/likely" if c.location_eligible else "location unclear")
    if is_official_ats(c.direct_apply_url):
        bits.append("official ATS/apply detected")
    elif is_allowed_discovery(c.direct_apply_url):
        bits.append("allowlist platform apply path")
    return "; ".join(bits)


def make_fingerprint(c: Candidate) -> str:
    key = "|".join([c.company.lower(), c.role.lower(), c.location.lower(), canonical_url(c.direct_apply_url or c.url)])
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def load_seen() -> Dict[str, dict]:
    try:
        return json.loads(SEEN_PATH.read_text())
    except Exception:
        return {}


def save_seen(seen: Dict[str, dict]) -> None:
    tmp = SEEN_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(seen, indent=2, sort_keys=True))
    tmp.replace(SEEN_PATH)


def discover_source_pages(max_leads: int) -> List[Dict[str, str]]:
    """Direct programmable retrieval from allowlisted sources.

    This avoids relying only on generic search. It is intentionally conservative:
    collect candidate URLs from source APIs/pages, then hydrate/validate later.
    """
    leads: List[Dict[str, str]] = []
    seen = set()

    def add(url: str, title: str, query: str) -> None:
        if not url.startswith("http"):
            return
        if not (is_allowed_discovery(url) or is_official_ats(url)):
            return
        cu = canonical_url(url)
        if cu in seen:
            return
        seen.add(cu)
        leads.append({"url": url, "title": title[:200], "query": query, "search_status": "direct"})

    # RemoteOK has a stable public API, but it is noisy; cap it so it cannot crowd out better sources.
    remoteok_cap = max(2, min(8, max_leads // 4))
    remoteok_added = 0
    status, final, body = fetch("https://remoteok.com/api", timeout=20)
    if status == 200:
        try:
            data = json.loads(body)
            for item in data[1:] if isinstance(data, list) else []:
                if not isinstance(item, dict):
                    continue
                text = " ".join(str(item.get(k, "")) for k in ["position", "company", "description", "tags", "location"]).lower()
                if re.search(POSITIVE_PATTERNS["ai_core"], text, re.I) and any(k in text for k in ["product", "solutions", "consultant", "program", "operations", "customer"]):
                    before = len(leads)
                    add(item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id')}", f"{item.get('company','')} - {item.get('position','')}", "remoteok_api")
                    if len(leads) > before:
                        remoteok_added += 1
                    if remoteok_added >= remoteok_cap:
                        break
        except Exception:
            pass

    # Allowlisted pages with visible links or embedded data.
    seed_pages = [
        "https://aijobs.ai/jobs",
        "https://aijobs.net/",
        "https://www.ycombinator.com/jobs",
        "https://www.hirist.tech/search/ai-product-manager-jobs",
        "https://www.hirist.tech/search/genai-jobs",
        "https://www.theproductfolks.com/jobs",
        "https://builtin.com/jobs/remote/artificial-intelligence",
        "https://www.levels.fyi/jobs",
    ]
    for page in seed_pages:
        if len(leads) >= max_leads:
            break
        status, final, body = fetch(page, timeout=20)
        if status < 200 or status >= 400:
            continue
        parser = LinkExtractor()
        try:
            parser.feed(body)
        except Exception:
            continue
        page_text = clean_text(body).lower()
        for href, text in parser.links:
            low = f"{href} {text}".lower()
            if not any(k in low for k in ["job", "career", "opening", "position", "apply"]):
                continue
            if not re.search(r"\b(ai|genai|llm|product|solutions|consultant|program|operations|customer engineer|founder)\b", low, re.I):
                # Some modern apps have thin link text; allow if page itself is targeted and link looks like job path.
                if not ("job" in low and re.search(POSITIVE_PATTERNS["ai_core"], page_text, re.I)):
                    continue
            add(urllib.parse.urljoin(final, href), text or title_of(body), f"direct_seed:{page}")
            if len(leads) >= max_leads:
                return leads
    return leads


def discover(max_leads: int, per_query: int) -> List[Dict[str, str]]:
    direct = discover_source_pages(max_leads=max_leads)
    out: List[Dict[str, str]] = []
    seen = set()
    for item in direct:
        cu = canonical_url(item["url"])
        if cu not in seen:
            seen.add(cu); out.append(item)
            if len(out) >= max_leads:
                return out

    queries = []
    # Site-specific quality source queries first.
    queries.extend(DISCOVERY_SITE_QUERIES.values())
    # Cross site queries across allowlist.
    for rq in ROLE_QUERIES[:8]:
        sites = " OR ".join(f"site:{s}" for s in ["wellfound.com/jobs", "ycombinator.com/jobs", "aijobs.ai", "aijobs.net", "startup.jobs"])
        queries.append(f"({sites}) {rq}")
    with futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(search_duckduckgo, q, per_query) for q in queries]
        for fut in futures.as_completed(futs):
            for item in fut.result():
                cu = canonical_url(item["url"])
                if cu not in seen:
                    seen.add(cu); out.append(item)
                    if len(out) >= max_leads:
                        return out
    return out


def run(max_output: int, max_leads: int, per_query: int, include_seen: bool) -> dict:
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    leads = discover(max_leads=max_leads, per_query=per_query)
    candidates: List[Candidate] = []
    with futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(hydrate, lead) for lead in leads]
        for fut in futures.as_completed(futs):
            candidates.append(fut.result())

    # Deduplicate by canonical fingerprint.
    by_fp: Dict[str, Candidate] = {}
    for c in candidates:
        fp = c.fingerprint or make_fingerprint(c)
        existing = by_fp.get(fp)
        if existing is None or (is_official_ats(c.direct_apply_url) and not is_official_ats(existing.direct_apply_url)) or c.fit_score > existing.fit_score:
            by_fp[fp] = c
    candidates = list(by_fp.values())

    seen = load_seen()
    rejected_counts: Dict[str, int] = {}
    shortlisted: List[Candidate] = []
    for c in candidates:
        if not include_seen and c.fingerprint in seen:
            c.reject_reasons.append("already_seen")
        final_reject = bool(c.reject_reasons) or c.fit_score < 8.0
        if final_reject:
            reasons = c.reject_reasons or ["below_score_threshold"]
            for r in sorted(set(reasons)):
                rejected_counts[r] = rejected_counts.get(r, 0) + 1
            continue
        shortlisted.append(c)

    shortlisted.sort(key=lambda x: (x.fit_score, x.date_posted != "unknown", is_official_ats(x.direct_apply_url)), reverse=True)
    shortlisted = shortlisted[:max_output]

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    for c in shortlisted:
        seen[c.fingerprint] = {"seen_at": now, "company": c.company, "role": c.role, "url": c.direct_apply_url or c.url, "fit_score": c.fit_score}
    save_seen(seen)

    source_mix: Dict[str, int] = {}
    rejected_job_count = 0
    for c in candidates:
        source_mix[source_name(c.url)] = source_mix.get(source_name(c.url), 0) + 1
        if c not in shortlisted:
            rejected_job_count += 1

    return {
        "schema": "hawks.scout_as_code.v1",
        "started_at_utc": started,
        "finished_at_utc": now,
        "approved_sources": ALLOWLIST,
        "reviewed_count": len(candidates),
        "raw_leads_count": len(leads),
        "validated_shortlist_count": len(shortlisted),
        "rejected_suppressed_count": rejected_job_count,
        "rejected_suppressed_by_reason": dict(sorted(rejected_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "source_mix_used": dict(sorted(source_mix.items())),
        "jobs": [dataclasses.asdict(c) for c in shortlisted],
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Hawks Scout-as-Code quality job scout")
    ap.add_argument("--session", choices=["morning", "evening", "manual"], default="manual")
    ap.add_argument("--max-output", type=int, default=10)
    ap.add_argument("--max-leads", type=int, default=50)
    ap.add_argument("--per-query", type=int, default=4)
    ap.add_argument("--include-seen", action="store_true", help="Allow jobs already shown in prior reports")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args(argv)
    result = run(args.max_output, args.max_leads, args.per_query, args.include_seen)
    result["session"] = args.session
    print(json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
