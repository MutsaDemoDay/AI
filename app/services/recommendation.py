"""
카테고리별 가게 추천 로직 서비스
"""
from typing import List, Dict
from datetime import datetime, timedelta
from app.models.request import RecommendationRequest
from app.models.response import StoreInfo, StoreEvent, EventType, CategoryRecommendation, RecommendationResponse
from app.utils.calculator import haversine_distance
import pandas as pd
import os


class RecommendationService:
    """가게 추천 서비스"""
    
    def __init__(self):
        """초기화 - lazy loading (첫 요청 시 데이터 로드)"""
        self.stores_df = None
        self._is_loading = False
        print("✅ RecommendationService 초기화 완료")
    
    def _ensure_data_loaded(self):
        """데이터가 로드되었는지 확인하고, 안되어 있으면 로드"""
        if self.stores_df is None and not self._is_loading:
            self._is_loading = True
            try:
                self.stores_df = self._load_stores_from_excel()
                print(f"✅ 가게 데이터 로드 완료: {len(self.stores_df)}개 가게")
            except Exception as e:
                print(f"❌ 데이터 로드 실패: {e}")
                # 최소한의 Mock 데이터
                self.stores_df = pd.DataFrame([{
                    "store_id": "store0001",
                    "name": "테스트 카페",
                    "category": "카페",
                    "address": "서울시 마포구",
                    "latitude": 37.5665,
                    "longitude": 126.9780,
                    "rating": 4.5,
                    "review_count": 100
                }])
            finally:
                self._is_loading = False
    
    def _load_stores_from_excel(self) -> pd.DataFrame:
        try:
            # ai_data 폴더에서 파일 찾기
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            excel_path = os.path.join(current_dir, "..", "ai_data", "마포구_전체_가게_위경도.xlsx")
            
            # 파일이 없으면 기본 파일 사용
            if not os.path.exists(excel_path):
                excel_path = os.path.join(current_dir, "..", "ai_data", "마포구_전체_가게.xlsx")
            
            df = pd.read_excel(excel_path)
            
            # 필요한 컬럼만 선택 및 이름 변경
            # 업소명 → name, 소재지(도로명) → address, 업태명 → category
            df = df.rename(columns={
                '업소명': 'name',
                '소재지(도로명)': 'address',
                '업태명': 'category',
                '위도': 'latitude',
                '경도': 'longitude'
            })
            
            # store_id 생성 (인덱스 기반)
            df['store_id'] = df.index.map(lambda x: f"store{x:04d}")
            
            # 위도/경도가 있는 행만 사용
            if 'latitude' in df.columns and 'longitude' in df.columns:
                df = df[df['latitude'].notna() & df['longitude'].notna()]
            
            # 기본 rating과 review_count 추가 (실제로는 DB에서 가져와야 함)
            if 'rating' not in df.columns:
                df['rating'] = 4.0 + (df.index % 10) / 10  # 4.0 ~ 4.9 랜덤
            if 'review_count' not in df.columns:
                df['review_count'] = 50 + (df.index % 20) * 10  # 50 ~ 240
            
            return df
            
        except Exception as e:
            print(f"❌ xlsx 파일 로드 실패: {str(e)}")
            print("Mock 데이터를 사용합니다.")
            # Mock 데이터 반환
            return pd.DataFrame([
                {
                    "store_id": "store001",
                    "name": "스타벅스 강남점",
                    "category": "카페",
                    "address": "서울시 강남구 역삼동",
                    "latitude": 37.5665,
                    "longitude": 126.9780,
                    "rating": 4.5,
                    "review_count": 120,
                },
            ])
    
    def _get_store_by_id(self, store_id: str) -> Dict:
        """가게 ID로 가게 정보 조회"""
        self._ensure_data_loaded()  # 데이터 로드 확인
        store_row = self.stores_df[self.stores_df['store_id'] == store_id]
        if len(store_row) == 0:
            return None
        return store_row.iloc[0].to_dict()
    
    def _calculate_distance(self, user_lat: float, user_lon: float, store: Dict) -> float:
        """사용자와 가게 사이의 거리 계산"""
        return haversine_distance(user_lat, user_lon, store["latitude"], store["longitude"])
    
    def _create_store_info(self, store: Dict, distance: float, score: float, reasons: List[str]) -> StoreInfo:
        """StoreInfo 객체 생성"""
        return StoreInfo(
            store_id=store["store_id"],
            name=store["name"],
            category=store["category"],
            address=store["address"],
            latitude=store["latitude"],
            longitude=store["longitude"],
            distance_km=distance,
            rating=store["rating"],
            review_count=store["review_count"],
            is_new=False,
            opened_date=None,
            events=None,
            recommendation_score=score,
            recommendation_reason=reasons
        )
    
    def recommend_event_stores(self, request: RecommendationRequest) -> List[StoreInfo]:
        """
        1. 이벤트 참여 가게 추천 (경험치 2배 부여 등)
        - 경험치 배수가 높은 순
        - 거리가 가까운 순
        - 최대 2개
        """
        user_lat = request.location.latitude
        user_lon = request.location.longitude
        
        candidates = []
        
        for event_store in request.event_stores:
            # Spring의 store_id(숫자)를 xlsx 형식으로 변환
            # "1" -> "store0001", "24" -> "store0024"
            xlsx_store_id = f"store{int(event_store.store_id):04d}"
            
            # xlsx에서 가게 조회
            store = self._get_store_by_id(xlsx_store_id)
            if not store:
                print(f"⚠️ 가게를 찾을 수 없음: Spring ID={event_store.store_id}, xlsx ID={xlsx_store_id}")
                continue
            
            distance = self._calculate_distance(user_lat, user_lon, store)
            
            # 점수 = 경험치 배수 * 30 - 거리 * 2 (거리 패널티)
            score = event_store.exp_multiplier * 30 - distance * 2
            
            reasons = [
                f"경험치 {event_store.exp_multiplier}배 이벤트",
                f"거리 {distance:.1f}km"
            ]
            
            store_info = self._create_store_info(store, distance, score, reasons)
            candidates.append(store_info)
        
        # 점수 높은 순으로 정렬
        candidates.sort(key=lambda x: x.recommendation_score, reverse=True)
        
        return candidates[:2]
    
    def recommend_new_stores(self, request: RecommendationRequest) -> List[StoreInfo]:
        """
        2. 신규 가입 가게 추천
        - 최근 가입한 순
        - 거리가 가까운 순
        - 최대 2개
        """
        user_lat = request.location.latitude
        user_lon = request.location.longitude
        current_date = datetime.now()
        
        candidates = []
        
        for new_store in request.new_stores:
            # Spring의 store_id(숫자)를 xlsx 형식으로 변환
            xlsx_store_id = f"store{int(new_store.store_id):04d}"
            
            # xlsx에서 가게 조회
            store = self._get_store_by_id(xlsx_store_id)
            if not store:
                print(f"⚠️ 가게를 찾을 수 없음: Spring ID={new_store.store_id}, xlsx ID={xlsx_store_id}")
                continue
            
            distance = self._calculate_distance(user_lat, user_lon, store)
            
            # 가입한 지 며칠 됐는지
            days_since_joined = (current_date - new_store.joined_date).days
            
            # 점수 = (30 - 가입일수) * 2 - 거리 * 2
            # 최근 가입일수록 높은 점수
            score = max(0, (30 - days_since_joined) * 2) - distance * 2
            
            reasons = [
                f"{days_since_joined}일 전 신규 가입",
                f"거리 {distance:.1f}km"
            ]
            
            store_info = self._create_store_info(store, distance, score, reasons)
            candidates.append(store_info)
        
        # 점수 높은 순으로 정렬
        candidates.sort(key=lambda x: x.recommendation_score, reverse=True)
        
        return candidates[:2]
    
    def recommend_popular_stores(self, request: RecommendationRequest) -> List[StoreInfo]:
        """
        3. 인기 가게 추천 (유저들이 많이 방문한 가게)
        - 방문 횟수가 많은 순
        - 거리가 가까운 순
        - 최대 2개
        """
        user_lat = request.location.latitude
        user_lon = request.location.longitude
        
        candidates = []
        
        for popular_store in request.popular_stores:
            # Spring의 store_id(숫자)를 xlsx 형식으로 변환
            xlsx_store_id = f"store{int(popular_store.store_id):04d}"
            
            # xlsx에서 가게 조회
            store = self._get_store_by_id(xlsx_store_id)
            if not store:
                print(f"⚠️ 가게를 찾을 수 없음: Spring ID={popular_store.store_id}, xlsx ID={xlsx_store_id}")
                continue
            
            distance = self._calculate_distance(user_lat, user_lon, store)
            
            # 점수 = 방문횟수 / 10 - 거리 * 2
            score = popular_store.visit_count / 10 - distance * 2
            
            reasons = [
                f"방문 {popular_store.visit_count}회",
                f"거리 {distance:.1f}km",
                "인기 많은 가게"
            ]
            
            store_info = self._create_store_info(store, distance, score, reasons)
            candidates.append(store_info)
        
        # 점수 높은 순으로 정렬
        candidates.sort(key=lambda x: x.recommendation_score, reverse=True)
        
        return candidates[:2]
    
    def recommend_nearby_stores(self, request: RecommendationRequest) -> List[StoreInfo]:
        """
        4. 가까운 가게 추천
        - 거리가 가까운 순
        - 평점이 높은 순
        - 최대 2개
        """
        self._ensure_data_loaded()  # 데이터 로드 확인
        
        user_lat = request.location.latitude
        user_lon = request.location.longitude
        
        # 이미 추천된 가게 ID들
        recommended_ids = set()
        for event_store in request.event_stores:
            recommended_ids.add(event_store.store_id)
        for new_store in request.new_stores:
            recommended_ids.add(new_store.store_id)
        for popular_store in request.popular_stores:
            recommended_ids.add(popular_store.store_id)
        
        candidates = []
        
        # DataFrame에서 반복
        for idx, store in self.stores_df.iterrows():
            # 이미 추천된 가게는 제외
            if store["store_id"] in recommended_ids:
                continue
            
            store_dict = store.to_dict()
            distance = self._calculate_distance(user_lat, user_lon, store_dict)
            
            # 5km 이내만
            if distance > 5.0:
                continue
            
            # 점수 = 30 - 거리 * 5 + 평점 * 2
            score = 30 - distance * 5 + store_dict["rating"] * 2
            
            reasons = [
                f"거리 {distance:.1f}km",
                f"평점 {store_dict['rating']:.1f}"
            ]
            
            store_info = self._create_store_info(store_dict, distance, score, reasons)
            candidates.append(store_info)
        
        # 점수 높은 순으로 정렬 (거리가 가깝고 평점이 높은 순)
        candidates.sort(key=lambda x: x.recommendation_score, reverse=True)
        
        return candidates[:2]
    
    def recommend_stores(self, request: RecommendationRequest) -> RecommendationResponse:
        """
        4개 카테고리별로 2개씩 가게 추천
        """
        try:
            recommendations = []
            
            # 1. 이벤트 참여 가게
            event_stores = self.recommend_event_stores(request)
            recommendations.append(CategoryRecommendation(
                category="이벤트 참여 가게",
                stores=event_stores
            ))
            
            # 2. 신규 가입 가게
            new_stores = self.recommend_new_stores(request)
            recommendations.append(CategoryRecommendation(
                category="신규 가입 가게",
                stores=new_stores
            ))
            
            # 3. 인기 가게
            popular_stores = self.recommend_popular_stores(request)
            recommendations.append(CategoryRecommendation(
                category="인기 가게",
                stores=popular_stores
            ))
            
            # 4. 가까운 가게
            nearby_stores = self.recommend_nearby_stores(request)
            recommendations.append(CategoryRecommendation(
                category="가까운 가게",
                stores=nearby_stores
            ))
            
            return RecommendationResponse(
                success=True,
                message="카테고리별 추천 가게 목록을 성공적으로 가져왔습니다.",
                user_id=request.user_id,
                recommendations=recommendations
            )
        
        except Exception as e:
            return RecommendationResponse(
                success=False,
                message=f"오류가 발생했습니다: {str(e)}",
                user_id=request.user_id,
                recommendations=[]
            )
