import streamlit as st
import pandas as pd
import numpy as np
import openpyxl
from io import StringIO
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="회계감사 JET 자동화 프로그램",
    page_icon="📊",
    layout="wide"
)

def load_data_file(uploaded_file):
    """파일 업로드 및 데이터 로딩 함수"""
    try:
        if uploaded_file.name.endswith('.csv'):
            # 파일 포인터를 처음으로 리셋
            uploaded_file.seek(0)
            
            # 다양한 인코딩 시도
            encodings = ['cp949', 'euc-kr', 'utf-8', 'utf-8-sig', 'ansi']
            df = None
            successful_encoding = None
            
            for encoding in encodings:
                try:
                    uploaded_file.seek(0)  # 각 시도마다 파일 포인터 리셋
                    df = pd.read_csv(uploaded_file, encoding=encoding)
                    successful_encoding = encoding
                    # 컬럼이 제대로 파싱되었는지 확인
                    if len(df.columns) > 0 and not df.empty:
                        break
                except (UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError):
                    continue
            
            if df is None or len(df.columns) == 0:
                st.error("CSV 파일을 읽을 수 없습니다. 파일 형식을 확인해주세요.")
                return None
                
            st.success(f"파일이 {successful_encoding} 인코딩으로 성공적으로 로드되었습니다.")
            
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            st.error("지원하지 않는 파일 형식입니다. CSV 또는 Excel 파일을 업로드해주세요.")
            return None
        
        # 빈 DataFrame 체크
        if df.empty:
            st.error("파일이 비어있거나 데이터를 읽을 수 없습니다.")
            return None
        
        # 컬럼명 정리 (오타 수정 및 공백 제거)
        df.columns = df.columns.str.strip().str.replace('차변진액', '차변잔액')
        
        # 계정코드를 문자열로 통일
        if '계정코드' in df.columns:
            df['계정코드'] = df['계정코드'].astype(str).str.strip()
        
        # 숫자형 컬럼 변환 및 결측치 처리
        numeric_columns = ['차변잔액', '대변잔액', '차변금액', '대변금액']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 데이터 로딩 정보 표시
        st.info(f"로드된 데이터: {len(df)}행, {len(df.columns)}열")
        st.write("컬럼명:", list(df.columns))
            
        return df
    except Exception as e:
        st.error(f"파일 로딩 중 오류가 발생했습니다: {str(e)}")
        return None

def validate_trial_balance(df):
    """시산표 데이터 유효성 검증"""
    required_columns = ['계정코드', '계정과목', '차변잔액', '대변잔액']
    
    if not all(col in df.columns for col in required_columns):
        missing_cols = [col for col in required_columns if col not in df.columns]
        st.error(f"시산표에 필수 컬럼이 누락되었습니다: {missing_cols}")
        return False
    
    return True

def validate_journal_entries(df):
    """분개장 데이터 유효성 검증"""
    required_columns = ['전표일자', '전표번호', '계정코드', '계정과목', '차변금액', '대변금액']
    
    if not all(col in df.columns for col in required_columns):
        missing_cols = [col for col in required_columns if col not in df.columns]
        st.error(f"분개장에 필수 컬럼이 누락되었습니다: {missing_cols}")
        return False
    
    return True

def scenario_a01_data_integrity(journal_df):
    """A01: 데이터 유효성 검증 및 레코드 이해 절차"""
    issues = []
    
    # 1. 결측값 검사
    missing_data = journal_df.isnull().sum()
    if missing_data.any():
        issues.append(f"결측값 발견: {missing_data[missing_data > 0].to_dict()}")
    
    # 2. 중복 레코드 검사
    duplicates = journal_df.duplicated().sum()
    if duplicates > 0:
        issues.append(f"중복 레코드 {duplicates}건 발견")
    
    # 3. 데이터 타입 검사
    required_numeric = ['차변금액', '대변금액']
    for col in required_numeric:
        if col in journal_df.columns:
            non_numeric = journal_df[col].apply(lambda x: not isinstance(x, (int, float, np.number))).sum()
            if non_numeric > 0:
                issues.append(f"{col} 컬럼에 숫자가 아닌 값 {non_numeric}건 발견")
    
    # 4. 전표번호 형식 검사
    if '전표번호' in journal_df.columns:
        empty_vouchers = journal_df['전표번호'].isnull().sum()
        if empty_vouchers > 0:
            issues.append(f"전표번호가 누락된 항목 {empty_vouchers}건 발견")
    
    return issues

