import streamlit as st
import pandas as pd

st.set_page_config(page_title="Sales vs ERP Recon", layout="wide")
st.title("🚀 통합 파일 검증 시스템")
st.markdown("비교할 **두 개의 파일(ERP, Sales)**을 아래 창에 한꺼번에 던져주세요!")

# 1. 단일 업로드 창 (여러 파일 수용)
uploaded_files = st.file_uploader(
    "파일을 한꺼번에 선택하거나 드래그하세요", 
    type=['xlsx', 'csv'], 
    accept_multiple_files=True
)

if len(uploaded_files) == 2:
    df_sales, df_erp = None, None
    
    # 2. 파일명 키워드로 자동 분류 (사용자가 순서를 고민할 필요 없음)
    for file in uploaded_files:
        if "book" in file.name.lower():
            df_erp = pd.read_excel(file) if file.name.endswith('xlsx') else pd.read_csv(file)
        elif "sales" in file.name.lower():
            df_sales = pd.read_excel(file) if file.name.endswith('xlsx') else pd.read_csv(file)

    # 분류 확인
    if df_sales is not None and df_erp is not None:
        # --- 전처리 로직 (기존과 동일하게 None 필터링 포함) ---
        df_sales = df_sales.dropna(subset=['Order #'])
        df_sales['Order #'] = df_sales['Order #'].astype(str).str.strip()
        df_sales = df_sales[df_sales['Order #'].str.lower() != 'none']
        
        df_erp['Order Number'] = df_erp['Order Number'].astype(str).str.strip()

        # 그룹화 합산
        sales_final = df_sales.groupby('Order #').agg({'수량': 'sum', 'Total Amount': 'sum'}).reset_index()
        erp_final = df_erp.groupby('Order Number').agg({'Quantity': 'sum', 'Extended Amount': 'sum'}).reset_index()

        # 병합 및 차이 계산
        merged = pd.merge(sales_final, erp_final, left_on='Order #', right_on='Order Number', how='outer')
        merged['수량차이'] = merged['수량'].fillna(0) - merged['Quantity'].fillna(0)
        merged['금액차이'] = merged['Total Amount'].fillna(0) - merged['Extended Amount'].fillna(0)

        # 결과 출력
        mismatch = merged[(merged['수량차이'] != 0) | (merged['금액차이'] != 0)]
        
        if mismatch.empty:
            st.success("✅ 모든 데이터가 일치합니다!")
        else:
            st.error(f"⚠️ {len(mismatch)}건의 차이가 발견되었습니다.")
            st.dataframe(mismatch, use_container_width=True)
    else:
        st.warning("파일명을 확인해주세요. 하나는 'Book', 다른 하나는 'Sales' 키워드가 포함되어야 합니다.")

elif len(uploaded_files) > 0:
    st.info("파일을 하나 더 올려주세요. (현재 1개 업로드됨)")
