from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime
from enum import Enum


class Condition(str, Enum):
    NEW = "New"
    USED = "Used"
    UNKNOWN = "Unknown"


class Platform(str, Enum):
    TRADEME = "TradeMe"
    FACEBOOK = "Facebook Marketplace"
    CASH_CONVERTERS = "Cash Converters"
    PBTECH = "PB Tech"
    COMPUTER_LOUNGE = "Computer Lounge"
    NOEL_LEEMING = "Noel Leeming"
    MIGHTY_APE = "MightyApe"
    JB_HIFI = "JB Hi-Fi"
    HARVEY_NORMAN = "Harvey Norman"
    DICK_SMITH = "Dick Smith"


class ParsedQuery(BaseModel):
    keywords: List[str]
    max_price: Optional[float] = None
    min_specs: List[str] = []
    raw_query: str


class NormalizedItem(BaseModel):
    title: str
    price: Optional[float] = None
    price_display: str
    condition: Condition = Condition.UNKNOWN
    platform: str
    url: str
    image_url: Optional[str] = None
    description: Optional[str] = None


class SearchQueryCreate(BaseModel):
    raw_query: str
    notify_telegram: bool = True


class SearchQueryResponse(BaseModel):
    id: str
    raw_query: str
    parsed_keywords: List[str]
    max_price: Optional[float]
    min_specs: List[str]
    is_active: bool
    notify_telegram: bool
    created_at: datetime
    last_run_at: Optional[datetime]
    total_results: int = 0


class FoundItemResponse(BaseModel):
    id: str
    query_id: str
    title: str
    price: Optional[float]
    price_display: str
    condition: str
    platform: str
    url: str
    image_url: Optional[str]
    description: Optional[str]
    found_at: datetime
    notified: bool
    reviewed: bool = False
    reviewed_at: Optional[datetime] = None
    is_likely_fit: Optional[bool] = None
    fit_score: Optional[int] = None
    fit_reason: Optional[str] = None
    price_assessment: Optional[str] = None
    price_assessment_reason: Optional[str] = None


class RunNowRequest(BaseModel):
    query_id: str


class TelegramTestRequest(BaseModel):
    message: str = "Test notification from NZ Market Aggregator! 🎉"


class ItemReviewUpdate(BaseModel):
    reviewed: bool