def scenario_a02_dr_cr_test(journal_df):
    """A02: 전표번호별 차변금액과 대변금액 일치 검증"""
    if '전표번호' not in journal_df.columns:
        return ["전표번호 컬럼이 없어 검증할 수 없습니다."]
    
    # 전표번호별 차변금액과 대변금액 합계 계산
    voucher_summary = journal_df.groupby('전표번호').agg({
        '차변금액': 'sum',
        '대변금액': 'sum'
    }).reset_index()
    
    # 차변과 대변이 일치하지 않는 전표 찾기
    unbalanced = voucher_summary[voucher_summary['차변금액'] != voucher_summary['대변금액']]
    
    if len(unbalanced) == 0:
        return []
    else:
        unbalanced['차이금액'] = unbalanced['차변금액'] - unbalanced['대변금액']
        return unbalanced

def scenario_a03_rollforward_test(prev_tb, journal_df, curr_tb):
    """A03: 전표데이터 기반 시산표 재구성으로 완전성 검증"""
    if not all([prev_tb is not None, journal_df is not None, curr_tb is not None]):
        return None, "필요한 데이터가 모두 업로드되지 않았습니다."
    
    try:
        # 분개장에서 계정코드별 집계
        journal_summary = journal_df.groupby('계정코드').agg({
            '차변금액': 'sum',
            '대변금액': 'sum'
        }).reset_index()
        
        # 전기 시산표 준비
        prev_tb_clean = prev_tb.copy()
        prev_tb_clean['계정코드'] = prev_tb_clean['계정코드'].astype(str).str.strip()
        prev_tb_clean['차변잔액'] = pd.to_numeric(prev_tb_clean['차변잔액'], errors='coerce').fillna(0)
        prev_tb_clean['대변잔액'] = pd.to_numeric(prev_tb_clean['대변잔액'], errors='coerce').fillna(0)
        
        # 당기 시산표 준비
        curr_tb_clean = curr_tb.copy()
        curr_tb_clean['계정코드'] = curr_tb_clean['계정코드'].astype(str).str.strip()
        curr_tb_clean['차변잔액'] = pd.to_numeric(curr_tb_clean['차변잔액'], errors='coerce').fillna(0)
        curr_tb_clean['대변잔액'] = pd.to_numeric(curr_tb_clean['대변잔액'], errors='coerce').fillna(0)
        
        # 분개장 계정코드 정리
        journal_summary['계정코드'] = journal_summary['계정코드'].astype(str).str.strip()
        
        # 전기 시산표와 분개장 합계 병합
        merged = prev_tb_clean.merge(journal_summary, on='계정코드', how='outer', suffixes=('_prev', '_journal'))
        
        # 결측값을 0으로 처리
        for col in ['차변잔액', '대변잔액', '차변금액', '대변금액']:
            if col in merged.columns:
                merged[col] = merged[col].fillna(0)
        
        # 계산된 당기 잔액 구하기
        merged['계산된_차변잔액'] = merged['차변잔액'] + merged['차변금액'] - merged['대변금액']
        merged['계산된_대변잔액'] = merged['대변잔액'] + merged['대변금액'] - merged['차변금액']
        
        # 차변/대변 잔액 조정 (음수인 경우 반대편으로 이동)
        negative_dr_mask = merged['계산된_차변잔액'] < 0
        merged.loc[negative_dr_mask, '계산된_대변잔액'] = merged.loc[negative_dr_mask, '계산된_대변잔액'] + abs(merged.loc[negative_dr_mask, '계산된_차변잔액'])
        merged.loc[negative_dr_mask, '계산된_차변잔액'] = 0
        
        negative_cr_mask = merged['계산된_대변잔액'] < 0
        merged.loc[negative_cr_mask, '계산된_차변잔액'] = merged.loc[negative_cr_mask, '계산된_차변잔액'] + abs(merged.loc[negative_cr_mask, '계산된_대변잔액'])
        merged.loc[negative_cr_mask, '계산된_대변잔액'] = 0
        
        # 당기 시산표와 비교
        comparison = merged.merge(curr_tb_clean, on='계정코드', how='outer', suffixes=('_calc', '_actual'))
        
        # 결측값 처리
        for col in ['계산된_차변잔액', '계산된_대변잔액', '차변잔액_actual', '대변잔액_actual']:
            if col in comparison.columns:
                comparison[col] = comparison[col].fillna(0)
        
        # 차이 계산
        comparison['차변_차이'] = comparison['계산된_차변잔액'] - comparison['차변잔액_actual']
        comparison['대변_차이'] = comparison['계산된_대변잔액'] - comparison['대변잔액_actual']
        
        # 차이가 있는 항목만 필터링 (0.01원 이상 차이)
        differences = comparison[(abs(comparison['차변_차이']) > 0.01) | (abs(comparison['대변_차이']) > 0.01)]
        
        return differences, None
        
    except Exception as e:
        return None, f"Roll-forward 테스트 중 오류 발생: {str(e)}"

