# 회계감사 JET(Journal Entry Testing) 자동화 프로그램

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)

## 📋 프로젝트 개요
회계감사 절차 중 저널 엔트리 테스트(JET)를 자동화하는 Streamlit 웹 애플리케이션입니다.

## 🌐 라이브 데모
👉 **[JET 자동화 프로그램 체험하기](https://jet-automation.streamlit.app)**


## 🚀 주요 기능

### 필수 시나리오 (Essential)
- **A01: 데이터 유효성 검증** - 데이터 무결성 및 레코드 이해 절차
- **A02: 전표 차대평형 검증** - 전표번호별 차변금액과 대변금액 일치 검증
- **A03: 시산표 Roll-forward 검증** - 전표데이터 기반 시산표 재구성으로 완전성 검증

### 선택 시나리오 (Optional)
- **B01: 손익계정 중요성금액 분석** - 손익계정별 중요성금액 기준 분석
- **B02: 비정상 계정 사용 검사** - CoA 기준 비정상적인 계정 사용 전표 확인
- **B03: 신규 생성 계정과목 검사** - 신규 생성 계정과목 사용 전표 추출
- **B04: 저빈도 사용 계정 검사** - 저빈도 사용 계정 포함 전표 적정성 확인
- **B05: 비정상 사용자 검사** - 인사정보 외 사용자 작성 전표 확인
- **B06: 권한 없는 사용자 검사** - 전표입력권한 없는 사용자 전표 확인
- **B07: 기표일 이후 입력 전표 분석** - 기표일/입력일 비교로 결산일 이후 입력 전표 추출
- **B08: 입력자-승인자 동일 검사** - 입력자와 승인자 동일 전표 추출
- **B09: 비정상 계정 조합 검사** - 비정상적인 계정 조합 전표 추출

## 📊 데이터 구조

### 시산표 (Trial Balance)
- **컬럼**: `계정코드`, `계정과목`, `차변잔액`, `대변잔액`
- **형식**: CSV (cp949 인코딩) 또는 XLSX

### 분개장 (Journal Entries)
- **컬럼**: `전표일자`, `전표번호`, `계정코드`, `계정과목`, `차변금액`, `대변금액`, `거래처코드`, `입력사원`
- **형식**: CSV (cp949 인코딩) 또는 XLSX

## 🛠️ 설치 및 실행

### 1. 환경 설정
```bash
# Python 가상환경 생성 (권장)
python -m venv venv

# 가상환경 활성화
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 필요한 패키지 설치
pip install -r requirements.txt
```

### 2. 프로그램 실행
```bash
streamlit run jet_automation.py
```

### 3. 웹 브라우저 접속
프로그램이 실행되면 자동으로 웹 브라우저가 열리며, 수동으로 접속할 경우:
```
http://localhost:8501
```

## 📈 사용 방법

### 1. 파일 업로드
- 사이드바에서 필요한 파일들을 업로드합니다:
  - **전기 시산표** (선택사항)
  - **분개장** (필수)
  - **당기 시산표** (Roll-forward 테스트용, 선택사항)

### 2. 시나리오 선택
- **필수 시나리오**: 기본적으로 선택되어 있음
- **선택 시나리오**: 필요에 따라 체크박스로 선택

### 3. 분석 파라미터 설정
- **중요성금액 기준**: B01 시나리오용
- **저빈도 기준**: B04 시나리오용 (사용횟수)
- **회계연도 종료일**: B07 시나리오용

### 4. 결과 확인
- 각 시나리오별로 expandable 섹션에서 결과 확인
- 문제 발견 시 상세 데이터 테이블 제공

## 🔍 핵심 알고리즘

### Roll-Forward 검증 공식
```
기말잔액 = 기초잔액 + 당기증가액 - 당기감소액
```

### 차대평형 검증
```
전표별 차변금액 합계 = 전표별 대변금액 합계
```

## ⚠️ 주의사항

1. **파일 인코딩**: CSV 파일은 cp949 인코딩을 사용해주세요
2. **컬럼명**: 정확한 컬럼명 사용이 필요합니다
3. **데이터 형식**: 금액 데이터는 숫자 형식이어야 합니다
4. **메모리 사용량**: 대용량 파일 처리 시 충분한 메모리가 필요합니다

## 🎯 출력 형식

- ✅ **성공**: 문제가 발견되지 않은 경우
- ⚠️ **경고**: 검토가 필요한 항목이 발견된 경우
- ❌ **오류**: 시스템 오류 또는 데이터 형식 문제

## 🔧 기술 스택

- **Python 3.8+**
- **Streamlit**: 웹 애플리케이션 프레임워크
- **Pandas**: 데이터 처리 및 분석
- **NumPy**: 수치 계산
- **OpenPyXL**: Excel 파일 처리
