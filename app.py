import streamlit as st
import pandas as pd
import re

# 페이지 설정
st.set_page_config(page_title="Sales vs ERP Recon Tool", layout="wide")

st.title("📊 통합 매출 마감 검증 시스템")
st.info("비교할 두 파일(Sales Report, Book1)을 한꺼번에 업로드하세요. 'Order #'에서 숫자만 있는 데이터만 자동 선별합니다.")

# 1. 통합 파일 업로드 (accept_multiple_files=True)
uploaded_files = st.file_uploader(
    "파일을 한꺼번에 드래그앤드롭 하세요 (Sales Report, Book1)", 
    type=['xlsx', 'csv'], 
    accept_multiple_files=True
)

if len(uploaded_files) == 2:
    df_sales, df_erp = None, None
    
    # 2. 파일명 키워드로 자동 분류
    for file in uploaded_files:
        fname = file.name.lower()
        if "book" in fname:
            df_erp = pd.read_excel(file) if file.name.endswith('xlsx') else pd.read_csv(file)
        else:
            # 기본적으로 book이 아니면 sales report로 간주
            df_sales = pd.read_excel(file) if file.name.endswith('xlsx') else pd.read_csv(file)

    if df_sales is not None and df_erp is not None:
        # --- [데이터 전처리: Sales Report] ---
        
        # J열(Order #)이 비어있는 행 제거
        df_sales = df_sales.dropna(subset=['Order #'])
        
        # Order # 컬럼을 문자열로 변환 후 공백 제거
        df_sales['Order #'] = df_sales['Order #'].astype(str).str.strip()
        
        # 정규표현식을 사용하여 '오직 숫자'로만 구성된 데이터만 필터링 (숫자 외 문자 포함 시 제외)
        # 예: '220549' (유지), '220549-1' (제외), 'None' (제외)
        df_sales = df_sales[df_sales['Order #'].str.match(r'^\d+$')]
        
        # --- [데이터 전처리: ERP (Book1)] ---
        df_erp['Order Number'] = df_erp['Order Number'].astype(str).str.strip()
        # ERP도 안전하게 숫자 패턴만 비교 대상으로 삼음
        df_erp = df_erp[df_erp['Order Number'].str.match(r'^\d+$')]

        # 3. 그룹화 및 합산
        sales_final = df_sales.groupby('Order #').agg({
            '수량': 'sum', 
            'Total Amount': 'sum'
        }).reset_index()

        erp_final = df_erp.groupby('Order Number').agg({
            'Quantity': 'sum', 
            'Extended Amount': 'sum'
        }).reset_index()

        # 4. 데이터 병합 및 오차 계산
        merged = pd.merge(sales_final, erp_final, left_on='Order #', right_on='Order Number', how='outer')
        
        merged['수량_차이'] = merged['수량'].fillna(0) - merged['Quantity'].fillna(0)
        merged['금액_차이'] = merged['Total Amount'].fillna(0) - merged['Extended Amount'].fillna(0)

        # 5. 결과 시각화
        mismatch = merged[(merged['수량_차이'] != 0) | (merged['금액_차이'] != 0)].copy()

        st.subheader("✅ 필터링 및 분석 결과")
        c1, c2, c3 = st.columns(3)
        c1.metric("유효 숫자 오더 수 (Sales)", len(sales_final))
        c2.metric("ERP 오더 수", len(erp_final))
        c3.metric("불일치 건수", len(mismatch), delta_color="inverse")

        if not mismatch.empty:
            st.error(f"🚩 {len(mismatch)}건의 차이가 발견되었습니다.")
            
            # 보기 편하게 컬럼 정리
            display_df = mismatch[['Order #', 'Order Number', '수량', 'Quantity', '수량_차이', 'Total Amount', 'Extended Amount', '금액_차이']]
            display_df.columns = ['Sales_오더', 'ERP_오더', 'Sales_수량', 'ERP_수량', '수량차이', 'Sales_금액', 'ERP_금액', '금액차이']
            
            st.dataframe(display_df.style.format(precision=0).background_gradient(cmap='Reds', subset=['수량차이', '금액차이']))
            
            csv = display_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 불일치 리스트 다운로드", csv, "mismatch_report.csv", "text/csv")
        else:
            st.success("🎉 숫자 코드가 입력된 모든 오더가 ERP 데이터와 완벽히 일치합니다!")

    else:
        st.warning("⚠️ 파일 분류에 실패했습니다. 파일명에 'Book' 키워드가 포함되어 있는지 확인해주세요.")

elif len(uploaded_files) > 0:
    st.info(f"현재 {len(uploaded_files)}개의 파일이 올라갔습니다. 비교를 위해 총 2개의 파일이 필요합니다.")
