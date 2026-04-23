import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="Sales vs ERP Recon Tool", layout="wide")

st.title("📊 매출 마감 데이터 정밀 비교 툴")
st.info("Sales Report에서 'Order #'가 없는 데이터는 자동으로 제외하고 분석을 시작합니다.")

# 1. 파일 업로드 섹션
col1, col2 = st.columns(2)

with col1:
    sales_file = st.file_uploader("📂 Sales Report (수기 관리 엑셀) 업로드", type=['xlsx', 'csv'])
with col2:
    erp_file = st.file_uploader("📂 Book1 (ERP 로우 데이터) 업로드", type=['xlsx', 'csv'])

if sales_file and erp_file:
    # 데이터 로드 (엑셀 시트가 여러개일 경우를 대비해 첫 번째 시트를 기본 로드)
    df_sales = pd.read_excel(sales_file) if sales_file.name.endswith('xlsx') else pd.read_csv(sales_file)
    df_erp = pd.read_excel(erp_file) if erp_file.name.endswith('xlsx') else pd.read_csv(erp_file)

    # --- [필터링 및 전처리 로직 시작] ---
    
    # 1. Sales Report: Order # 컬럼에서 결측치 및 'None' 제거
    # 숫자가 아닌 문자열 'None'과 실제 NaN 값을 모두 처리합니다.
    df_sales_clean = df_sales.dropna(subset=['Order #']).copy()
    df_sales_clean = df_sales_clean[df_sales_clean['Order #'].astype(str).str.lower() != 'none']
    
    # 데이터 타입 통일 (비교를 위해 문자열로 변환)
    df_sales_clean['Order #'] = df_sales_clean['Order #'].astype(str).str.strip()
    df_erp['Order Number'] = df_erp['Order Number'].astype(str).str.strip()

    # 2. Sales Report 그룹화 (Order # 기준 합산)
    sales_grouped = df_sales_clean.groupby('Order #').agg({
        '수량': 'sum',
        'Total Amount': 'sum'
    }).reset_index()

    # 3. ERP 데이터 그룹화 (Order Number 기준 합산)
    erp_grouped = df_erp.groupby('Order Number').agg({
        'Quantity': 'sum',
        'Extended Amount': 'sum'
    }).reset_index()

    # --- [필터링 및 전처리 로직 끝] ---

    # 4. 데이터 병합 (Outer Join)
    merged = pd.merge(
        sales_grouped, 
        erp_grouped, 
        left_on='Order #', 
        right_on='Order Number', 
        how='outer'
    )

    # 5. 오차 계산
    merged['수량_차이'] = merged['수량'].fillna(0) - merged['Quantity'].fillna(0)
    merged['금액_차이'] = merged['Total Amount'].fillna(0) - merged['Extended Amount'].fillna(0)

    # 6. 결과 요약
    mismatch = merged[(merged['수량_차이'] != 0) | (merged['금액_차이'] != 0)].copy()

    st.subheader("✅ 필터링 후 분석 요약")
    s_col1, s_col2, s_col3, s_col4 = st.columns(4)
    s_col1.metric("Sales 유효 오더 수", len(sales_grouped))
    s_col2.metric("ERP 오더 수", len(erp_grouped))
    s_col3.metric("불일치 오더", len(mismatch), delta_color="inverse")
    s_col4.metric("일치 오더", len(merged) - len(mismatch))

    st.markdown("---")

    # 7. 불일치 데이터 리포트
    if len(mismatch) > 0:
        st.error(f"🚩 총 {len(mismatch)}건의 데이터 불일치가 발견되었습니다.")
        
        # 가독성을 위해 컬럼 순서 조정
        display_df = mismatch[[
            'Order #', 'Order Number', 
            '수량', 'Quantity', '수량_차이', 
            'Total Amount', 'Extended Amount', '금액_차이'
        ]].rename(columns={
            '수량': 'Sales수량', 'Quantity': 'ERP수량',
            'Total Amount': 'Sales금액', 'Extended Amount': 'ERP금액'
        })
        
        # 스타일링: 0이 아닌 오차값에 강조색 적용
        def highlight_errors(val):
            color = 'background-color: #ffcccc' if val != 0 else ''
            return color

        st.dataframe(
            display_df.style.applymap(highlight_errors, subset=['수량_차이', '금액_차이']),
            use_container_width=True
        )
        
        # 다운로드 버튼
        csv = display_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 수정 필요 리스트 다운로드", csv, "mismatch_check_list.csv", "text/csv")
    else:
        st.success("🎉 'Order #'가 있는 모든 유효 데이터가 ERP와 완벽히 일치합니다!")

else:
    st.warning("⚠️ 분석을 시작하려면 두 파일을 모두 업로드해주세요.")