def scenario_b01_large_items_test(journal_df, materiality_threshold=1000000):
    """B01: 손익계정별 중요성금액 기준 분석"""
    # 손익계정 코드 패턴 (일반적으로 4로 시작하는 수익, 5로 시작하는 비용)
    pl_accounts = journal_df[journal_df['계정코드'].astype(str).str.startswith(('4', '5'))]
    
    if len(pl_accounts) == 0:
        return pd.DataFrame(), "손익계정이 발견되지 않았습니다."
    
    # 계정별 금액 집계
    pl_summary = pl_accounts.groupby(['계정코드', '계정과목']).agg({
        '차변금액': 'sum',
        '대변금액': 'sum'
    }).reset_index()
    
    pl_summary['순금액'] = pl_summary['차변금액'] - pl_summary['대변금액']
    
    # 중요성금액 기준 초과 항목
    large_items = pl_summary[abs(pl_summary['순금액']) >= materiality_threshold]
    
    return large_items, None

def scenario_b02_unmatched_accounts(journal_df, chart_of_accounts=None):
    """B02: CoA 기준 비정상적인 계정 사용 전표 확인"""
    if chart_of_accounts is None:
        # 기본적인 계정코드 패턴 검사
        account_codes = journal_df['계정코드'].astype(str)
        
        # 일반적이지 않은 패턴 (예: 너무 짧거나 긴 계정코드, 특수문자 포함)
        unusual_patterns = account_codes[
            (account_codes.str.len() < 3) | 
            (account_codes.str.len() > 10) |
            (~account_codes.str.match(r'^[0-9A-Za-z]+$', na=False))
        ]
        
        if len(unusual_patterns) > 0:
            unmatched_entries = journal_df[journal_df['계정코드'].astype(str).isin(unusual_patterns)]
            return unmatched_entries
    
    return pd.DataFrame()

def scenario_b03_new_accounts(journal_df, prev_tb_df):
    """B03: 신규 생성 계정과목 사용 전표 추출"""
    if prev_tb_df is None:
        return pd.DataFrame(), "전기 시산표가 없어 신규 계정을 확인할 수 없습니다."
    
    # 전기 시산표의 계정코드 목록
    prev_accounts = set(prev_tb_df['계정코드'].astype(str))
    
    # 분개장의 계정코드 목록
    current_accounts = set(journal_df['계정코드'].astype(str))
    
    # 신규 생성 계정코드
    new_accounts = current_accounts - prev_accounts
    
    if len(new_accounts) == 0:
        return pd.DataFrame(), None
    
    # 신규 계정을 사용한 전표 추출
    new_account_entries = journal_df[journal_df['계정코드'].astype(str).isin(new_accounts)]
    
    return new_account_entries, None

def scenario_b04_seldom_used_accounts(journal_df, frequency_threshold=5):
    """B04: 저빈도 사용 계정 포함 전표 적정성 확인"""
    # 계정별 사용 빈도 계산
    account_frequency = journal_df['계정코드'].value_counts()
    
    # 저빈도 사용 계정 (threshold 이하)
    seldom_used = account_frequency[account_frequency <= frequency_threshold].index
    
    if len(seldom_used) == 0:
        return pd.DataFrame(), None
    
    # 저빈도 계정을 사용한 전표 추출
    seldom_entries = journal_df[journal_df['계정코드'].isin(seldom_used)]
    
    return seldom_entries, None

