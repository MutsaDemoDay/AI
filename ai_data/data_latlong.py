import pandas as pd
import requests
import time
import os
import re


def clean_address(address):
    """
    주소를 정리하여 geocoding이 잘 되도록 함
    """
    if pd.isna(address):
        return None
    
    # 괄호와 괄호 안의 내용 제거 (건물명, 호수 등)
    address = re.sub(r'\([^)]*\)', '', address)
    
    # 여러 공백을 하나로 
    address = re.sub(r'\s+', ' ', address)
    
    # 앞뒤 공백 제거
    address = address.strip()
    
    return address


def get_coordinates(address, api_key):
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {api_key}"}
    params = {"query": address}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            result = response.json()
            if result['documents']:
                x = result['documents'][0]['x']  # 경도
                y = result['documents'][0]['y']  # 위도
                return float(y), float(x), None
        elif response.status_code == 401:
            return None, None, "API 키 오류 (401)"
        elif response.status_code == 403:
            return None, None, "권한 없음 (403)"
        else:
            return None, None, f"HTTP {response.status_code}"
        
        return None, None, "주소를 찾을 수 없음"
    except Exception as e:
        return None, None, f"오류: {str(e)}"


def add_latlong_columns(api_key):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(current_dir, "마포구_전체_가게.xlsx")
    output_file = os.path.join(current_dir, "마포구_전체_가게_위경도.xlsx")
    
    # 파일 읽기
    print("파일 읽는 중...")
    df = pd.read_excel(input_file)
    print(f"총 {len(df)}개 가게")
    print(f"컬럼: {list(df.columns)}")
    
    # 위도/경도 컬럼 추가
    df['위도'] = None
    df['경도'] = None
    
    # 주소 컬럼 찾기 (소재지, 소재지(도로명), 주소 등)
    address_column = None
    for col in df.columns:
        if '소재지' in col or '주소' in col:
            address_column = col
            break
    
    if address_column is None:
        print("주소 컬럼을 찾을 수 없습니다.")
        return
    
    print(f"\n주소 컬럼: {address_column}")
    print("위도/경도 변환 중...\n")
    
    # 각 주소를 위경도로 변환
    success_count = 0
    fail_count = 0
    error_messages = {}
    
    for idx, row in df.iterrows():
        address = row[address_column]
        
        if pd.isna(address):
            fail_count += 1
            continue
        
        # 주소 정리
        clean_addr = clean_address(address)
        
        lat, lon, error = get_coordinates(clean_addr, api_key)
        
        if lat and lon:
            df.at[idx, '위도'] = lat
            df.at[idx, '경도'] = lon
            success_count += 1
            print(f"[{idx+1}/{len(df)}] ✓ {clean_addr[:40]}")
        else:
            fail_count += 1
            print(f"[{idx+1}/{len(df)}] ✗ {clean_addr[:40]} → {error}")
            if error not in error_messages:
                error_messages[error] = 0
            error_messages[error] += 1
            
            # 첫 번째 실패 시 상세 정보 출력
            if fail_count == 1:
                print(f"\n[디버깅] 첫 번째 실패 상세:")
                print(f"  원본 주소: {address}")
                print(f"  정리된 주소: {clean_addr}")
                print(f"  오류: {error}")
        
        # API 호출 제한 방지 (0.1초 대기)
        time.sleep(0.1)
        
        # 처음 3개만 테스트
        if idx >= 2:
            print(f"\n[테스트 모드] 처음 3개만 처리했습니다.")
            print("전체 처리하려면 73번째 줄의 break를 삭제하세요.")
            break
    
    # 결과 저장
    print(f"\n파일 저장 중: {output_file}")
    df.to_excel(output_file, index=False)
    
    print("\n완료!")
    print(f"  성공: {success_count}개")
    print(f"  실패: {fail_count}개")
    
    if error_messages:
        print("\n[오류 유형별 통계]")
        for error, count in error_messages.items():
            print(f"  {error}: {count}개")
    
    print(f"\n저장 위치: {output_file}")


if __name__ == "__main__":
    # Kakao REST API 키 입력
    api_key = input("API 키 입력: ").strip()
    
    if not api_key:
        print("API 키를 입력해주세요.")
    else:
        add_latlong_columns(api_key)

