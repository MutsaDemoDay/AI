"""
API 요청 모델 정의
Spring Boot에서 전송하는 데이터 형식에 맞춰 설계
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Union
from datetime import datetime


class UserLocation(BaseModel):
    """사용자 위치 정보"""
    latitude: float = Field(..., description="위도")
    longitude: float = Field(..., description="경도")


class EventStore(BaseModel):
    """이벤트 참여 가게 정보"""
    store_id: Optional[Union[str, int]] = Field(None, description="가게 ID (선택)")
    store_address: Optional[str] = Field(None, description="가게 주소 (도로명)")
    exp_multiplier: float = Field(..., description="경험치 배수 (2배, 3배 등)")
    
    @field_validator('store_id')
    @classmethod
    def convert_store_id_to_str(cls, v):
        """store_id를 문자열로 변환"""
        if v is None:
            return None
        return str(v)


class NewStore(BaseModel):
    """신규 가입 가게 정보"""
    store_id: Optional[Union[str, int]] = Field(None, description="가게 ID (선택)")
    store_address: Optional[str] = Field(None, description="가게 주소 (도로명)")
    joined_date: Union[datetime, str] = Field(..., description="가입 날짜")
    
    @field_validator('store_id')
    @classmethod
    def convert_store_id_to_str(cls, v):
        """store_id를 문자열로 변환"""
        if v is None:
            return None
        return str(v)
    
    @field_validator('joined_date')
    @classmethod
    def parse_joined_date(cls, v):
        """날짜 문자열을 datetime으로 변환"""
        if isinstance(v, str):
            # "2025-11-05" 형식을 "2025-11-05T00:00:00"으로 변환
            if 'T' not in v:
                v = v + 'T00:00:00'
            return datetime.fromisoformat(v)
        return v


class PopularStore(BaseModel):
    """인기 가게 정보"""
    store_id: Optional[Union[str, int]] = Field(None, description="가게 ID (선택)")
    store_address: Optional[str] = Field(None, description="가게 주소 (도로명)")
    visit_count: int = Field(..., description="방문 횟수")
    
    @field_validator('store_id')
    @classmethod
    def convert_store_id_to_str(cls, v):
        """store_id를 문자열로 변환"""
        if v is None:
            return None
        return str(v)


class VisitData(BaseModel):
    """
    사용자-가게 방문 데이터 (협업 필터링용)
    Spring Boot에서 visit_statics로 전송됨
    """
    user_id: Union[str, int] = Field(..., description="사용자 ID")
    store_id: Optional[Union[str, int]] = Field(None, description="가게 ID (선택)")
    store_address: Optional[str] = Field(None, description="가게 주소 (도로명)")
    visit_count: int = Field(..., description="방문 횟수")
    
    @field_validator('user_id', 'store_id')
    @classmethod
    def convert_to_str(cls, v):
        """user_id와 store_id를 문자열로 변환"""
        if v is None:
            return None
        return str(v)


class RecommendationRequest(BaseModel):
    """
    가게 추천 요청 모델
    Spring Boot AiRequest와 동일한 구조
    """
    user_id: Union[str, int] = Field(..., description="사용자 ID")
    location: UserLocation = Field(..., description="사용자 위치")
    event_stores: List[EventStore] = Field(default_factory=list, description="이벤트 참여 가게 목록")
    new_stores: List[NewStore] = Field(default_factory=list, description="신규 가입 가게 목록")
    popular_stores: List[PopularStore] = Field(default_factory=list, description="인기 가게 목록")
    visit_statics: List[VisitData] = Field(default_factory=list, description="방문 통계 데이터 (협업 필터링용)")
    
    @field_validator('user_id')
    @classmethod
    def convert_user_id_to_str(cls, v):
        """user_id를 문자열로 변환"""
        return str(v)
    
    @property
    def visit_data(self) -> List[VisitData]:
        """visit_statics를 visit_data로 접근할 수 있도록 별칭 제공"""
        return self.visit_statics
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 2,
                "location": {
                    "latitude": 37.111,
                    "longitude": 126.111
                },
                "event_stores": [
                    {"store_id": 1, "exp_multiplier": 2.0},
                    {"store_id": 2, "exp_multiplier": 1.0}
                ],
                "new_stores": [
                    {"store_id": 15, "joined_date": "2025-11-05"},
                    {"store_id": 12, "joined_date": "2025-11-05"}
                ],
                "popular_stores": [
                    {"store_id": 3, "visit_count": 4},
                    {"store_id": 2, "visit_count": 3}
                ],
                "visit_statics": [
                    {"user_id": 2, "store_id": 14, "visit_count": 1},
                    {"user_id": 2, "store_id": 3, "visit_count": 1},
                    {"user_id": 2, "store_id": 8, "visit_count": 1}
                ]
            }
        }

