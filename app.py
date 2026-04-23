import streamlit as st
import pandas as pd
import numpy as np

# 페이지 설정
st.set_page_config(page_title="Sales vs ERP Recon Tool", layout="wide")

st.title("📊 매출 마감 데이터 최종 검증 툴 (단가 소수점 4자리 절사 버전)")
st.markdown("---")

# 1. 파일 업로드 섹션
uploaded_files = st.file_uploader(
    "Sales Report와 Book1 파일을 함께 업로드하세요", 
    type=['xlsx', 'csv'], 
    accept_multiple_files=True
)

if len(uploaded_files) == 2:
    df_sales, df_erp = None, None
    
    # 파일 분류 및 로드
    for file in uploaded_files:
        if "book" in file.name.lower():
            df_erp = pd.read_excel(file) if file.name.endswith('xlsx') else pd.read_csv(file)
        else:
            if file.name.endswith('xlsx'):
                try:
                    df_sales = pd.read_excel(file, sheet_name='일일출고')
                except ValueError:
                    st.error(f"❌ '{file.name}' 파일에 [일일출고] 시트가 없습니다.")
                    st.stop()
            else:
                df_sales = pd.read_csv(file)

    if df_sales is not None and df_erp is not None:
        # --- [Sales Report 전처리] ---
        if 'Order #' in df_sales.columns:
            # 기본 필터링 (결측치 제거 및 오더번호 정수화)
            df_sales = df_sales.dropna(subset=['Order #', '수량', '단가'])
            df_sales['Order #'] = df_sales['Order #'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            df_sales = df_sales[df_sales['Order #'].str.match(r'^\d+$')]

            # [핵심 수정] 단가 소수점 4자리 절사 및 금액 재계산
            # np.floor를 이용해 소수점 4자리까지 남기고 절사 (예: 10.12345 -> 10.1234)
            df_sales['단가'] = np.floor(df_sales['단가'] * 10000) / 10000
            df_sales['Total Amount'] = df_sales['단가'] * df_sales['수량']

            sales_grouped = df_sales.groupby('Order #').agg({
                '수량': 'sum',
                'Total Amount': 'sum'
            }).reset_index()
        else:
            st.error("❌ Sales Report에 'Order #' 컬럼이 없습니다.")
            st.stop()

        # --- [ERP(Book) 데이터 전처리] ---
        if 'Order Number' in df_erp.columns:
            df_erp = df_erp.dropna(subset=['Order Number'])
            df_erp['Order Number'] = df_erp['Order Number'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            
            erp_grouped = df_erp.groupby('Order Number').agg({
                'Quantity': 'sum',
                'Extended Amount': 'sum'
            }).reset_index()
        else:
            st.error("❌ ERP 파일에 'Order Number' 컬럼이 없습니다.")
            st.stop()

        # --- [데이터 병합 및 최종 비교] ---
        merged = pd.merge(
            sales_grouped, 
            erp_grouped, 
            left_on='Order #', 
            right_on='Order Number', 
            how='outer'
        ).fillna(0)

        # 차이 계산
        merged['수량차이'] = merged['수량'] - merged['Quantity']
        # 비교 시에는 정수 단위 반올림하여 비교
        merged['금액차이'] = merged['Total Amount'].round(0) - merged['Extended Amount'].round(0)

        # 불일치 조건 추출
        mismatch = merged[(merged['수량차이'] != 0) | (merged['금액차이'] != 0)].copy()

        # --- [결과 표시] ---
        st.subheader("✅ 분석 결과 요약 (단가 절사 및 반올림 적용)")
        s_col1, s_col2, s_col3 = st.columns(3)
        s_col1.metric("Sales 오더 수", len(sales_grouped))
        s_col2.metric("ERP 오더 수", len(erp_grouped))
        s_col3.metric("불일치 건수", len(mismatch), delta_color="inverse")

        if not mismatch.empty:
            st.error(f"🚩 총 {len(mismatch)}건의 불일치가 발견되었습니다.")
            
            display_df = mismatch[['Order #', 'Order Number', '수량', 'Quantity', '수량차이', 'Total Amount', 'Extended Amount', '금액차이']]
            display_df.columns = ['Sales오더', 'ERP오더', 'Sales수량', 'ERP수량', '수량차이', 'Sales금액', 'ERP금액', '금액차이']

            st.dataframe(
                display_df.style.format(precision=2).background_gradient(cmap='Reds', subset=['수량차이', '금액차이']),
                use_container_width=True
            )
            
            csv_data = display_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 불일치 리스트 다운로드",
                data=csv_data,
                file_name="mismatch_report_final.csv",
                mime="text/csv"
            )
        else:
            st.success("🎉 단가 소수점 4자리 절사 기준, 모든 데이터가 일치합니다!")

elif len(uploaded_files) > 0:
    st.info("비교를 위해 나머지 파일 하나를 더 업로드해주세요.")
