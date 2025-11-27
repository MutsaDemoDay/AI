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
    가게 추천 요청 모델 (하위 호환성 유지)
    Spring Boot가 보내는 데이터를 우선 사용하고, 없으면 DB에서 조회
    """
    user_id: Union[str, int] = Field(..., description="사용자 ID")
    location: UserLocation = Field(..., description="사용자 위치")
    
    # 선택적 필드 (Spring Boot가 보낼 수도 있음)
    event_stores: List[EventStore] = Field(default_factory=list, description="이벤트 참여 가게 목록")
    new_stores: List[NewStore] = Field(default_factory=list, description="신규 가입 가게 목록")
    popular_stores: List[PopularStore] = Field(default_factory=list, description="인기 가게 목록")
    visit_statics: List[VisitData] = Field(default_factory=list, description="방문 통계 데이터")
    
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
                    "latitude": 37.556,
                    "longitude": 126.925
                },
                "event_stores": [],
                "new_stores": [],
                "popular_stores": [],
                "visit_statics": []
            }
        }

