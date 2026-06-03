from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ToolName = Literal[
    "web_search",
    "fetch_url",
    "get_time",
    "currency_convert",
    "read_file",
    "list_dir",
    "create_file",
    "update_file",
    "edit_file",
    "index_document",
    "search_knowledge",
    "remember",
    "final_answer",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WebSearchArgs(StrictModel):
    query: str = Field(min_length=1)
    max_results: int = Field(default=3, ge=1, le=5)


class FetchUrlArgs(StrictModel):
    url: str = Field(min_length=1)
    timeout: int = Field(default=20, ge=5, le=60)


class GetTimeArgs(StrictModel):
    timezone: str = Field(default="UTC", min_length=1)


class CurrencyConvertArgs(StrictModel):
    amount: float
    from_currency: str = Field(min_length=3, max_length=3)
    to_currency: str = Field(min_length=3, max_length=3)


class ReadFileArgs(StrictModel):
    path: str = Field(min_length=1)


class ListDirArgs(StrictModel):
    path: str = Field(default=".")


class CreateFileArgs(StrictModel):
    path: str = Field(min_length=1)
    content: str


class UpdateFileArgs(StrictModel):
    path: str = Field(min_length=1)
    content: str


class EditFileArgs(StrictModel):
    path: str = Field(min_length=1)
    find: str = Field(min_length=1)
    replace: str
    replace_all: bool = False


class IndexDocumentArgs(StrictModel):
    path: str = Field(min_length=1)
    chunk_size: int = Field(default=400, ge=50, le=2000)
    overlap: int = Field(default=80, ge=0, le=1000)

    @model_validator(mode="after")
    def _valid_window(self) -> "IndexDocumentArgs":
        if self.overlap >= self.chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        return self


class SearchKnowledgeArgs(StrictModel):
    query: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=20)


class RememberArgs(StrictModel):
    fact: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class FinalAnswerArgs(StrictModel):
    answer: str = Field(min_length=1)
    sources: list[str] = Field(default_factory=list)


class WebSearchAction(WebSearchArgs):
    kind: Literal["web_search"] = "web_search"


class FetchUrlAction(FetchUrlArgs):
    kind: Literal["fetch_url"] = "fetch_url"


class GetTimeAction(GetTimeArgs):
    kind: Literal["get_time"] = "get_time"


class CurrencyConvertAction(CurrencyConvertArgs):
    kind: Literal["currency_convert"] = "currency_convert"


class ReadFileAction(ReadFileArgs):
    kind: Literal["read_file"] = "read_file"


class ListDirAction(ListDirArgs):
    kind: Literal["list_dir"] = "list_dir"


class CreateFileAction(CreateFileArgs):
    kind: Literal["create_file"] = "create_file"


class UpdateFileAction(UpdateFileArgs):
    kind: Literal["update_file"] = "update_file"


class EditFileAction(EditFileArgs):
    kind: Literal["edit_file"] = "edit_file"


class IndexDocumentAction(IndexDocumentArgs):
    kind: Literal["index_document"] = "index_document"


class SearchKnowledgeAction(SearchKnowledgeArgs):
    kind: Literal["search_knowledge"] = "search_knowledge"


class RememberAction(RememberArgs):
    kind: Literal["remember"] = "remember"


class FinalAnswerAction(FinalAnswerArgs):
    kind: Literal["final_answer"] = "final_answer"


ActionSpec = Annotated[
    WebSearchAction
    | FetchUrlAction
    | GetTimeAction
    | CurrencyConvertAction
    | ReadFileAction
    | ListDirAction
    | CreateFileAction
    | UpdateFileAction
    | EditFileAction
    | IndexDocumentAction
    | SearchKnowledgeAction
    | RememberAction
    | FinalAnswerAction,
    Field(discriminator="kind"),
]


class ToolObservation(StrictModel):
    iteration: int = Field(ge=1)
    action: ToolName
    ok: bool
    summary: str
    raw_json: str = ""


class PerceptionInput(StrictModel):
    query: str
    observations: list[ToolObservation] = Field(default_factory=list)


class PerceptionOutput(StrictModel):
    normalized_query: str
    user_goal: str
    query_type: Literal[
        "web_research",
        "time",
        "currency",
        "file_task",
        "memory_store",
        "memory_recall",
        "general",
    ]
    likely_tools: list[ToolName] = Field(default_factory=list)
    facts_to_remember: list[str] = Field(default_factory=list)
    answer_must_include: list[str] = Field(default_factory=list)
    completion_criteria: str