def scenario_b05_unusual_user(journal_df, authorized_users=None):
    """B05: 인사정보 외 사용자 작성 전표 확인"""
    if '입력사원' not in journal_df.columns:
        return pd.DataFrame(), "입력사원 컬럼이 없어 분석할 수 없습니다."
    
    # 기본 승인된 사용자 목록 (실제로는 인사 시스템에서 가져와야 함)
    if authorized_users is None:
        # 사용자 패턴 분석으로 일반적이지 않은 사용자 찾기
        user_counts = journal_df['입력사원'].value_counts()
        
        # 매우 적게 사용한 사용자들 (1-2회만 사용)
        unusual_users = user_counts[user_counts <= 2].index
        
        # 시스템 계정으로 보이는 사용자 (예: SYSTEM, ADMIN 등)
        system_pattern_users = journal_df[
            journal_df['입력사원'].astype(str).str.contains('SYSTEM|ADMIN|TEST|AUTO', case=False, na=False)
        ]['입력사원'].unique()
        
        all_unusual = list(unusual_users) + list(system_pattern_users)
    else:
        # 승인된 사용자 목록에 없는 사용자
        all_users = journal_df['입력사원'].unique()
        all_unusual = [user for user in all_users if user not in authorized_users]
    
    if len(all_unusual) == 0:
        return pd.DataFrame(), None
    
    unusual_entries = journal_df[journal_df['입력사원'].isin(all_unusual)]
    
    return unusual_entries, None

def scenario_b06_inappropriate_user(journal_df, user_roles=None):
    """B06: 전표입력권한 없는 사용자 전표 확인"""
    if '입력사원' not in journal_df.columns:
        return pd.DataFrame(), "입력사원 컬럼이 없어 분석할 수 없습니다."
    
    # 실제로는 권한 시스템에서 가져와야 하지만, 여기서는 패턴으로 분석
    if user_roles is None:
        # 일반적으로 입력권한이 없을 것으로 보이는 사용자 패턴
        # 예: 임원, 감사, 외부 등
        inappropriate_patterns = ['CEO', 'CFO', '감사', '외부', 'GUEST', '임원']
        
        inappropriate_users = []
        for pattern in inappropriate_patterns:
            pattern_users = journal_df[
                journal_df['입력사원'].astype(str).str.contains(pattern, case=False, na=False)
            ]['입력사원'].unique()
            inappropriate_users.extend(pattern_users)
    else:
        # 권한이 없는 사용자 목록에서 실제로 입력한 사용자 찾기
        inappropriate_users = [user for user in journal_df['입력사원'].unique() 
                             if user in user_roles and user_roles[user] != 'input_authorized']
    
    if len(inappropriate_users) == 0:
        return pd.DataFrame(), None
    
    inappropriate_entries = journal_df[journal_df['입력사원'].isin(inappropriate_users)]
    
    return inappropriate_entries, None

def scenario_b07_back_dated_entries(journal_df, fiscal_year_end='2023-12-31'):
    """B07: 기표일/입력일 비교로 결산일 이후 입력 전표 추출"""
    # 입력일 컬럼이 있다고 가정하고, 없으면 스킵
    if '입력일자' not in journal_df.columns:
        return pd.DataFrame(), "입력일자 컬럼이 없어 분석할 수 없습니다."
    
    try:
        fiscal_end = pd.to_datetime(fiscal_year_end)
        journal_copy = journal_df.copy()
        journal_copy['전표일자'] = pd.to_datetime(journal_copy['전표일자'])
        journal_copy['입력일자'] = pd.to_datetime(journal_copy['입력일자'])
        
        # 결산일 이전 전표이지만 결산일 이후에 입력된 전표
        back_dated = journal_copy[
            (journal_copy['전표일자'] <= fiscal_end) & 
            (journal_copy['입력일자'] > fiscal_end)
        ]
        
        return back_dated, None
    except Exception as e:
        return pd.DataFrame(), f"날짜 처리 중 오류 발생: {str(e)}"

