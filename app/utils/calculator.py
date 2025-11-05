"""
거리 계산 및 점수 계산 유틸리티
"""
import math
from datetime import datetime, timedelta
from typing import Dict


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Haversine 공식을 사용한 두 지점 간 거리 계산 (km)
    
    Args:
        lat1: 첫 번째 지점의 위도
        lon1: 첫 번째 지점의 경도
        lat2: 두 번째 지점의 위도
        lon2: 두 번째 지점의 경도
    
    Returns:
        거리 (km)
    """
    # 지구 반지름 (km)
    R = 6371.0
    
    # 라디안으로 변환
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # 차이 계산
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Haversine 공식
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return round(distance, 2)


def calculate_distance_score(distance_km: float, max_distance_km: float = 5.0) -> float:
    """
    거리 기반 점수 계산 (가까울수록 높은 점수)
    
    Args:
        distance_km: 거리 (km)
        max_distance_km: 최대 거리 (km)
    
    Returns:
        거리 점수 (0-30)
    """
    if distance_km >= max_distance_km:
        return 0.0
    
    # 가까울수록 높은 점수 (최대 30점)
    score = 30 * (1 - (distance_km / max_distance_km))
    return round(score, 2)


def calculate_rating_score(rating: float, review_count: int) -> float:
    """
    평점 및 리뷰 수 기반 점수 계산
    
    Args:
        rating: 평점 (0-5)
        review_count: 리뷰 수
    
    Returns:
        평점 점수 (0-20)
    """
    # 평점 점수 (최대 15점)
    rating_score = (rating / 5.0) * 15
    
    # 리뷰 수 점수 (최대 5점)
    # 리뷰가 많을수록 신뢰도 증가
    review_score = min(5, math.log(review_count + 1) / math.log(100) * 5)
    
    return round(rating_score + review_score, 2)


def calculate_event_score(events: list, current_date: datetime = None) -> float:
    """
    이벤트 기반 점수 계산
    
    Args:
        events: 이벤트 목록
        current_date: 현재 날짜 (기본값: 현재 시간)
    
    Returns:
        이벤트 점수 (0-30)
    """
    if not events:
        return 0.0
    
    if current_date is None:
        current_date = datetime.now()
    
    total_score = 0.0
    
    for event in events:
        # 이벤트 타입별 점수
        event_type_scores = {
            "DOUBLE_EXP": 15,
            "TRIPLE_EXP": 20,
            "BONUS_STAMP": 10,
            "DISCOUNT": 8,
            "FREE_ITEM": 12
        }
        
        # 진행 중인 이벤트인지 확인
        if event.start_date <= current_date <= event.end_date:
            base_score = event_type_scores.get(event.event_type, 5)
            
            # 경험치 배수가 있으면 추가 점수
            if hasattr(event, 'exp_multiplier') and event.exp_multiplier:
                base_score *= min(event.exp_multiplier / 2, 1.5)
            
            total_score += base_score
    
    # 최대 30점으로 제한
    return round(min(total_score, 30.0), 2)


def calculate_new_store_score(is_new: bool, opened_date: datetime = None, current_date: datetime = None) -> float:
    """
    신규 오픈 가게 점수 계산
    
    Args:
        is_new: 신규 오픈 여부
        opened_date: 오픈 날짜
        current_date: 현재 날짜 (기본값: 현재 시간)
    
    Returns:
        신규 오픈 점수 (0-20)
    """
    if not is_new or opened_date is None:
        return 0.0
    
    if current_date is None:
        current_date = datetime.now()
    
    # 오픈한 지 얼마나 되었는지 계산
    days_since_open = (current_date - opened_date).days
    
    # 오픈한 지 30일 이내일 때만 점수 부여
    if days_since_open < 0 or days_since_open > 30:
        return 0.0
    
    # 최근 오픈일수록 높은 점수 (최대 20점)
    score = 20 * (1 - (days_since_open / 30))
    
    return round(score, 2)


def calculate_recommendation_score(
    distance_km: float,
    rating: float,
    review_count: int,
    events: list,
    is_new: bool,
    opened_date: datetime = None,
    max_distance_km: float = 5.0
) -> Dict[str, float]:
    """
    종합 추천 점수 계산
    
    Args:
        distance_km: 거리 (km)
        rating: 평점
        review_count: 리뷰 수
        events: 이벤트 목록
        is_new: 신규 오픈 여부
        opened_date: 오픈 날짜
        max_distance_km: 최대 거리
    
    Returns:
        점수 상세 정보 딕셔너리
    """
    distance_score = calculate_distance_score(distance_km, max_distance_km)
    rating_score = calculate_rating_score(rating, review_count)
    event_score = calculate_event_score(events)
    new_store_score = calculate_new_store_score(is_new, opened_date)
    
    total_score = distance_score + rating_score + event_score + new_store_score
    
    return {
        "total": round(total_score, 2),
        "distance": distance_score,
        "rating": rating_score,
        "event": event_score,
        "new_store": new_store_score
    }

