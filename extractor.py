import re
import json

TECH_KEYWORDS: dict[str, list[str]] = {
    "languages": [
        "Python", "Go", "Golang", "Java", "Kotlin", "TypeScript",
        "JavaScript", "Rust", "C++", "Scala", "Ruby", "Swift", "PHP",
    ],
    "cloud": ["AWS", "GCP", "Azure", "Google Cloud"],
    "infra": [
        "Kubernetes", "k8s", "Docker", "Terraform", "Helm",
        "Ansible", "ArgoCD", "Pulumi", "Linux",
    ],
    "data": [
        "Kafka", "Spark", "Flink", "dbt", "Airflow", "Snowflake",
        "BigQuery", "Redshift", "PostgreSQL", "MySQL", "MongoDB",
        "Redis", "Elasticsearch", "Databricks",
    ],
    "practices": [
        "microservices", "event-driven", "CI/CD", "DevOps",
        "platform engineering", "SRE", "agile", "scrum",
        "domain-driven design", "DDD",
    ],
    "observability": [
        "Datadog", "Grafana", "Prometheus", "Splunk",
        "New Relic", "OpenTelemetry",
    ],
    "ml_ai": ["ML", "machine learning", "LLM", "GenAI", "AI", "MLOps"],
}

def extract_tech_stack(description: str) -> list[str]:
    found: set[str] = set()
    for keywords in TECH_KEYWORDS.values():
        for kw in keywords:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, description, re.IGNORECASE):
                found.add(kw)
    return sorted(found)


def enrich_job(job: dict) -> dict:
    desc = job.get("description", "") or ""
    job["tech_stack"] = json.dumps(extract_tech_stack(desc))
    job["team_size_signals"] = None
    return job