def scenario_b08_create_approve_same(journal_df):
    """B08: 입력자와 승인자 동일 전표 추출"""
    if '입력사원' not in journal_df.columns or '승인자' not in journal_df.columns:
        return pd.DataFrame(), "입력사원 또는 승인자 컬럼이 없어 분석할 수 없습니다."
    
    # 입력자와 승인자가 동일한 전표
    same_user_entries = journal_df[journal_df['입력사원'] == journal_df['승인자']]
    
    return same_user_entries, None

def scenario_b09_corresponding_accounts(journal_df):
    """B09: 비정상적인 계정 조합 전표 추출"""
    # 전표번호별로 그룹화하여 계정 조합 분석
    voucher_groups = journal_df.groupby('전표번호')
    
    unusual_combinations = []
    
    for voucher_no, group in voucher_groups:
        accounts = group['계정코드'].astype(str).tolist()
        account_names = group['계정과목'].tolist()
        
        # 비정상적인 조합 패턴 검사
        # 1. 현금과 현금 간의 거래 (예: 현금 -> 현금)
        cash_accounts = ['101', '102', '103']  # 일반적인 현금성 자산 계정
        cash_in_voucher = [acc for acc in accounts if acc.startswith(tuple(cash_accounts))]
        
        if len(cash_in_voucher) >= 2:
            unusual_combinations.append({
                '전표번호': voucher_no,
                '문제유형': '현금-현금 거래',
                '관련계정': ', '.join(cash_in_voucher),
                '거래내역': group
            })
        
        # 2. 자산과 부채의 직접적인 상계
        assets = [acc for acc in accounts if acc.startswith(('1', '2'))]  # 자산: 1, 투자자산: 2
        liabilities = [acc for acc in accounts if acc.startswith('3')]  # 부채: 3
        
        if len(assets) > 0 and len(liabilities) > 0 and len(group) == 2:
            # 단순한 자산-부채 직접 상계 (수익/비용 없이)
            revenue_expense = [acc for acc in accounts if acc.startswith(('4', '5'))]
            if len(revenue_expense) == 0:
                unusual_combinations.append({
                    '전표번호': voucher_no,
                    '문제유형': '자산-부채 직접상계',
                    '관련계정': ', '.join(accounts),
                    '거래내역': group
                })
    
    if len(unusual_combinations) == 0:
        return pd.DataFrame(), None
    
    # 결과를 DataFrame으로 변환
    result_df = pd.DataFrame()
    for combo in unusual_combinations:
        combo_df = combo['거래내역'].copy()
        combo_df['문제유형'] = combo['문제유형']
        result_df = pd.concat([result_df, combo_df], ignore_index=True)
    
    return result_df, None

# Streamlit UI
st.title("📊 회계감사 JET(Journal Entry Testing) 자동화 프로그램")
st.markdown("---")

# 사이드바
st.sidebar.header("📁 파일 업로드")

# 파일 업로드
prev_tb_file = st.sidebar.file_uploader("전기 시산표", type=['csv', 'xlsx'], key="prev_tb")
journal_file = st.sidebar.file_uploader("분개장", type=['csv', 'xlsx'], key="journal")
curr_tb_file = st.sidebar.file_uploader("당기 시산표", type=['csv', 'xlsx'], key="curr_tb")

st.sidebar.markdown("---")
st.sidebar.header("🔍 JET 시나리오 선택")

# 필수 시나리오
st.sidebar.subheader("필수 시나리오 (Essential)")
scenario_a01 = st.sidebar.checkbox("A01: 데이터 유효성 검증", value=True)
scenario_a02 = st.sidebar.checkbox("A02: 전표 차대평형 검증", value=True)
scenario_a03 = st.sidebar.checkbox("A03: 시산표 Roll-forward 검증", value=True)

