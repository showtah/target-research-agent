from pydantic import BaseModel
from typing import List, Dict, Optional, Any


class CreateQueryInput(BaseModel):
    """
    This class is no longer used as we've changed to direct parameter inputs.
    Keeping it for backward compatibility.
    """
    query: str


class CreateQueryOutput(BaseModel):
    queries: List[str]
    """List of search queries to be passed directly to the target_search tool"""


class TargetSearchInput(BaseModel):
    queries: List[str]
    """The list of search queries from the create_query tool output"""


class TargetSearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: float


class TargetSearchOutput(BaseModel):
    results: List[TargetSearchResult]
    """Search results that must be used to create the final summary"""


class MindmapNode(BaseModel):
    id: str
    label: str
    children: Optional[List['MindmapNode']] = None
    image_url: Optional[str] = None


class CompanyResearchOutput(BaseModel):
    markdown_summary: str
    mindmap: MindmapNode 