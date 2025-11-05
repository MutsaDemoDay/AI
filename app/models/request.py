"""
API 요청 모델 정의
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class UserLocation(BaseModel):
    """사용자 위치 정보"""
    latitude: float = Field(..., description="위도")
    longitude: float = Field(..., description="경도")


class EventStore(BaseModel):
    """이벤트 참여 가게 정보"""
    store_id: str = Field(..., description="가게 ID")
    exp_multiplier: float = Field(..., description="경험치 배수 (2배, 3배 등)")


class NewStore(BaseModel):
    """신규 가입 가게 정보"""
    store_id: str = Field(..., description="가게 ID")
    joined_date: datetime = Field(..., description="가입 날짜")


class PopularStore(BaseModel):
    """인기 가게 정보"""
    store_id: str = Field(..., description="가게 ID")
    visit_count: int = Field(..., description="방문 횟수")


class RecommendationRequest(BaseModel):
    """가게 추천 요청 모델"""
    user_id: str = Field(..., description="사용자 ID")
    location: UserLocation = Field(..., description="사용자 위치")
    event_stores: List[EventStore] = Field(default_factory=list, description="이벤트 참여 가게 목록")
    new_stores: List[NewStore] = Field(default_factory=list, description="신규 가입 가게 목록")
    popular_stores: List[PopularStore] = Field(default_factory=list, description="인기 가게 목록")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "location": {
                    "latitude": 37.5665,
                    "longitude": 126.9780
                },
                "event_stores": [
                    {"store_id": "store001", "exp_multiplier": 2.0},
                    {"store_id": "store002", "exp_multiplier": 3.0}
                ],
                "new_stores": [
                    {"store_id": "store003", "joined_date": "2025-11-01T00:00:00"},
                    {"store_id": "store004", "joined_date": "2025-11-03T00:00:00"}
                ],
                "popular_stores": [
                    {"store_id": "store005", "visit_count": 150},
                    {"store_id": "store006", "visit_count": 120}
                ]
            }
        }