# 선택 시나리오
st.sidebar.subheader("선택 시나리오 (Optional)")
scenario_b01 = st.sidebar.checkbox("B01: 손익계정 중요성금액 분석")
scenario_b02 = st.sidebar.checkbox("B02: 비정상 계정 사용 검사")
scenario_b03 = st.sidebar.checkbox("B03: 신규 생성 계정과목 검사")
scenario_b04 = st.sidebar.checkbox("B04: 저빈도 사용 계정 검사")
scenario_b05 = st.sidebar.checkbox("B05: 비정상 사용자 검사")
scenario_b06 = st.sidebar.checkbox("B06: 권한 없는 사용자 검사")
scenario_b07 = st.sidebar.checkbox("B07: 기표일 이후 입력 전표 분석")
scenario_b08 = st.sidebar.checkbox("B08: 입력자-승인자 동일 검사")
scenario_b09 = st.sidebar.checkbox("B09: 비정상 계정 조합 검사")

# 파라미터 설정
st.sidebar.subheader("분석 파라미터")
if scenario_b01:
    materiality = st.sidebar.number_input("중요성금액 기준", value=1000000, step=100000)

if scenario_b04:
    frequency_threshold = st.sidebar.number_input("저빈도 기준 (사용횟수)", value=5, step=1, min_value=1)

if scenario_b07:
    fiscal_year_end = st.sidebar.date_input("회계연도 종료일", value=pd.to_datetime('2023-12-31'))
    fiscal_year_end = fiscal_year_end.strftime('%Y-%m-%d')

