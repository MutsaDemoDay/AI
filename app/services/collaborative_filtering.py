"""
협업 필터링(Collaborative Filtering) 기반 추천 시스템

User-based Collaborative Filtering:
- 비슷한 취향의 사용자들이 방문한 가게를 추천
- KNN 알고리즘으로 유사 사용자 찾기
- Cosine Similarity로 유사도 계산
"""
from typing import List, Dict, Tuple
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics.pairwise import cosine_similarity


class CollaborativeFilteringModel:
    """협업 필터링 모델"""
    
    def __init__(self):
        """초기화"""
        self.user_item_matrix = None
        self.user_ids = []
        self.store_ids = []
        self.model = None
        self.is_trained = False
        
    def create_user_item_matrix(self, visit_data: List[Dict]) -> pd.DataFrame:
        """
        사용자-가게 방문 행렬 생성
        
        Args:
            visit_data: [{"user_id": "user1", "store_id": "store0001", "visit_count": 5}, ...]
            
        Returns:
            user_item_matrix: 행=사용자, 열=가게, 값=방문횟수
        """
        if not visit_data:
            return pd.DataFrame()
        
        # DataFrame으로 변환
        df = pd.DataFrame(visit_data)
        
        # Pivot table 생성 (사용자 x 가게)
        user_item_matrix = df.pivot_table(
            index='user_id',
            columns='store_id',
            values='visit_count',
            fill_value=0
        )
        
        self.user_ids = user_item_matrix.index.tolist()
        self.store_ids = user_item_matrix.columns.tolist()
        
        return user_item_matrix
    
    def train(self, visit_data: List[Dict], n_neighbors: int = 10):
        """
        협업 필터링 모델 훈련
        
        Args:
            visit_data: 사용자-가게 방문 기록
            n_neighbors: 유사 사용자 수 (기본 10명)
        """
        # 1. 사용자-가게 행렬 생성
        self.user_item_matrix = self.create_user_item_matrix(visit_data)
        
        if self.user_item_matrix.empty:
            print("방문 데이터가 없어서 모델을 훈련할 수 없습니다.")
            return
        
        # 2. KNN 모델 훈련 (Cosine Similarity 사용)
        self.model = NearestNeighbors(
            n_neighbors=min(n_neighbors, len(self.user_ids)),
            metric='cosine',
            algorithm='brute'
        )
        self.model.fit(self.user_item_matrix.values)
        
        self.is_trained = True
        print(f"협업 필터링 모델 훈련 완료: {len(self.user_ids)}명 사용자, {len(self.store_ids)}개 가게")
    
    def get_similar_users(self, user_id: str, n_neighbors: int = 5) -> List[Tuple[str, float]]:
        """
        특정 사용자와 유사한 사용자 찾기
        
        Args:
            user_id: 대상 사용자 ID
            n_neighbors: 찾을 유사 사용자 수
            
        Returns:
            [(user_id, similarity_score), ...] 유사도 높은 순
        """
        if not self.is_trained or user_id not in self.user_ids:
            return []
        
        # 사용자가 1명뿐이면 유사 사용자를 찾을 수 없음
        if len(self.user_ids) <= 1:
            return []
        
        # 사용자 인덱스 찾기
        user_idx = self.user_ids.index(user_id)
        user_vector = self.user_item_matrix.iloc[user_idx].values.reshape(1, -1)
        
        # n_neighbors가 전체 사용자 수를 초과하지 않도록 조정
        # 자기 자신을 제외하므로 +1
        actual_n_neighbors = min(n_neighbors + 1, len(self.user_ids))
        
        # 유사 사용자 찾기
        distances, indices = self.model.kneighbors(user_vector, n_neighbors=actual_n_neighbors)
        
        # 자기 자신 제외
        similar_users = []
        for idx, distance in zip(indices[0][1:], distances[0][1:]):
            similar_user_id = self.user_ids[idx]
            similarity = 1 - distance  # Cosine distance -> similarity
            similar_users.append((similar_user_id, similarity))
        
        return similar_users
    
    def recommend_stores(
        self, 
        user_id: str, 
        n_recommendations: int = 10,
        exclude_visited: bool = True
    ) -> List[Tuple[str, float]]:
        """
        협업 필터링으로 가게 추천
        
        Args:
            user_id: 대상 사용자 ID
            n_recommendations: 추천할 가게 수
            exclude_visited: 이미 방문한 가게 제외 여부
            
        Returns:
            [(store_id, predicted_score), ...] 예측 점수 높은 순
        """
        if not self.is_trained:
            return []
        
        # 사용자가 너무 적으면 협업 필터링 불가능 (최소 2명 필요)
        if len(self.user_ids) < 2:
            print(f"사용자가 {len(self.user_ids)}명뿐이라 협업 필터링이 불가능합니다. 인기 기반 추천으로 대체합니다.")
            return self._recommend_for_new_user(n_recommendations)
        
        # 신규 사용자 처리
        if user_id not in self.user_ids:
            return self._recommend_for_new_user(n_recommendations)
        
        # 1. 유사 사용자 찾기
        similar_users = self.get_similar_users(user_id, n_neighbors=10)
        
        if not similar_users:
            print(f"유사한 사용자를 찾을 수 없습니다. 인기 기반 추천으로 대체합니다.")
            return self._recommend_for_new_user(n_recommendations)
        
        # 2. 유사 사용자들의 방문 가게를 가중 평균
        user_idx = self.user_ids.index(user_id)
        user_visited = self.user_item_matrix.iloc[user_idx]
        
        # 예측 점수 계산
        predicted_scores = np.zeros(len(self.store_ids))
        total_similarity = 0.0
        
        for similar_user_id, similarity in similar_users:
            similar_user_idx = self.user_ids.index(similar_user_id)
            similar_user_visits = self.user_item_matrix.iloc[similar_user_idx].values
            predicted_scores += similarity * similar_user_visits
            total_similarity += similarity
        
        if total_similarity > 0:
            predicted_scores /= total_similarity
        
        # 3. 이미 방문한 가게 제외
        if exclude_visited:
            visited_mask = user_visited.values > 0
            predicted_scores[visited_mask] = -1
        
        # 4. 상위 N개 추천
        top_indices = np.argsort(predicted_scores)[::-1][:n_recommendations]
        
        recommendations = []
        for idx in top_indices:
            if predicted_scores[idx] > 0:  # 점수가 있는 것만
                store_id = self.store_ids[idx]
                score = predicted_scores[idx]
                recommendations.append((store_id, float(score)))
        
        return recommendations
    
    def _recommend_for_new_user(self, n_recommendations: int) -> List[Tuple[str, float]]:
        """
        신규 사용자를 위한 추천 (Cold Start)
        전체 사용자들이 가장 많이 방문한 인기 가게 추천
        
        Args:
            n_recommendations: 추천할 가게 수
            
        Returns:
            [(store_id, popularity_score), ...] 인기 순
        """
        if self.user_item_matrix is None or self.user_item_matrix.empty:
            return []
        
        # 각 가게의 총 방문 횟수 계산
        store_popularity = self.user_item_matrix.sum(axis=0)
        
        # 상위 N개 추천
        top_stores = store_popularity.nlargest(n_recommendations)
        
        recommendations = []
        for store_id, score in top_stores.items():
            if score > 0:
                recommendations.append((store_id, float(score)))
        
        return recommendations
    
    def get_model_stats(self) -> Dict:
        """모델 통계 정보 반환"""
        if not self.is_trained:
            return {
                "is_trained": False,
                "message": "모델이 아직 훈련되지 않았습니다."
            }
        
        # 희소성(sparsity) 계산
        total_cells = len(self.user_ids) * len(self.store_ids)
        non_zero_cells = (self.user_item_matrix.values > 0).sum()
        sparsity = 1 - (non_zero_cells / total_cells)
        
        return {
            "is_trained": True,
            "n_users": len(self.user_ids),
            "n_stores": len(self.store_ids),
            "total_visits": int(self.user_item_matrix.sum().sum()),
            "sparsity": f"{sparsity * 100:.2f}%",
            "avg_visits_per_user": float(self.user_item_matrix.sum(axis=1).mean())
        }

