"""Pydantic response models — one per tool, replacing raw GitHub JSON."""

from pydantic import BaseModel


class RepoSummary(BaseModel):
    full_name: str
    description: str | None
    stars: int
    forks: int
    open_issues: int
    default_branch: str
    languages: dict[str, int]
    last_commit_date: str | None
    url: str


class Commit(BaseModel):
    sha: str
    message: str
    author: str
    date: str
    url: str


class Issue(BaseModel):
    number: int
    title: str
    labels: list[str]
    age_days: int
    url: str
