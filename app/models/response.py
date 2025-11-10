"""
API 응답 모델 정의
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    """이벤트 타입"""
    DOUBLE_EXP = "DOUBLE_EXP"  # 경험치 2배
    TRIPLE_EXP = "TRIPLE_EXP"  # 경험치 3배
    BONUS_STAMP = "BONUS_STAMP"  # 보너스 스탬프
    DISCOUNT = "DISCOUNT"  # 할인
    FREE_ITEM = "FREE_ITEM"  # 무료 아이템


class StoreEvent(BaseModel):
    """가게 이벤트 정보"""
    event_id: str = Field(..., description="이벤트 ID")
    event_type: EventType = Field(..., description="이벤트 타입")
    title: str = Field(..., description="이벤트 제목")
    description: Optional[str] = Field(default=None, description="이벤트 설명")
    start_date: datetime = Field(..., description="시작 날짜")
    end_date: datetime = Field(..., description="종료 날짜")
    exp_multiplier: Optional[float] = Field(default=1.0, description="경험치 배수")


class StoreInfo(BaseModel):
    """가게 정보"""
    store_id: str = Field(..., description="가게 ID")
    name: str = Field(..., description="가게 이름")
    category: str = Field(..., description="카테고리")
    address: str = Field(..., description="주소")
    latitude: float = Field(..., description="위도")
    longitude: float = Field(..., description="경도")
    distance_km: float = Field(..., description="사용자로부터의 거리 (km)")
    rating: float = Field(..., description="평점")
    review_count: int = Field(..., description="리뷰 수")
    is_new: bool = Field(default=False, description="신규 오픈 여부")
    opened_date: Optional[datetime] = Field(default=None, description="오픈 날짜")
    events: Optional[List[StoreEvent]] = Field(default=None, description="진행 중인 이벤트")
    recommendation_score: float = Field(..., description="추천 점수")
    recommendation_reason: List[str] = Field(default_factory=list, description="추천 이유")


class SimpleStoreInfo(BaseModel):
    """간단한 가게 정보 (Spring Boot 연동용)"""
    name: str = Field(..., description="가게 이름")
    address: str = Field(..., description="주소")


class CategoryRecommendation(BaseModel):
    """카테고리별 추천"""
    category: str = Field(..., description="카테고리 이름")
    stores: List[SimpleStoreInfo] = Field(default_factory=list, description="추천 가게 목록 (최대 2개)")


class RecommendationResponse(BaseModel):
    """가게 추천 응답 모델"""
    success: bool = Field(..., description="요청 성공 여부")
    user_id: str = Field(..., description="사용자 ID")
    recommendations: List[CategoryRecommendation] = Field(default_factory=list, description="카테고리별 추천")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "user_id": "user123",
                "recommendations": [
                    {
                        "category": "이벤트 참여 가게",
                        "stores": [
                            {
                                "store_id": "store001",
                                "name": "스타벅스 강남점",
                                "category": "카페",
                                "distance_km": 0.5,
                                "recommendation_score": 95.5
                            }
                        ]
                    },
                    {
                        "category": "신규 가입 가게",
                        "stores": []
                    },
                    {
                        "category": "인기 가게",
                        "stores": []
                    },
                    {
                        "category": "가까운 가게",
                        "stores": []
                    }
                ]
            }
        }

