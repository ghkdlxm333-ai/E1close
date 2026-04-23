import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="Sales vs ERP Recon Tool", layout="wide")

st.title("📊 매출 마감 데이터 비교 검증 툴")
st.markdown("---")

# 1. 파일 업로드 섹션
col1, col2 = st.columns(2)

with col1:
    sales_file = st.file_uploader("📂 Sales Report (수기 관리 엑셀) 업로드", type=['xlsx', 'csv'])
with col2:
    erp_file = st.file_uploader("📂 Book1 (ERP 로우 데이터) 업로드", type=['xlsx', 'csv'])

if sales_file and erp_file:
    # 데이터 로드
    df_sales = pd.read_excel(sales_file) if sales_file.name.endswith('xlsx') else pd.read_csv(sales_file)
    df_erp = pd.read_excel(erp_file) if erp_file.name.endswith('xlsx') else pd.read_csv(erp_file)

    # 데이터 전처리 (Order Number 기준 그룹화)
    # 수기 데이터는 중복 데이터가 있을 수 있으므로 Order # 기준으로 수량과 금액을 합산합니다.
    sales_grouped = df_sales.groupby('Order #').agg({
        '수량': 'sum',
        'Total Amount': 'sum'
    }).reset_index()

    # ERP 데이터 전처리 (Order Number 기준 그룹화)
    erp_grouped = df_erp.groupby('Order Number').agg({
        'Quantity': 'sum',
        'Extended Amount': 'sum'
    }).reset_index()

    # 2. 데이터 병합 (Outer Join으로 누락된 오더까지 체크)
    merged = pd.merge(
        sales_grouped, 
        erp_grouped, 
        left_on='Order #', 
        right_on='Order Number', 
        how='outer'
    )

    # 3. 차이 계산 로직
    merged['수량_차이'] = merged['수량'].fillna(0) - merged['Quantity'].fillna(0)
    merged['금액_차이'] = merged['Total Amount'].fillna(0) - merged['Extended Amount'].fillna(0)

    # 불일치 데이터 필터링
    mismatch = merged[(merged['수량_차이'] != 0) | (merged['금액_차이'] != 0)].copy()

    # 결과 요약 시각화
    st.subheader("✅ 분석 결과 요약")
    s_col1, s_col2, s_col3 = st.columns(3)
    s_col1.metric("총 처리 오더 수", len(merged))
    s_col2.metric("일치 오더", len(merged) - len(mismatch))
    s_col3.metric("불일치 오더", len(mismatch), delta_color="inverse")

    st.markdown("---")

    # 4. 세부 비교 데이터 표시
    if len(mismatch) > 0:
        st.error(f"🚩 총 {len(mismatch)}건의 데이터 불일치가 발견되었습니다. 아래 표를 확인하여 수정하세요.")
        
        # 가독성을 위해 컬럼명 정리 및 스타일링
        display_df = mismatch[['Order #', 'Order Number', '수량', 'Quantity', '수량_차이', 'Total Amount', 'Extended Amount', '금액_차이']]
        
        # 스타일 적용: 차이가 있는 셀 강조
        def highlight_diff(s):
            return ['background-color: #ffcccc' if v != 0 else '' for v in s]

        st.dataframe(
            display_df.style.apply(highlight_diff, subset=['수량_차이', '금액_차이']),
            use_container_width=True
        )
        
        # 엑셀 다운로드 기능
        csv = display_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 불일치 리스트 다운로드 (CSV)", csv, "mismatch_report.csv", "text/csv")
    else:
        st.success("🎉 모든 데이터가 ERP 시스템과 일치합니다! 마감을 진행하셔도 좋습니다.")

    # 5. 전체 데이터 보기 (선택 사항)
    with st.expander("전체 비교 데이터 상세 보기"):
        st.write(merged)

else:
    st.info("💡 왼쪽 상단에서 두 개의 파일을 모두 업로드하면 자동으로 비교 분석이 시작됩니다.")
