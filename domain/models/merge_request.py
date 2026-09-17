"""Typed views over the GitLab webhook payload and the model's review output."""

from typing import List, Optional

from pydantic import BaseModel, Field


class DiffSHAs(BaseModel):
    """The three SHAs GitLab requires to anchor a comment to a diff line."""

    base_sha: Optional[str] = None
    start_sha: Optional[str] = None
    head_sha: Optional[str] = None

    @property
    def complete(self) -> bool:
        return all([self.base_sha, self.start_sha, self.head_sha])


class MergeRequestEvent(BaseModel):
    """The subset of the Merge Request Hook payload this service acts on."""

    project_id: int
    mr_iid: int
    title: str = ""
    description: str = ""
    action: Optional[str] = None
    author_id: Optional[int] = None
    sha: DiffSHAs = Field(default_factory=DiffSHAs)

    @classmethod
    def from_payload(cls, payload: dict) -> "MergeRequestEvent":
        project = payload.get("project") or {}
        attrs = payload.get("object_attributes") or {}
        user = payload.get("user") or {}
        return cls(
            project_id=project.get("id"),
            mr_iid=attrs.get("iid"),
            title=attrs.get("title") or "",
            description=attrs.get("description") or "",
            action=attrs.get("action"),
            author_id=user.get("id"),
            sha=DiffSHAs(
                base_sha=attrs.get("base_sha"),
                start_sha=attrs.get("start_sha"),
                head_sha=attrs.get("head_sha"),
            ),
        )


class InlineComment(BaseModel):
    file_path: str
    line: int
    comment: str


class ChunkReview(BaseModel):
    """One model response, after parsing."""

    inline_comments: List[InlineComment] = Field(default_factory=list)
    summary: str = ""
