import http.client
import json
import re
from urllib.parse import quote

from .config import LI_AT, JSESSIONID

VOYAGER_HOST = "www.linkedin.com"

# Single decoration that returns profile + positions + education + skills +
# languages + courses in one request.
DECORATION_ID = (
    "com.linkedin.voyager.dash.deco.identity.profile"
    ".FullProfileWithEntities-93"
)


class LinkedInClient:
    """Fetches LinkedIn profile data via the Voyager dash API.

    Uses a single API call to minimise the risk of session invalidation.
    """

    def __init__(self):
        self._headers = {
            "csrf-token": JSESSIONID,
            "cookie": f"li_at={LI_AT}; JSESSIONID=\"{JSESSIONID}\";",
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "x-restli-protocol-version": "2.0.0",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

    @staticmethod
    def _extract_username(linkedin_url: str) -> str:
        """Extract username from a LinkedIn profile URL or plain username."""
        match = re.search(r"linkedin\.com/in/([^/?#]+)", linkedin_url)
        if match:
            return match.group(1).strip("/")
        return linkedin_url.strip().strip("/")

    def get_profile(self, linkedin_url: str) -> dict:
        """Fetch a LinkedIn profile by URL and return normalised JSON.

        Single API call returns profile, positions, education, skills,
        languages, and courses.
        """
        username = self._extract_username(linkedin_url)

        conn = http.client.HTTPSConnection(VOYAGER_HOST)
        path = (
            f"/voyager/api/identity/dash/profiles"
            f"?q=memberIdentity"
            f"&memberIdentity={quote(username, safe='')}"
            f"&decorationId={DECORATION_ID}"
        )
        conn.request("GET", path, headers=self._headers)
        res = conn.getresponse()
        raw = res.read().decode("utf-8")
        conn.close()

        if res.status != 200:
            raise RuntimeError(
                f"Voyager API returned {res.status}: {raw[:500]}"
            )

        data = json.loads(raw)
        return self._normalize(data)

    @staticmethod
    def _normalize(data: dict) -> dict:
        """Map the dash API response into the expected output schema."""

        def _parse_date(d):
            if not d or not isinstance(d, dict):
                return {"year": 0, "month": 0, "day": 0}
            return {
                "year": d.get("year", 0) or 0,
                "month": d.get("month", 0) or 0,
                "day": d.get("day", 0) or 0,
            }

        elements = data.get("included", [])

        profile = {}
        positions = []
        educations = []
        skills = []
        languages = []
        courses = []

        for el in elements:
            t = el.get("$type", "")

            # --- Profile ---
            if t == "com.linkedin.voyager.dash.identity.profile.Profile":
                profile = el

            # --- Positions (skip company-level dupes without a title) ---
            elif t == "com.linkedin.voyager.dash.identity.profile.Position":
                if not el.get("title"):
                    continue
                tp = el.get("dateRange") or el.get("timePeriod") or {}
                positions.append({
                    "companyName": el.get("companyName", ""),
                    "title": el.get("title", ""),
                    "location": (
                        el.get("locationName", "")
                        or el.get("location", "")
                    ),
                    "description": el.get("description", ""),
                    "employmentType": el.get("employmentType", ""),
                    "start": _parse_date(
                        tp.get("start") or tp.get("startDate")
                    ),
                    "end": _parse_date(
                        tp.get("end") or tp.get("endDate")
                    ),
                })

            # --- Education ---
            elif t == "com.linkedin.voyager.dash.identity.profile.Education":
                tp = el.get("dateRange") or el.get("timePeriod") or {}
                educations.append({
                    "start": _parse_date(
                        tp.get("start") or tp.get("startDate")
                    ),
                    "end": _parse_date(
                        tp.get("end") or tp.get("endDate")
                    ),
                    "fieldOfStudy": el.get("fieldOfStudy", ""),
                    "degree": el.get("degreeName", "") or el.get("degree", ""),
                    "grade": el.get("grade", ""),
                    "schoolName": el.get("schoolName", ""),
                    "description": el.get("description", ""),
                    "activities": el.get("activities", ""),
                })

            # --- Skills ---
            elif t == "com.linkedin.voyager.dash.identity.profile.Skill":
                name = el.get("name", "")
                if name:
                    skills.append({"name": name})

            # --- Languages ---
            elif t == "com.linkedin.voyager.dash.identity.profile.Language":
                languages.append({
                    "name": el.get("name", ""),
                    "proficiency": el.get("proficiency", ""),
                })

            # --- Courses ---
            elif t == "com.linkedin.voyager.dash.identity.profile.Course":
                courses.append({
                    "name": el.get("name", ""),
                    "number": el.get("number", ""),
                })

        # Geo
        geo = {"country": "", "city": "", "full": ""}
        for el in elements:
            if el.get("$type") == "com.linkedin.voyager.dash.common.Geo":
                geo = {
                    "country": el.get("countryName", ""),
                    "city": el.get("defaultLocalizedName", ""),
                    "full": el.get("defaultLocalizedName", ""),
                }
                break

        # Profile picture
        profile_pic = ""
        pp = profile.get("profilePicture", {}) or {}
        display_ref = pp.get("displayImageReference", {}) or {}
        vec = display_ref.get("vectorImage", {}) or {}
        root_url = vec.get("rootUrl", "")
        artifacts = vec.get("artifacts", []) or []
        if root_url and artifacts:
            largest = max(artifacts, key=lambda a: a.get("width", 0))
            profile_pic = root_url + largest.get(
                "fileIdentifyingUrlPathSegment", ""
            )

        return {
            "connection": 0,
            "data": {
                "firstName": profile.get("firstName", ""),
                "lastName": profile.get("lastName", ""),
                "isOpenToWork": bool(profile.get("isOpenToWork", False)),
                "isHiring": bool(profile.get("isHiring", False)),
                "profilePicture": profile_pic,
                "summary": profile.get("summary", ""),
                "headline": profile.get("headline", ""),
                "geo": geo,
                "languages": languages,
                "educations": educations,
                "position": positions,
                "skills": skills,
                "courses": courses,
            },
            "follower": 0,
        }
