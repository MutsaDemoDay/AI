"""
FastAPI 메인 애플리케이션
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models.request import RecommendationRequest
from app.models.response import RecommendationResponse
from app.services.recommendation import RecommendationService
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="Stamp AI - 가게 추천 시스템",
    description="스탬프 앱을 위한 AI 기반 가게 추천 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 설정 (스프링 백엔드와 통신을 위해)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 운영 환경에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 추천 서비스 인스턴스
recommendation_service = RecommendationService()


@app.get("/")
async def root():
    """
    루트 엔드포인트
    """
    return {
        "message": "Stamp AI - 가게 추천 시스템 API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """
    헬스 체크 엔드포인트
    """
    return {
        "status": "healthy",
        "service": "stamp-ai"
    }


@app.post("/api/v1/recommendations", response_model=RecommendationResponse)
async def get_recommendations(request: RecommendationRequest):
    try:
        logger.info(f"카테고리별 추천 요청 수신: user_id={request.user_id}, "
                   f"location=({request.location.latitude}, {request.location.longitude})")
        logger.info(f"이벤트 가게: {len(request.event_stores)}개, "
                   f"신규 가게: {len(request.new_stores)}개, "
                   f"인기 가게: {len(request.popular_stores)}개")
        
        # 추천 서비스 호출
        response = recommendation_service.recommend_stores(request)
        
        total_stores = sum(len(cat.stores) for cat in response.recommendations)
        logger.info(f"추천 완료: 총 {total_stores}개 가게 반환")
        
        return response
    
    except Exception as e:
        logger.error(f"추천 중 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")




if __name__ == "__main__":
    import uvicorn
    
    # 서버 실행
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

