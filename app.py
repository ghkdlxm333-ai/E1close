import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="Sales vs ERP Recon Tool", layout="wide")

st.title("📊 매출 마감 데이터 최종 검증 툴")
st.markdown("---")

# 1. 파일 업로드 섹션 (통합)
uploaded_files = st.file_uploader(
    "Sales Report와 Book1 파일을 함께 업로드하세요 (드래그 앤 드롭 가능)", 
    type=['xlsx', 'csv'], 
    accept_multiple_files=True
)

if len(uploaded_files) == 2:
    df_sales, df_erp = None, None
    
    # 파일 분류 로직
    for file in uploaded_files:
        if "book" in file.name.lower():
            df_erp = pd.read_excel(file) if file.name.endswith('xlsx') else pd.read_csv(file)
        else:
            if file.name.endswith('xlsx'):
                try:
                    # [수정] 오직 '일일출고' 시트만 로드
                    df_sales = pd.read_excel(file, sheet_name='일일출고')
                except ValueError:
                    st.error(f"❌ '{file.name}' 파일에 [일일출고] 시트가 없습니다. 시트명을 확인해 주세요.")
                    st.stop()
            else:
                df_sales = pd.read_csv(file)

    if df_sales is not None and df_erp is not None:
        # --- [Sales Report 전처리] ---
        # 1. Order # 컬럼 존재 확인
        if 'Order #' not in df_sales.columns:
            st.error("❌ Sales Report에 'Order #' 컬럼이 없습니다. J열의 제목을 확인해 주세요.")
            st.stop()

        # 2. J열(Order #) 필터링: 숫자 코드 외 나머지 제외
        # - 결측치 제거
        df_sales = df_sales.dropna(subset=['Order #'])
        # - 문자열 변환 및 공백 제거
        df_sales['Order #'] = df_sales['Order #'].astype(str).str.strip()
        # - 정규표현식: 오직 숫자만 있는 행만 유지 (그 외 텍스트, 혼합형 제외)
        df_sales = df_sales[df_sales['Order #'].str.match(r'^\d+$')]

        # 3. 데이터 그룹화 (중복 오더 합산)
        sales_grouped = df_sales.groupby('Order #').agg({
            '수량': 'sum',
            'Total Amount': 'sum'
        }).reset_index()

        # --- [ERP(Book) 데이터 전처리] ---
        # Order Number 기준으로 전처리
        df_erp['Order Number'] = df_erp['Order Number'].astype(str).str.strip()
        erp_grouped = df_erp.groupby('Order Number').agg({
            'Quantity': 'sum',
            'Extended Amount': 'sum'
        }).reset_index()

        # --- [데이터 비교 분석] ---
        merged = pd.merge(
            sales_grouped, 
            erp_grouped, 
            left_on='Order #', 
            right_on='Order Number', 
            how='outer'
        )

        # 차이 계산 (결측치는 0으로 처리)
        merged['수량_차이'] = merged['수량'].fillna(0) - merged['Quantity'].fillna(0)
        merged['금액_차이'] = merged['Total Amount'].fillna(0) - merged['Extended Amount'].fillna(0)

        # 불일치 데이터만 추출
        mismatch = merged[(merged['수량_차이'] != 0) | (merged['금액_차이'] != 0)].copy()

        # --- [결과 표시] ---
        st.subheader("✅ 분석 결과 요약")
        s_col1, s_col2, s_col3 = st.columns(3)
        s_col1.metric("최종 비교 대상 (Sales)", len(sales_grouped))
        s_col2.metric("일치 오더", len(merged) - len(mismatch))
        s_col3.metric("불일치 오더", len(mismatch), delta_color="inverse")

        st.markdown("---")

        if len(mismatch) > 0:
            st.error(f"🚩 총 {len(mismatch)}건의 데이터 불일치가 발견되었습니다.")
            
            # 보기 좋게 컬럼 재정렬
            display_df = mismatch[['Order #', 'Order Number', '수량', 'Quantity', '수량_차이', 'Total Amount', 'Extended Amount', '금액_차이']]
            display_df.columns = ['Sales_오더', 'ERP_오더', 'Sales_수량', 'ERP_수량', '수량차이', 'Sales_금액', 'ERP_금액', '금액차이']

            # 불일치 데이터 테이블 출력 (색상 강조)
            st.dataframe(
                display_df.style.format(precision=0).background_gradient(cmap='Reds', subset=['수량차이', '금액차이']),
                use_container_width=True
            )
            
            # [수정] 불일치 결과 다운로드 버튼 추가
            csv_data = display_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 불일치 리스트 다운로드 (CSV)",
                data=csv_data,
                file_name="mismatch_report.csv",
                mime="text/csv"
            )
        else:
            st.success("🎉 모든 숫자 코드 데이터가 ERP와 완벽하게 일치합니다!")

elif len(uploaded_files) > 0:
    st.warning("⚠️ 파일이 2개 필요합니다. (Sales Report와 Book1 파일을 모두 업로드해 주세요)")