# 메인 영역
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📈 분석 결과")
    
    # 데이터 로딩
    prev_tb_df = load_data_file(prev_tb_file) if prev_tb_file else None
    journal_df = load_data_file(journal_file) if journal_file else None
    curr_tb_df = load_data_file(curr_tb_file) if curr_tb_file else None
    
    if journal_df is not None and validate_journal_entries(journal_df):
        
        # A01: 데이터 유효성 검증
        if scenario_a01:
            with st.expander("🔍 A01: 데이터 유효성 검증 결과", expanded=True):
                with st.spinner("데이터 유효성을 검증하는 중..."):
                    integrity_issues = scenario_a01_data_integrity(journal_df)
                    
                    if not integrity_issues:
                        st.success("✅ 데이터 유효성 검증 통과: 발견된 문제가 없습니다.")
                    else:
                        st.warning("⚠️ 데이터 유효성 문제 발견:")
                        for issue in integrity_issues:
                            st.write(f"- {issue}")
        
        # A02: 전표 차대평형 검증
        if scenario_a02:
            with st.expander("⚖️ A02: 전표 차대평형 검증 결과", expanded=True):
                with st.spinner("전표별 차대평형을 검증하는 중..."):
                    unbalanced_vouchers = scenario_a02_dr_cr_test(journal_df)
                    
                    if isinstance(unbalanced_vouchers, list) and not unbalanced_vouchers:
                        st.success("✅ 전표 차대평형 검증 통과: 모든 전표의 차변과 대변이 일치합니다.")
                    elif isinstance(unbalanced_vouchers, pd.DataFrame) and len(unbalanced_vouchers) > 0:
                        st.error(f"❌ 차대평형 오류 발견: {len(unbalanced_vouchers)}건의 불일치 전표")
                        st.dataframe(unbalanced_vouchers)
                    else:
                        st.info("ℹ️ 전표번호 정보가 부족하여 검증할 수 없습니다.")
        
        # A03: Roll-forward 테스트
        if scenario_a03:
            with st.expander("🔄 A03: 시산표 Roll-forward 검증 결과", expanded=True):
                if prev_tb_df is not None and curr_tb_df is not None:
                    if validate_trial_balance(prev_tb_df) and validate_trial_balance(curr_tb_df):
                        with st.spinner("시산표 Roll-forward를 검증하는 중..."):
                            differences, error_msg = scenario_a03_rollforward_test(prev_tb_df, journal_df, curr_tb_df)
                            
                            if error_msg:
                                st.error(f"❌ {error_msg}")
                            elif differences is not None and len(differences) == 0:
                                st.success("✅ Roll-forward 검증 통과: 계산된 시산표와 실제 시산표가 일치합니다.")
                            elif differences is not None and len(differences) > 0:
                                st.warning(f"⚠️ Roll-forward 차이 발견: {len(differences)}건의 불일치 항목")
                                
                                # 주요 차이 항목만 표시
                                display_columns = ['계정코드', '계정과목_prev', '계산된_차변잔액', '차변잔액_actual', 
                                                 '계산된_대변잔액', '대변잔액_actual', '차변_차이', '대변_차이']
                                available_columns = [col for col in display_columns if col in differences.columns]
                                
                                if available_columns:
                                    st.dataframe(differences[available_columns])
                                else:
                                    st.dataframe(differences)
                    else:
                        st.error("❌ 시산표 데이터 형식이 올바르지 않습니다.")
                else:
                    st.info("ℹ️ 시산표 파일(전기, 당기)을 모두 업로드해주세요.")
        
        # B01: 손익계정 중요성금액 분석
        if scenario_b01:
            with st.expander("💰 B01: 손익계정 중요성금액 분석 결과", expanded=False):
                with st.spinner("손익계정을 분석하는 중..."):
                    large_items, error_msg = scenario_b01_large_items_test(journal_df, materiality)
                    
                    if error_msg:
                        st.warning(f"⚠️ {error_msg}")
                    elif len(large_items) == 0:
                        st.success(f"✅ 중요성금액({materiality:,}원) 기준 초과 항목이 없습니다.")
                    else:
                        st.warning(f"⚠️ 중요성금액 기준 초과 항목 {len(large_items)}건 발견")
                        st.dataframe(large_items)
        
        # B02: 비정상 계정 사용 검사
        if scenario_b02:
            with st.expander("🚨 B02: 비정상 계정 사용 검사 결과", expanded=False):
                with st.spinner("비정상 계정 사용을 검사하는 중..."):
                    unmatched_accounts = scenario_b02_unmatched_accounts(journal_df)
                    
                    if len(unmatched_accounts) == 0:
                        st.success("✅ 비정상적인 계정 사용이 발견되지 않았습니다.")
                    else:
                        st.warning(f"⚠️ 비정상적인 계정 사용 {len(unmatched_accounts)}건 발견")
                        st.dataframe(unmatched_accounts)
        
        # B03: 신규 생성 계정과목 검사
        if scenario_b03:
            with st.expander("🆕 B03: 신규 생성 계정과목 검사 결과", expanded=False):
                with st.spinner("신규 계정과목을 분석하는 중..."):
                    new_account_entries, error_msg = scenario_b03_new_accounts(journal_df, prev_tb_df)
                    
                    if error_msg:
                        st.warning(f"⚠️ {error_msg}")
                    elif len(new_account_entries) == 0:
                        st.success("✅ 신규 생성 계정과목이 발견되지 않았습니다.")
                    else:
                        st.warning(f"⚠️ 신규 계정과목 사용 전표 {len(new_account_entries)}건 발견")
                        st.dataframe(new_account_entries)
        
        # B04: 저빈도 사용 계정 검사
        if scenario_b04:
            with st.expander("🔍 B04: 저빈도 사용 계정 검사 결과", expanded=False):
                with st.spinner("저빈도 사용 계정을 분석하는 중..."):
                    seldom_entries, error_msg = scenario_b04_seldom_used_accounts(journal_df, frequency_threshold)
                    
                    if error_msg:
                        st.warning(f"⚠️ {error_msg}")
                    elif len(seldom_entries) == 0:
                        st.success(f"✅ 저빈도({frequency_threshold}회 이하) 사용 계정이 발견되지 않았습니다.")
                    else:
                        st.warning(f"⚠️ 저빈도 사용 계정 전표 {len(seldom_entries)}건 발견")
                        st.dataframe(seldom_entries)
        
        # B05: 비정상 사용자 검사
        if scenario_b05:
            with st.expander("👤 B05: 비정상 사용자 검사 결과", expanded=False):
                with st.spinner("비정상 사용자를 분석하는 중..."):
                    unusual_entries, error_msg = scenario_b05_unusual_user(journal_df)
                    
                    if error_msg:
                        st.warning(f"⚠️ {error_msg}")
                    elif len(unusual_entries) == 0:
                        st.success("✅ 비정상적인 사용자가 발견되지 않았습니다.")
                    else:
                        st.warning(f"⚠️ 비정상 사용자 전표 {len(unusual_entries)}건 발견")
                        st.dataframe(unusual_entries)
        
        # B06: 권한 없는 사용자 검사
        if scenario_b06:
            with st.expander("🚫 B06: 권한 없는 사용자 검사 결과", expanded=False):
                with st.spinner("권한 없는 사용자를 분석하는 중..."):
                    inappropriate_entries, error_msg = scenario_b06_inappropriate_user(journal_df)
                    
                    if error_msg:
                        st.warning(f"⚠️ {error_msg}")
                    elif len(inappropriate_entries) == 0:
                        st.success("✅ 권한 없는 사용자가 발견되지 않았습니다.")
                    else:
                        st.warning(f"⚠️ 권한 없는 사용자 전표 {len(inappropriate_entries)}건 발견")
                        st.dataframe(inappropriate_entries)
        
        # B07: 기표일 이후 입력 전표 분석
        if scenario_b07:
            with st.expander("📅 B07: 기표일 이후 입력 전표 분석 결과", expanded=False):
                with st.spinner("기표일 이후 입력 전표를 분석하는 중..."):
                    back_dated, error_msg = scenario_b07_back_dated_entries(journal_df, fiscal_year_end)
                    
                    if error_msg:
                        st.warning(f"⚠️ {error_msg}")
                    elif len(back_dated) == 0:
                        st.success("✅ 결산일 이후 입력된 전표가 발견되지 않았습니다.")
                    else:
                        st.warning(f"⚠️ 결산일 이후 입력된 전표 {len(back_dated)}건 발견")
                        st.dataframe(back_dated)
        
        # B08: 입력자-승인자 동일 검사
        if scenario_b08:
            with st.expander("👥 B08: 입력자-승인자 동일 검사 결과", expanded=False):
                with st.spinner("입력자와 승인자를 분석하는 중..."):
                    same_user_entries, error_msg = scenario_b08_create_approve_same(journal_df)
                    
                    if error_msg:
                        st.warning(f"⚠️ {error_msg}")
                    elif len(same_user_entries) == 0:
                        st.success("✅ 입력자와 승인자가 동일한 전표가 발견되지 않았습니다.")
                    else:
                        st.warning(f"⚠️ 입력자-승인자 동일 전표 {len(same_user_entries)}건 발견")
                        st.dataframe(same_user_entries)
        
        # B09: 비정상 계정 조합 검사
        if scenario_b09:
            with st.expander("🔗 B09: 비정상 계정 조합 검사 결과", expanded=False):
                with st.spinner("비정상 계정 조합을 분석하는 중..."):
                    unusual_combinations, error_msg = scenario_b09_corresponding_accounts(journal_df)
                    
                    if error_msg:
                        st.warning(f"⚠️ {error_msg}")
                    elif len(unusual_combinations) == 0:
                        st.success("✅ 비정상적인 계정 조합이 발견되지 않았습니다.")
                    else:
                        st.warning(f"⚠️ 비정상 계정 조합 전표 {len(unusual_combinations)}건 발견")
                        st.dataframe(unusual_combinations)
    
    else:
        st.info("📁 분개장 파일을 업로드하고 시나리오를 선택해주세요.")

with col2:
    st.header("📊 데이터 현황")
    
    # 업로드된 파일 현황
    if prev_tb_file:
        st.success("✅ 전기 시산표")
        if prev_tb_df is not None:
            st.metric("레코드 수", len(prev_tb_df))
    else:
        st.info("📄 전기 시산표 대기중")
    
    if journal_file:
        st.success("✅ 분개장")
        if journal_df is not None:
            st.metric("분개 수", len(journal_df))
            if '전표번호' in journal_df.columns:
                unique_vouchers = journal_df['전표번호'].nunique()
                st.metric("전표 수", unique_vouchers)
    else:
        st.info("📄 분개장 대기중")
    
    if curr_tb_file:
        st.success("✅ 당기 시산표")
        if curr_tb_df is not None:
            st.metric("레코드 수", len(curr_tb_df))
    else:
        st.info("📄 당기 시산표 대기중")

# 푸터
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>회계감사 JET 자동화 프로그램 v1.0</p>
    <p>© 2025 Audit Analytics Solutions</p>
</div>
""", unsafe_allow_html=True)