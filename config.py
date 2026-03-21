import os

DB_PATH: str = os.getenv("DB_PATH", "data/jobs.db")

SEARCH_TERMS: list[str] = [
    "Engineering Manager",
    "Head of Engineering",
    "Director of Engineering",
]

# Job description must mention at least REQUIRED_TECH_MIN_MATCHES of these
REQUIRED_TECH: list[str] = [
    "TypeScript",
    "JavaScript",
    "Node.js",
    "NestJS",
    "React",
    "microservices",
    "event-driven",
    "Kafka",
    "Architecture",
]
REQUIRED_TECH_MIN_MATCHES: int = 2
SEARCH_LOCATION: str = "Munich, Germany"
RESULTS_PER_SEARCH: int = int(os.getenv("RESULTS_PER_SEARCH", "200"))
SCRAPE_DELAY_SECONDS: float = float(os.getenv("SCRAPE_DELAY_SECONDS", "3.0"))
