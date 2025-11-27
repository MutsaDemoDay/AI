"""
카테고리별 가게 추천 로직 서비스
"""
from typing import List, Dict
from datetime import datetime, timedelta
from app.models.request import RecommendationRequest
from app.models.response import StoreInfo, StoreEvent, EventType, CategoryRecommendation, RecommendationResponse, SimpleStoreInfo
from app.utils.calculator import haversine_distance
from app.services.collaborative_filtering import CollaborativeFilteringModel
import pandas as pd
import os
import pymysql
from sqlalchemy import create_engine
from app.config import get_database_url


class RecommendationService:
    """가게 추천 서비스"""
    
    def __init__(self):
        """초기화 - lazy loading (첫 요청 시 데이터 로드)"""
        self.stores_df = None
        self._is_loading = False
        self.cf_model = CollaborativeFilteringModel()
        self.db_engine = None  # SQLAlchemy 엔진
        print("RecommendationService 초기화 완료")
    
    def _fetch_event_stores_from_db(self) -> List[Dict]:
        """
        DB에서 이벤트 참여 가게 조회
        Returns:
            [{"store_address": "주소", "exp_multiplier": 2.0}, ...]
        """
        engine = self._get_db_engine()
        if engine is None:
            print("DB 연결 실패로 이벤트 가게를 조회할 수 없습니다.")
            return []
        
        try:
            # exp_multiplier가 1보다 큰 가게들 조회 (이벤트 참여 중)
            # stores 테이블에 exp_multiplier 컬럼이 있다고 가정
            query = """
                SELECT 
                    address as store_address,
                    COALESCE(exp_multiplier, 1.0) as exp_multiplier
                FROM stores
                WHERE exp_multiplier > 1.0
                  AND address IS NOT NULL 
                  AND address != ''
                ORDER BY exp_multiplier DESC
                LIMIT 20
            """
            
            df = pd.read_sql(query, engine)
            
            if df.empty:
                print("이벤트 참여 가게가 없습니다.")
                return []
            
            result = df.to_dict('records')
            print(f"DB에서 이벤트 가게 {len(result)}개 조회 완료")
            return result
            
        except Exception as e:
            print(f"이벤트 가게 조회 실패: {e}")
            return []
    
    def _fetch_new_stores_from_db(self) -> List[Dict]:
        """
        DB에서 신규 가입 가게 조회 (최근 30일 이내)
        Returns:
            [{"store_address": "주소", "joined_date": datetime}, ...]
        """
        engine = self._get_db_engine()
        if engine is None:
            print("DB 연결 실패로 신규 가게를 조회할 수 없습니다.")
            return []
        
        try:
            # 최근 30일 이내 가입한 가게들 조회
            query = """
                SELECT 
                    address as store_address,
                    joined_date
                FROM stores
                WHERE joined_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                  AND address IS NOT NULL 
                  AND address != ''
                ORDER BY joined_date DESC
                LIMIT 20
            """
            
            df = pd.read_sql(query, engine)
            
            if df.empty:
                print("신규 가입 가게가 없습니다.")
                return []
            
            result = df.to_dict('records')
            print(f"DB에서 신규 가게 {len(result)}개 조회 완료")
            return result
            
        except Exception as e:
            print(f"신규 가게 조회 실패: {e}")
            return []
    
    def _fetch_popular_stores_from_db(self) -> List[Dict]:
        """
        DB에서 인기 가게 조회 (방문 횟수 많은 순)
        Returns:
            [{"store_address": "주소", "visit_count": 10}, ...]
        """
        engine = self._get_db_engine()
        if engine is None:
            print("DB 연결 실패로 인기 가게를 조회할 수 없습니다.")
            return []
        
        try:
            # 전체 사용자의 방문 횟수를 집계하여 인기 가게 찾기
            queries = [
                # Case 1: stores.store_id
                """
                    SELECT 
                        s.address as store_address,
                        COUNT(o.order_id) as visit_count
                    FROM orders o
                    INNER JOIN stores s ON o.store_id = s.store_id
                    WHERE s.address IS NOT NULL 
                      AND s.address != ''
                    GROUP BY s.address
                    HAVING visit_count > 0
                    ORDER BY visit_count DESC
                    LIMIT 20
                """,
                # Case 2: stores.id
                """
                    SELECT 
                        s.address as store_address,
                        COUNT(o.order_id) as visit_count
                    FROM orders o
                    INNER JOIN stores s ON o.store_id = s.id
                    WHERE s.address IS NOT NULL 
                      AND s.address != ''
                    GROUP BY s.address
                    HAVING visit_count > 0
                    ORDER BY visit_count DESC
                    LIMIT 20
                """
            ]
            
            df = None
            for i, query in enumerate(queries, 1):
                try:
                    df = pd.read_sql(query, engine)
                    print(f"인기 가게 쿼리 패턴 {i} 성공!")
                    break
                except Exception as e:
                    print(f"인기 가게 쿼리 패턴 {i} 실패: {str(e)[:100]}")
                    continue
            
            if df is None or df.empty:
                print("인기 가게가 없습니다.")
                return []
            
            result = df.to_dict('records')
            # visit_count를 int로 변환
            for record in result:
                record['visit_count'] = int(record['visit_count'])
            
            print(f"DB에서 인기 가게 {len(result)}개 조회 완료")
            return result
            
        except Exception as e:
            print(f"인기 가게 조회 실패: {e}")
            return []
    
    def _fetch_user_visit_data_from_db(self, user_id: str) -> List[Dict]:
        """
        DB에서 특정 사용자의 방문 데이터 조회
        Args:
            user_id: 사용자 ID
        Returns:
            [{"user_id": "2", "store_address": "주소", "visit_count": 5}, ...]
        """
        engine = self._get_db_engine()
        if engine is None:
            print("DB 연결 실패로 사용자 방문 데이터를 조회할 수 없습니다.")
            return []
        
        try:
            queries = [
                # Case 1: stores.store_id
                f"""
                    SELECT 
                        o.user_id,
                        s.address as store_address,
                        COUNT(o.order_id) as visit_count
                    FROM orders o
                    INNER JOIN stores s ON o.store_id = s.store_id
                    WHERE o.user_id = {user_id}
                      AND s.address IS NOT NULL 
                      AND s.address != ''
                    GROUP BY o.user_id, s.address
                    HAVING visit_count > 0
                    ORDER BY visit_count DESC
                """,
                # Case 2: stores.id
                f"""
                    SELECT 
                        o.user_id,
                        s.address as store_address,
                        COUNT(o.order_id) as visit_count
                    FROM orders o
                    INNER JOIN stores s ON o.store_id = s.id
                    WHERE o.user_id = {user_id}
                      AND s.address IS NOT NULL 
                      AND s.address != ''
                    GROUP BY o.user_id, s.address
                    HAVING visit_count > 0
                    ORDER BY visit_count DESC
                """
            ]
            
            df = None
            for i, query in enumerate(queries, 1):
                try:
                    df = pd.read_sql(query, engine)
                    print(f"사용자 방문 데이터 쿼리 패턴 {i} 성공!")
                    break
                except Exception as e:
                    print(f"사용자 방문 데이터 쿼리 패턴 {i} 실패: {str(e)[:100]}")
                    continue
            
            if df is None or df.empty:
                print(f"사용자 {user_id}의 방문 데이터가 없습니다.")
                return []
            
            result = df.to_dict('records')
            # user_id와 visit_count를 적절한 타입으로 변환
            for record in result:
                record['user_id'] = str(record['user_id'])
                record['visit_count'] = int(record['visit_count'])
            
            print(f"DB에서 사용자 {user_id}의 방문 데이터 {len(result)}개 조회 완료")
            return result
            
        except Exception as e:
            print(f"사용자 방문 데이터 조회 실패: {e}")
            return []
    
    def _get_db_engine(self):
        """SQLAlchemy 엔진 생성 (lazy loading)"""
        if self.db_engine is None:
            try:
                self.db_engine = create_engine(get_database_url(), pool_pre_ping=True)
                print("MySQL 연결 성공")
            except Exception as e:
                print(f"MySQL 연결 실패: {e}")
                self.db_engine = None
        return self.db_engine
    
    def _fetch_visit_data_from_db(self) -> List[Dict]:
        """
        MySQL DB에서 직접 모든 사용자 방문 데이터 조회
        
        Returns:
            [{"user_id": "1", "store_address": "주소", "visit_count": 5}, ...]
        """
        engine = self._get_db_engine()
        if engine is None:
            print("DB 연결 실패로 MySQL 데이터를 가져올 수 없습니다.")
            return []
        
        try:
            print(f"MySQL 쿼리 실행 중...")
            
            # stores 테이블의 기본키가 store_id인지 id인지 확인 후 시도
            queries = [
                # Case 1: stores.store_id (일반적인 경우)
                """
                    SELECT 
                        o.user_id,
                        s.address as store_address,
                        COUNT(o.order_id) as visit_count
                    FROM orders o
                    INNER JOIN stores s ON o.store_id = s.store_id
                    WHERE s.address IS NOT NULL 
                      AND s.address != ''
                    GROUP BY o.user_id, s.address
                    HAVING visit_count > 0
                    ORDER BY o.user_id, visit_count DESC
                """,
                # Case 2: stores.id (대안)
                """
                    SELECT 
                        o.user_id,
                        s.address as store_address,
                        COUNT(o.order_id) as visit_count
                    FROM orders o
                    INNER JOIN stores s ON o.store_id = s.id
                    WHERE s.address IS NOT NULL 
                      AND s.address != ''
                    GROUP BY o.user_id, s.address
                    HAVING visit_count > 0
                    ORDER BY o.user_id, visit_count DESC
                """
            ]
            
            df = None
            last_error = None
            
            # 두 가지 쿼리를 순서대로 시도
            for i, query in enumerate(queries, 1):
                try:
                    df = pd.read_sql(query, engine)
                    print(f"쿼리 패턴 {i} 성공!")
                    break
                except Exception as e:
                    last_error = e
                    print(f"쿼리 패턴 {i} 실패: {str(e)[:100]}")
                    continue
            
            if df is None:
                raise last_error if last_error else Exception("모든 쿼리 패턴 실패")
            
            if df.empty:
                print("MySQL에서 조회된 데이터가 없습니다.")
                return []
            
            # Dict 리스트로 변환
            visit_data = df.to_dict('records')
            
            # user_id를 문자열로 변환
            for record in visit_data:
                record['user_id'] = str(record['user_id'])
                record['visit_count'] = int(record['visit_count'])
            
            print(f"MySQL에서 방문 데이터 조회 완료: {len(visit_data)}개 레코드")
            print(f"  사용자 수: {len(df['user_id'].unique())}명")
            
            # 샘플 데이터 출력 (디버깅용)
            if len(visit_data) > 0:
                print(f"  샘플 데이터: {visit_data[0]}")
            
            return visit_data
            
        except Exception as e:
            print(f"MySQL 데이터 조회 실패: {e}")
            return []
    
    def _ensure_data_loaded(self):
        """데이터가 로드되었는지 확인하고, 안되어 있으면 로드"""
        if self.stores_df is None and not self._is_loading:
            self._is_loading = True
            try:
                self.stores_df = self._load_stores_from_excel()
                print(f"가게 데이터 로드 완료: {len(self.stores_df)}개 가게")
                
                # 성능 향상: 주소 인덱스 생성 (O(1) 검색)
                if not hasattr(self, '_address_index'):
                    self._address_index = {}
                    for idx, row in self.stores_df.iterrows():
                        address = str(row['address']).strip()
                        if address not in self._address_index:
                            self._address_index[address] = row.to_dict()
                    print(f"주소 인덱스 생성: {len(self._address_index)}개 주소")
                    
            except Exception as e:
                print(f"데이터 로드 실패: {e}")
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
                self._address_index = {}
            finally:
                self._is_loading = False
    
    def _train_cf_model(self, visit_data: List[Dict]):
        """
        협업 필터링 모델 훈련
        Args:
            visit_data: Spring Boot에서 전달받은 현재 사용자의 방문 데이터
        """
        try:
            # Spring Boot 데이터 확인
            current_user_id = None
            if visit_data and len(visit_data) > 0:
                current_user_id = visit_data[0].get("user_id")
                print(f"현재 사용자: {current_user_id}, 방문 기록: {len(visit_data)}개")
            else:
                print("Spring Boot에서 현재 사용자 방문 데이터가 비어있습니다.")
            
            # Spring Boot 데이터만 사용 (MySQL 조회 생략하여 속도 향상)
            print(f"Spring Boot 데이터만 사용합니다 (빠른 응답을 위해 MySQL 조회 생략)")
            all_visit_data = []
            
            # Spring Boot의 현재 사용자 데이터 사용
            for visit in visit_data:
                all_visit_data.append(visit)
            
            # 사용자 수 확인
            unique_users = set(v.get("user_id") for v in all_visit_data if v.get("user_id"))
            print(f"전체 데이터: {len(unique_users)}명 사용자, {len(all_visit_data)}개 레코드")
            
            if len(unique_users) < 2:
                print(f"사용자가 {len(unique_users)}명뿐입니다. 인기 기반 추천으로 대체합니다.")
                # 사용자가 적어도 방문 데이터가 있으면 모델 훈련 시도
                if len(all_visit_data) > 0:
                    pass  # 계속 진행 (인기 기반 추천 사용)
                else:
                    return False
            
            # all_visit_data를 사용하여 모델 훈련
            visit_data = all_visit_data
            
            # 주소로 가게 찾아서 store_id 생성
            formatted_visit_data = []
            for visit in visit_data:
                # 주소로 가게 찾기
                store_address = visit.get("store_address")
                store_id = visit.get("store_id")
                
                if store_address:
                    # 주소로 가게 찾기
                    store = self._get_store_by_address(store_address)
                    if store:
                        formatted_visit_data.append({
                            "user_id": visit["user_id"],
                            "store_id": store["store_id"],
                            "visit_count": visit["visit_count"]
                        })
                    else:
                        # 주소를 찾을 수 없으면 스킵 (출력은 하지 않음, 너무 많을 수 있음)
                        pass
                elif store_id:
                    # store_id로 변환
                    formatted_visit_data.append({
                        "user_id": visit["user_id"],
                        "store_id": f"store{int(store_id):04d}",
                        "visit_count": visit["visit_count"]
                    })
            
            if not formatted_visit_data:
                print("협업 필터링: 유효한 방문 데이터가 없습니다.")
                return False
            
            # 모델 훈련
            self.cf_model.train(formatted_visit_data, n_neighbors=10)
            
            # 모델 통계 출력
            stats = self.cf_model.get_model_stats()
            print(f"협업 필터링 모델 훈련 완료: {stats}")
            return True
            
        except Exception as e:
            print(f"협업 필터링 모델 훈련 실패: {e}")
            return False
    
    def _load_stores_from_excel(self) -> pd.DataFrame:
        try:
            # ai_data 폴더에서 파일 찾기
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.join(current_dir, "..")
            
            # XLSX 파일 로드
            excel_path = os.path.join(project_root, "ai_data", "마포구_전체_가게_위경도.xlsx")
            if not os.path.exists(excel_path):
                excel_path = os.path.join(project_root, "ai_data", "마포구_전체_가게.xlsx")
            
            print(f"XLSX 파일 로드 시도: {excel_path}")
            df = pd.read_excel(excel_path)
            # 필요한 컬럼만 선택 및 이름 변경
            # 업소명 → name, 도로명(수정) → address, 업태명 → category
            df = df.rename(columns={
                '업소명': 'name',
                '도로명(수정)': 'address',  # 도로명(수정) 컬럼 사용
                '업태명': 'category',
                '위도': 'latitude',
                '경도': 'longitude'
            })
            
            # 위도/경도가 있는 행만 사용
            if 'latitude' in df.columns and 'longitude' in df.columns:
                df = df[df['latitude'].notna() & df['longitude'].notna()]
            
            # 인덱스 재설정 (0부터 다시 시작)
            df = df.reset_index(drop=True)
            
            # store_id 생성 (1부터 시작, Spring Boot DB와 동기화)
            df['store_id'] = df.index.map(lambda x: f"store{x+1:04d}")
            
            # 기본 rating과 review_count 추가 (실제로는 DB에서 가져와야 함)
            if 'rating' not in df.columns:
                df['rating'] = 4.0 + (df.index % 10) / 10  # 4.0 ~ 4.9 랜덤
            if 'review_count' not in df.columns:
                df['review_count'] = 50 + (df.index % 20) * 10  # 50 ~ 240
            
            return df
            
        except Exception as e:
            print(f"xlsx 파일 로드 실패: {str(e)}")
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
    
    def _get_store_by_address(self, store_address: str) -> Dict:
        """주소로 가게 정보 조회 (인덱스 사용으로 O(1) 성능)"""
        self._ensure_data_loaded()  # 데이터 로드 확인
        
        # 1. 인덱스에서 정확한 주소 검색 (O(1))
        address_key = str(store_address).strip()
        if hasattr(self, '_address_index') and address_key in self._address_index:
            return self._address_index[address_key]
        
        # 2. 인덱스 없으면 기존 방식 (fallback)
        store_row = self.stores_df[self.stores_df['address'] == store_address]
        
        if len(store_row) == 0:
            store_row = self.stores_df[self.stores_df['address'].str.strip() == store_address.strip()]
        
        if len(store_row) == 0:
            return None
            
        return store_row.iloc[0].to_dict()
    
    def _get_store(self, store_id: str = None, store_address: str = None) -> Dict:
        """가게 정보 조회 (store_address 우선, 없으면 store_id 사용)"""
        # store_address가 있으면 주소로 찾기
        if store_address:
            store = self._get_store_by_address(store_address)
            if store:
                return store
        
        # store_address가 없거나 못 찾았으면 store_id로 찾기
        if store_id:
            xlsx_store_id = f"store{int(store_id):04d}"
            return self._get_store_by_id(xlsx_store_id)
        
        return None
    
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
    
    def recommend_event_stores(self, user_lat: float, user_lon: float, event_stores_data: List[Dict]) -> List[SimpleStoreInfo]:
        """
        1. 이벤트 참여 가게 추천 (경험치 2배 부여 등)
        - 경험치 배수가 높은 순
        - 거리가 가까운 순
        - 최대 2개
        
        Args:
            user_lat: 사용자 위도
            user_lon: 사용자 경도
            event_stores_data: DB에서 조회한 이벤트 가게 데이터
        """
        candidates = []
        
        for event_data in event_stores_data:
            # 가게 조회 (주소로 찾기)
            store_address = event_data.get("store_address")
            exp_multiplier = event_data.get("exp_multiplier", 1.0)
            
            print(f"이벤트 가게 찾기: address={store_address}")
            store = self._get_store_by_address(store_address)
            if not store:
                print(f"가게를 찾을 수 없음: store_address={store_address}")
                continue
            print(f"가게 찾음: {store['name']} at {store['address']}")
            
            distance = self._calculate_distance(user_lat, user_lon, store)
            print(f"   거리: {distance:.2f}km")
            
            # 점수 = 경험치 배수 * 30 - 거리 * 2 (거리 패널티)
            score = exp_multiplier * 30 - distance * 2
            print(f"   점수: {score:.2f} (경험치 배수: {exp_multiplier})")
            
            reasons = [
                f"경험치 {exp_multiplier}배 이벤트",
                f"거리 {distance:.1f}km"
            ]
            
            store_info = self._create_store_info(store, distance, score, reasons)
            candidates.append(store_info)
        
        # 점수 높은 순으로 정렬
        candidates.sort(key=lambda x: x.recommendation_score, reverse=True)
        
        print(f"이벤트 가게 최종 후보: {len(candidates)}개")
        for i, c in enumerate(candidates[:5]):  # 상위 5개만 출력
            print(f"  {i+1}. {c.name} - 점수: {c.recommendation_score:.2f}, 거리: {c.distance_km:.2f}km")
        
        result = candidates[:2]
        print(f"이벤트 가게 최종 반환: {len(result)}개")
        
        # SimpleStoreInfo로 변환 (name, address만)
        simple_result = [SimpleStoreInfo(name=store.name, address=store.address) for store in result]
        return simple_result
    
    def recommend_new_stores(self, user_lat: float, user_lon: float, new_stores_data: List[Dict]) -> List[SimpleStoreInfo]:
        """
        2. 신규 가입 가게 추천
        - 최근 가입한 순
        - 거리가 가까운 순
        - 최대 2개
        
        Args:
            user_lat: 사용자 위도
            user_lon: 사용자 경도
            new_stores_data: DB에서 조회한 신규 가게 데이터
        """
        current_date = datetime.now()
        candidates = []
        
        print(f"\n 신규 가게 추천 시작: {len(new_stores_data)}개 후보")
        
        for new_data in new_stores_data:
            store_address = new_data.get("store_address")
            joined_date = new_data.get("joined_date")
            
            print(f"신규 가게 찾기: address={store_address}")
            
            # 가게 조회
            store = self._get_store_by_address(store_address)
            if not store:
                print(f"가게를 찾을 수 없음: store_address={store_address}")
                continue
            
            print(f"가게 찾음: {store['name']} at {store['address']}")
            
            distance = self._calculate_distance(user_lat, user_lon, store)
            
            # 가입한 지 며칠 됐는지
            if isinstance(joined_date, str):
                joined_date = datetime.fromisoformat(joined_date.replace('T', ' '))
            days_since_joined = (current_date - joined_date).days
            
            # 점수 = (30 - 가입일수) * 2 - 거리 * 2
            # 최근 가입일수록 높은 점수
            score = max(0, (30 - days_since_joined) * 2) - distance * 2
            
            print(f"   거리: {distance:.2f}km, 가입: {days_since_joined}일 전")
            print(f"   점수: {score:.2f}")
            
            reasons = [
                f"{days_since_joined}일 전 신규 가입",
                f"거리 {distance:.1f}km"
            ]
            
            store_info = self._create_store_info(store, distance, score, reasons)
            candidates.append(store_info)
        
        # 점수 높은 순으로 정렬
        candidates.sort(key=lambda x: x.recommendation_score, reverse=True)
        
        print(f"신규 가게 최종 후보: {len(candidates)}개")
        for i, c in enumerate(candidates[:5]):
            print(f"  {i+1}. {c.name} - 점수: {c.recommendation_score:.2f}, 거리: {c.distance_km:.2f}km")
        
        result = candidates[:2]
        print(f"신규 가게 최종 반환: {len(result)}개\n")
        
        # SimpleStoreInfo로 변환 (name, address만)
        simple_result = [SimpleStoreInfo(name=store.name, address=store.address) for store in result]
        return simple_result
    
    def recommend_popular_stores(self, user_lat: float, user_lon: float, popular_stores_data: List[Dict]) -> List[SimpleStoreInfo]:
        """
        3. 인기 가게 추천 (유저들이 많이 방문한 가게)
        - 방문 횟수가 많은 순
        - 거리가 가까운 순
        - 최대 2개
        
        Args:
            user_lat: 사용자 위도
            user_lon: 사용자 경도
            popular_stores_data: DB에서 조회한 인기 가게 데이터
        """
        candidates = []
        
        print(f"\n 인기 가게 추천 시작: {len(popular_stores_data)}개 후보")
        
        for popular_data in popular_stores_data:
            store_address = popular_data.get("store_address")
            visit_count = popular_data.get("visit_count", 0)
            
            print(f"인기 가게 찾기: address={store_address}")
            
            # 가게 조회
            store = self._get_store_by_address(store_address)
            if not store:
                print(f"가게를 찾을 수 없음: store_address={store_address}")
                continue
            
            print(f"가게 찾음: {store['name']} at {store['address']}")
            
            distance = self._calculate_distance(user_lat, user_lon, store)
            
            # 점수 = 방문횟수 / 10 - 거리 * 2
            score = visit_count / 10 - distance * 2
            
            print(f"   거리: {distance:.2f}km, 방문: {visit_count}회")
            print(f"   점수: {score:.2f}")
            
            reasons = [
                f"방문 {visit_count}회",
                f"거리 {distance:.1f}km",
                "인기 많은 가게"
            ]
            
            store_info = self._create_store_info(store, distance, score, reasons)
            candidates.append(store_info)
        
        # 점수 높은 순으로 정렬
        candidates.sort(key=lambda x: x.recommendation_score, reverse=True)
        
        print(f"인기 가게 최종 후보: {len(candidates)}개")
        for i, c in enumerate(candidates[:5]):
            print(f"  {i+1}. {c.name} - 점수: {c.recommendation_score:.2f}, 거리: {c.distance_km:.2f}km")
        
        result = candidates[:2]
        print(f"인기 가게 최종 반환: {len(result)}개\n")
        
        # SimpleStoreInfo로 변환 (name, address만)
        simple_result = [SimpleStoreInfo(name=store.name, address=store.address) for store in result]
        return simple_result
    
    def recommend_nearby_stores(self, user_lat: float, user_lon: float, recommended_addresses: set) -> List[SimpleStoreInfo]:
        """
        4. 가까운 가게 추천
        - 거리가 가까운 순
        - 평점이 높은 순
        - 최대 2개
        
        Args:
            user_lat: 사용자 위도
            user_lon: 사용자 경도
            recommended_addresses: 이미 추천된 가게 주소들 (중복 제거용)
        """
        self._ensure_data_loaded()  # 데이터 로드 확인
        
        candidates = []
        
        # DataFrame에서 반복
        for idx, store in self.stores_df.iterrows():
            # 이미 추천된 가게는 제외 (주소로 중복 체크)
            if store.get("address") in recommended_addresses:
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
        
        result = candidates[:2]
        
        # SimpleStoreInfo로 변환 (name, address만)
        simple_result = [SimpleStoreInfo(name=store.name, address=store.address) for store in result]
        return simple_result
    
    def recommend_cf_stores(self, user_id: str, user_lat: float, user_lon: float, user_visit_data: List[Dict]) -> List[SimpleStoreInfo]:
        """
        5. 협업 필터링 기반 추천 (AI 모델 사용)
        - 비슷한 취향의 사용자들이 방문한 가게 추천
        - KNN 알고리즘으로 유사 사용자 찾기
        - 최대 2개
        
        Args:
            user_id: 사용자 ID
            user_lat: 사용자 위도
            user_lon: 사용자 경도
            user_visit_data: DB에서 조회한 사용자 방문 데이터
        """
        self._ensure_data_loaded()  # 데이터 로드 확인
        
        # DB에서 조회한 방문 데이터로 모델 훈련
        if user_visit_data and len(user_visit_data) > 0:
            is_trained = self._train_cf_model(user_visit_data)
            
            if not is_trained:
                print("협업 필터링 모델 훈련 실패. AI 추천을 건너뜁니다.")
                return []
        else:
            print("방문 데이터가 없습니다. AI 추천을 건너뜁니다.")
            return []
        
        #  AI 추천은 1순위이므로 중복 체크 없이 순수하게 추천!
        # 다른 카테고리들이 AI 추천을 피해가도록 수정됨
        
        # 협업 필터링으로 가게 추천
        cf_recommendations = self.cf_model.recommend_stores(
            user_id=user_id,
            n_recommendations=10,
            exclude_visited=True
        )
        
        print(f"\n 협업 필터링 결과: {len(cf_recommendations)}개 후보")
        
        candidates = []
        
        for store_id, predicted_score in cf_recommendations:
            print(f"AI 추천 가게 찾기: store_id={store_id}, 예측 점수={predicted_score:.2f}")
            # 가게 정보 조회
            store = self._get_store_by_id(store_id)
            if not store:
                print(f"   가게를 찾을 수 없음: {store_id}")
                continue
            
            print(f"   가게 찾음: {store['name']} at {store.get('address', 'N/A')}")
            
            store_dict = store
            distance = self._calculate_distance(user_lat, user_lon, store_dict)
            
            print(f"   거리: {distance:.2f}km")
            
            # 거리가 너무 멀면 제외 (10km 이내)
            if distance > 10.0:
                print(f"   거리가 너무 멀어서 제외 (10km 이상)")
                continue
            
            # 점수 = 협업 필터링 예측 점수 * 10 - 거리 * 1
            score = predicted_score * 10 - distance * 1
            
            print(f"   점수: {score:.2f}")
            
            reasons = [
                "AI가 당신의 취향을 분석해 추천",
                f"유사한 사용자들이 좋아함 (예측 점수: {predicted_score:.2f})",
                f"거리 {distance:.1f}km"
            ]
            
            store_info = self._create_store_info(store_dict, distance, score, reasons)
            candidates.append(store_info)
            
            # 충분히 모았으면 중단
            if len(candidates) >= 5:
                break
        
        # 점수 높은 순으로 정렬
        candidates.sort(key=lambda x: x.recommendation_score, reverse=True)
        
        print(f"\n AI 추천 가게 최종 후보: {len(candidates)}개")
        for i, c in enumerate(candidates[:5]):
            print(f"  {i+1}. {c.name} - 점수: {c.recommendation_score:.2f}, 거리: {c.distance_km:.2f}km")
        
        result = candidates[:2]
        print(f"AI 추천 가게 최종 반환: {len(result)}개\n")
        
        # SimpleStoreInfo로 변환 (name, address만)
        simple_result = [SimpleStoreInfo(name=store.name, address=store.address) for store in result]
        return simple_result
    
    def recommend_stores(self, request: RecommendationRequest) -> RecommendationResponse:
        """
        5개 카테고리별로 2개씩 가게 추천
        에러가 발생한 카테고리는 빈 리스트로 반환하여 전체 프로세스 중단 방지
        """
        print("\n" + "="*60)
        print("전체 추천 프로세스 시작")
        print(f"사용자 ID: {request.user_id}, 위치: ({request.location.latitude}, {request.location.longitude})")
        print("="*60)
        
        # Spring Boot가 보낸 데이터 우선 사용
        print("\n[데이터 조회] Spring Boot에서 전달받은 데이터를 확인합니다...")
        
        # 1. 이벤트 가게 - Spring Boot 데이터를 dict 형식으로 변환
        event_stores_data = []
        if request.event_stores:
            for store in request.event_stores:
                event_stores_data.append({
                    "store_address": store.store_address,
                    "exp_multiplier": store.exp_multiplier
                })
        
        # 2. 신규 가게 - Spring Boot 데이터를 dict 형식으로 변환
        new_stores_data = []
        if request.new_stores:
            for store in request.new_stores:
                new_stores_data.append({
                    "store_address": store.store_address,
                    "joined_date": store.joined_date
                })
        
        # 3. 인기 가게 - Spring Boot 데이터를 dict 형식으로 변환
        popular_stores_data = []
        if request.popular_stores:
            for store in request.popular_stores:
                popular_stores_data.append({
                    "store_address": store.store_address,
                    "visit_count": store.visit_count
                })
        
        # 4. 사용자 방문 데이터 - Spring Boot 데이터를 dict 형식으로 변환
        user_visit_data = []
        if request.visit_statics:
            for visit in request.visit_statics:
                user_visit_data.append({
                    "user_id": visit.user_id,
                    "store_address": visit.store_address,
                    "visit_count": visit.visit_count
                })
        
        print(f"Spring Boot 데이터: 이벤트 {len(event_stores_data)}개, 신규 {len(new_stores_data)}개, "
              f"인기 {len(popular_stores_data)}개, 방문 기록 {len(user_visit_data)}개")
        
        recommendations = []
        
        user_lat = request.location.latitude
        user_lon = request.location.longitude
        
        # 1. AI 추천 가게 (협업 필터링)  우선순위 1순위!
        try:
            print("\n[1/5] AI 추천 가게 (협업 필터링) 중...")
            cf_stores = self.recommend_cf_stores(
                user_id=request.user_id,
                user_lat=user_lat,
                user_lon=user_lon,
                user_visit_data=user_visit_data
            )
            print(f"AI 추천 가게 {len(cf_stores)}개 추천 완료")
        except Exception as e:
            print(f"AI 추천 가게 추천 실패: {str(e)}")
            cf_stores = []
        recommendations.append(CategoryRecommendation(
            category="AI 추천 가게",
            stores=cf_stores
        ))
        
        # AI가 추천한 가게 주소들 (다른 카테고리에서 중복 제거용)
        ai_recommended_addresses = set(store.address for store in cf_stores)
        print(f"AI 추천 가게 {len(ai_recommended_addresses)}개 주소 보호")
        
        # 2. 이벤트 참여 가게
        try:
            print("\n[2/5] 이벤트 참여 가게 추천 중...")
            event_stores_raw = self.recommend_event_stores(
                user_lat=user_lat,
                user_lon=user_lon,
                event_stores_data=event_stores_data
            )
            # AI 추천과 중복 제거
            event_stores = [s for s in event_stores_raw if s.address not in ai_recommended_addresses]
            if len(event_stores_raw) > len(event_stores):
                print(f"   AI 추천과 중복되는 {len(event_stores_raw) - len(event_stores)}개 가게 제외")
            print(f"이벤트 가게 {len(event_stores)}개 추천 완료")
        except Exception as e:
            print(f"이벤트 가게 추천 실패: {str(e)}")
            event_stores = []
        recommendations.append(CategoryRecommendation(
            category="이벤트 참여 가게",
            stores=event_stores
        ))
        
        # 3. 신규 가입 가게
        try:
            print("\n[3/5] 신규 가입 가게 추천 중...")
            new_stores_raw = self.recommend_new_stores(
                user_lat=user_lat,
                user_lon=user_lon,
                new_stores_data=new_stores_data
            )
            # AI 추천과 중복 제거
            new_stores = [s for s in new_stores_raw if s.address not in ai_recommended_addresses]
            if len(new_stores_raw) > len(new_stores):
                print(f"   AI 추천과 중복되는 {len(new_stores_raw) - len(new_stores)}개 가게 제외")
            print(f"신규 가게 {len(new_stores)}개 추천 완료")
        except Exception as e:
            print(f"신규 가게 추천 실패: {str(e)}")
            new_stores = []
        recommendations.append(CategoryRecommendation(
            category="신규 가입 가게",
            stores=new_stores
        ))
        
        # 4. 인기 가게
        try:
            print("\n[4/5] 인기 가게 추천 중...")
            popular_stores_raw = self.recommend_popular_stores(
                user_lat=user_lat,
                user_lon=user_lon,
                popular_stores_data=popular_stores_data
            )
            # AI 추천과 중복 제거
            popular_stores = [s for s in popular_stores_raw if s.address not in ai_recommended_addresses]
            if len(popular_stores_raw) > len(popular_stores):
                print(f"   AI 추천과 중복되는 {len(popular_stores_raw) - len(popular_stores)}개 가게 제외")
            print(f"인기 가게 {len(popular_stores)}개 추천 완료")
        except Exception as e:
            print(f"인기 가게 추천 실패: {str(e)}")
            popular_stores = []
        recommendations.append(CategoryRecommendation(
            category="인기 가게",
            stores=popular_stores
        ))
        
        # 이미 추천된 가게 주소들 모으기 (가까운 가게에서 제외하기 위해)
        all_recommended_addresses = ai_recommended_addresses.copy()
        for store in event_stores:
            all_recommended_addresses.add(store.address)
        for store in new_stores:
            all_recommended_addresses.add(store.address)
        for store in popular_stores:
            all_recommended_addresses.add(store.address)
        
        # 5. 가까운 가게
        try:
            print("\n[5/5] 가까운 가게 추천 중...")
            nearby_stores_raw = self.recommend_nearby_stores(
                user_lat=user_lat,
                user_lon=user_lon,
                recommended_addresses=all_recommended_addresses
            )
            # AI 추천과 중복 제거
            nearby_stores = [s for s in nearby_stores_raw if s.address not in ai_recommended_addresses]
            if len(nearby_stores_raw) > len(nearby_stores):
                print(f"   AI 추천과 중복되는 {len(nearby_stores_raw) - len(nearby_stores)}개 가게 제외")
            print(f"가까운 가게 {len(nearby_stores)}개 추천 완료")
        except Exception as e:
            print(f"가까운 가게 추천 실패: {str(e)}")
            nearby_stores = []
        recommendations.append(CategoryRecommendation(
            category="가까운 가게",
            stores=nearby_stores
        ))
        
        # 전체 통계
        total_stores = sum(len(cat.stores) for cat in recommendations)
        print("\n" + "="*60)
        print(f"전체 추천 완료: 총 {total_stores}개 가게")
        print("="*60)
        print("카테고리별 추천 결과:")
        for cat in recommendations:
            print(f"  • {cat.category}: {len(cat.stores)}개")
        print("="*60 + "\n")
        
        return RecommendationResponse(
            success=True,
            user_id=request.user_id,
            recommendations=recommendations
        )
