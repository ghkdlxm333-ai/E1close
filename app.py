import streamlit as st
import pandas as pd

st.set_page_config(page_title="Sales vs ERP Recon Tool", layout="wide")
st.title("📊 [일일출고] 시트 전용 검증 시스템")

# 1. 통합 파일 업로드
uploaded_files = st.file_uploader(
    "Sales Report와 Book1 파일을 한꺼번에 업로드하세요", 
    type=['xlsx', 'csv'], 
    accept_multiple_files=True
)

if len(uploaded_files) == 2:
    df_sales, df_erp = None, None
    
    for file in uploaded_files:
        # Book1 파일 판별
        if "book" in file.name.lower():
            df_erp = pd.read_excel(file) if file.name.endswith('xlsx') else pd.read_csv(file)
        else:
            # Sales Report 파일일 경우 '일일출고' 시트만 로드
            if file.name.endswith('xlsx'):
                try:
                    # [핵심 수정] 오직 '일일출고' 시트만 읽어옴
                    df_sales = pd.read_excel(file, sheet_name='일일출고')
                    st.success(f"✅ {file.name}에서 '일일출고' 시트를 성공적으로 로드했습니다.")
                except ValueError:
                    st.error(f"❌ {file.name} 파일에 '일일출고' 시트가 없습니다. 시트명을 확인해주세요.")
            else:
                df_sales = pd.read_csv(file)

    if df_sales is not None and df_erp is not None:
        # --- 전처리: Sales Report (Order # 컬럼 기준 숫자만) ---
        # 'Order #' 컬럼이 존재하는지 확인
        if 'Order #' in df_sales.columns:
            df_sales = df_sales.dropna(subset=['Order #'])
            df_sales['Order #'] = df_sales['Order #'].astype(str).str.strip()
            # 숫자만 있는 데이터만 필터링 (텍스트, 빈값 제외)
            df_sales = df_sales[df_sales['Order #'].str.match(r'^\d+$')]
            
            # 수량 및 금액 합산
            sales_final = df_sales.groupby('Order #').agg({
                '수량': 'sum', 
                'Total Amount': 'sum'
            }).reset_index()
        else:
            st.error("❌ Sales Report에 'Order #' 컬럼이 없습니다.")
            st.stop()

        # --- 전처리: ERP (Order Number 기준) ---
        df_erp['Order Number'] = df_erp['Order Number'].astype(str).str.strip()
        erp_final = df_erp.groupby('Order Number').agg({
            'Quantity': 'sum', 
            'Extended Amount': 'sum'
        }).reset_index()

        # --- 데이터 병합 및 비교 ---
        merged = pd.merge(sales_final, erp_final, left_on='Order #', right_on='Order Number', how='outer')
        merged['수량차이'] = merged['수량'].fillna(0) - merged['Quantity'].fillna(0)
        merged['금액차이'] = merged['Total Amount'].fillna(0) - merged['Extended Amount'].fillna(0)

        # 결과 필터링
        mismatch = merged[(merged['수량차이'] != 0) | (merged['금액차이'] != 0)].copy()

        # 결과 화면
        st.subheader("📝 비교 결과 요약 (대상: 일일출고 시트)")
        c1, c2, c3 = st.columns(3)
        c1.metric("Sales 오더 수", len(sales_final))
        c2.metric("ERP 오더 수", len(erp_final))
        c3.metric("불일치 건수", len(mismatch), delta_color="inverse")

        if not mismatch.empty:
            st.warning("⚠️ 데이터 불일치가 발견되었습니다.")
            # 가독성 정리
            mismatch = mismatch[['Order #', '수량', 'Quantity', '수량차이', 'Total Amount', 'Extended Amount', '금액차이']]
            mismatch.columns = ['오더번호', 'Sales수량', 'ERP수량', '수량차이', 'Sales금액', 'ERP금액', '금액차이']
            st.dataframe(mismatch.style.format(precision=0).background_gradient(cmap='Reds', subset=['수량차이', '금액차이']))
        else:
            st.success("🎉 '일일출고' 시트의 모든 오더가 ERP 데이터와 정확히 일치합니다!")

elif len(uploaded_files) > 0:
    st.info("비교를 위해 나머지 파일 하나를 더 업로드해주세요.")