class MemoryFact(StrictModel):
    id: str
    fact: str
    tags: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None
    source_query: str = ""
    created_at: datetime
    updated_at: datetime


class MemoryHit(StrictModel):
    fact_id: str
    fact: str
    relevance: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class MemoryRecallInput(StrictModel):
    query: str
    perception: PerceptionOutput
    max_facts: int = Field(default=5, ge=1, le=20)


class MemoryRecallOutput(StrictModel):
    hits: list[MemoryHit] = Field(default_factory=list)
    store_path: str


class MemoryWriteInput(StrictModel):
    fact: str
    source_query: str = ""
    tags: list[str] = Field(default_factory=list)


class MemoryWriteOutput(StrictModel):
    fact: MemoryFact
    created: bool
    store_path: str


class MemoryRankingCandidate(StrictModel):
    fact_id: str
    fact: str
    tags: list[str] = Field(default_factory=list)


class MemoryRankingInput(StrictModel):
    query: str
    candidates: list[MemoryRankingCandidate]
    max_facts: int


class MemoryRankingOutput(StrictModel):
    hits: list[MemoryHit] = Field(default_factory=list)


class DecisionInput(StrictModel):
    query: str
    perception: PerceptionOutput
    memory: MemoryRecallOutput
    observations: list[ToolObservation] = Field(default_factory=list)
    iteration: int = Field(ge=1)
    max_iterations: int = Field(ge=1)


class DecisionOutput(StrictModel):
    next_action: ToolName
    rationale: str
    web_search: WebSearchArgs | None = None
    fetch_url: FetchUrlArgs | None = None
    get_time: GetTimeArgs | None = None
    currency_convert: CurrencyConvertArgs | None = None
    read_file: ReadFileArgs | None = None
    list_dir: ListDirArgs | None = None
    create_file: CreateFileArgs | None = None
    update_file: UpdateFileArgs | None = None
    edit_file: EditFileArgs | None = None
    index_document: IndexDocumentArgs | None = None
    search_knowledge: SearchKnowledgeArgs | None = None
    remember: RememberArgs | None = None
    final_answer: FinalAnswerArgs | None = None

    @model_validator(mode="after")
    def _matching_payload(self) -> "DecisionOutput":
        payload = getattr(self, self.next_action)
        if payload is None:
            if self.next_action == "get_time":
                self.get_time = GetTimeArgs()
                return self
            if self.next_action == "list_dir":
                self.list_dir = ListDirArgs()
                return self
            raise ValueError(f"{self.next_action} payload is required")
        return self

    def to_action(self) -> ActionSpec:
        if self.next_action == "web_search":
            return WebSearchAction(**self.web_search.model_dump())
        if self.next_action == "fetch_url":
            return FetchUrlAction(**self.fetch_url.model_dump())
        if self.next_action == "get_time":
            return GetTimeAction(**self.get_time.model_dump())
        if self.next_action == "currency_convert":
            return CurrencyConvertAction(**self.currency_convert.model_dump())
        if self.next_action == "read_file":
            return ReadFileAction(**self.read_file.model_dump())
        if self.next_action == "list_dir":
            return ListDirAction(**self.list_dir.model_dump())
        if self.next_action == "create_file":
            return CreateFileAction(**self.create_file.model_dump())
        if self.next_action == "update_file":
            return UpdateFileAction(**self.update_file.model_dump())
        if self.next_action == "edit_file":
            return EditFileAction(**self.edit_file.model_dump())
        if self.next_action == "index_document":
            return IndexDocumentAction(**self.index_document.model_dump())
        if self.next_action == "search_knowledge":
            return SearchKnowledgeAction(**self.search_knowledge.model_dump())
        if self.next_action == "remember":
            return RememberAction(**self.remember.model_dump())
        return FinalAnswerAction(**self.final_answer.model_dump())


class ActionInput(StrictModel):
    iteration: int = Field(ge=1)
    action: ActionSpec
    source_query: str = ""


class ActionOutput(ToolObservation):
    pass


class AgentResult(StrictModel):
    query: str
    answer: str
    iterations: int
    observations: list[ToolObservation] = Field(default_factory=list)
