from hashlib import sha256

from careerops.domain.assisted_imports import JobSearchQuery, JobSearchResult


class FakeJobSearchProvider:
    provider_name = "fake-search-v1"

    async def search(self, query: JobSearchQuery) -> tuple[JobSearchResult, ...]:
        identity = sha256(
            f"{query.query}|{query.location}|{query.remote}|{query.published_within_days}".encode()
        ).hexdigest()[:12]
        location = "Remote" if query.remote else query.location
        return (
            JobSearchResult(
                provider_result_id=f"fake-{identity}-1",
                company="Example Systems",
                title=f"{query.query} Intern",
                source_url=f"https://jobs.example.test/{identity}/1",
                summary=f"Synthetic result for {query.query}.",
                raw_description=(
                    f"Build and test reliable {query.query} systems. "
                    "Work with Python, PostgreSQL, and distributed queues."
                ),
                location=location,
                published_at=None,
            ),
            JobSearchResult(
                provider_result_id=f"fake-{identity}-2",
                company="Sample Technologies",
                title=f"Junior {query.query}",
                source_url=f"https://jobs.example.test/{identity}/2",
                summary=f"Synthetic listing for {query.query}; full description unavailable.",
                raw_description=None,
                location=location,
                published_at=None,
            ),
        )
