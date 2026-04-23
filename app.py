import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="Sales vs ERP Recon Tool", layout="wide")

st.title("📊 매출 마감 데이터 최종 검증 툴")
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
            df_sales = df_sales.dropna(subset=['Order #'])
            df_sales['Order #'] = df_sales['Order #'].astype(str).str.strip()
            # 소수점이 포함된 경우(예: '220549.0') 정수 부분만 추출
            df_sales['Order #'] = df_sales['Order #'].str.replace(r'\.0$', '', regex=True)
            df_sales = df_sales[df_sales['Order #'].str.match(r'^\d+$')]

            sales_grouped = df_sales.groupby('Order #').agg({
                '수량': 'sum',
                'Total Amount': 'sum'
            }).reset_index()
        else:
            st.error("❌ Sales Report에 'Order #' 컬럼이 없습니다.")
            st.stop()

        # --- [ERP(Book) 데이터 전처리] ---
        if 'Order Number' in df_erp.columns:
            # [핵심 수정] 소수점(.0) 제거 후 순수 숫자 문자열로 변환
            df_erp = df_erp.dropna(subset=['Order Number'])
            df_erp['Order Number'] = df_erp['Order Number'].astype(str).str.strip()
            # '12345.0' -> '12345'로 변환
            df_erp['Order Number'] = df_erp['Order Number'].str.replace(r'\.0$', '', regex=True)
            
            erp_grouped = df_erp.groupby('Order Number').agg({
                'Quantity': 'sum',
                'Extended Amount': 'sum'
            }).reset_index()
        else:
            st.error("❌ ERP 파일에 'Order Number' 컬럼이 없습니다.")
            st.stop()

        # --- [데이터 비교 분석] ---
        # 두 데이터프레임 모두 문자열 타입의 숫자만 존재하므로 정확히 매칭됩니다.
        merged = pd.merge(
            sales_grouped, 
            erp_grouped, 
            left_on='Order #', 
            right_on='Order Number', 
            how='outer'
        )

        merged['수량_차이'] = merged['수량'].fillna(0) - merged['Quantity'].fillna(0)
        merged['금액_차이'] = merged['Total Amount'].fillna(0) - merged['Extended Amount'].fillna(0)

        # 수량이나 금액 중 하나라도 차이가 있는 행만 추출
        mismatch = merged[(merged['수량_차이'] != 0) | (merged['금액_차이'].abs() > 0.1)].copy()

        # --- [결과 표시] ---
        st.subheader("✅ 분석 결과 요약")
        s_col1, s_col2, s_col3 = st.columns(3)
        s_col1.metric("Sales 오더 수", len(sales_grouped))
        s_col2.metric("ERP 오더 수", len(erp_grouped))
        s_col3.metric("불일치 건수", len(mismatch), delta_color="inverse")

        if len(mismatch) > 0:
            st.error(f"🚩 총 {len(mismatch)}건의 데이터 불일치가 발견되었습니다.")
            
            # 컬럼 정리 및 출력
            display_df = mismatch[['Order #', 'Order Number', '수량', 'Quantity', '수량_차이', 'Total Amount', 'Extended Amount', '금액_차이']]
            display_df.columns = ['Sales_오더', 'ERP_오더', 'Sales_수량', 'ERP_수량', '수량차이', 'Sales_금액', 'ERP_금액', '금액차이']

            st.dataframe(
                display_df.style.format(precision=0).background_gradient(cmap='Reds', subset=['수량차이', '금액차이']),
                use_container_width=True
            )
            
            # 다운로드 버튼
            csv_data = display_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 불일치 리스트 다운로드 (CSV)",
                data=csv_data,
                file_name="mismatch_report_fixed.csv",
                mime="text/csv"
            )
        else:
            st.success("🎉 모든 오더 번호가 정확하게 매칭되며, 데이터가 일치합니다!")

elif len(uploaded_files) > 0:
    st.warning("⚠️ Sales Report와 Book1 파일을 모두 업로드해 주세요.")
