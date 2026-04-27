import streamlit as st
import pandas as pd
import numpy as np

# 페이지 설정
st.set_page_config(page_title="Sales vs ERP Recon Tool", layout="wide")

st.title("📊 매출 마감 데이터 최종 검증 툴 (단가 None=0원 처리)")
st.info("💡 세일즈 리포트 단가가 비어있거나(None) 문자인 경우 0원으로 자동 계산합니다.")

# 1. 파일 업로드 섹션
uploaded_files = st.file_uploader(
    "Sales Report와 Book1 파일을 함께 업로드하세요", 
    type=['xlsx', 'csv'], 
    accept_multiple_files=True
)

if len(uploaded_files) == 2:
    df_sales, df_erp = None, None
    
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
        # [수정] '단가'가 비어있어도 행을 삭제하지 않음 (Order #와 수량만 필수 체크)
        df_sales = df_sales.dropna(subset=['Order #', '수량'])
        
        # 오더번호 전처리
        df_sales['Order #'] = df_sales['Order #'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        df_sales = df_sales[df_sales['Order #'].str.match(r'^\d+$')]

        # [수정] 단가가 숫자가 아니거나 None인 경우 0으로 강제 변환
        df_sales['단가'] = pd.to_numeric(df_sales['단가'], errors='coerce').fillna(0)
        
        # 수량 데이터 숫자 변환
        df_sales['수량'] = pd.to_numeric(df_sales['수량'], errors='coerce').fillna(0)

        # 단가 소수점 4자리 절사 및 금액 계산
        df_sales['단가'] = np.floor(df_sales['단가'] * 10000) / 10000
        df_sales['Total Amount'] = df_sales['단가'] * df_sales['수량']

        sales_grouped = df_sales.groupby('Order #').agg({
            '수량': 'sum',
            'Total Amount': 'sum'
        }).reset_index()

        # --- [ERP(Book) 데이터 전처리] ---
        df_erp = df_erp.dropna(subset=['Order Number'])
        df_erp['Order Number'] = df_erp['Order Number'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        
        # ERP 수량/금액도 숫자형 변환 (에러 방지)
        df_erp['Quantity'] = pd.to_numeric(df_erp['Quantity'], errors='coerce').fillna(0)
        df_erp['Extended Amount'] = pd.to_numeric(df_erp['Extended Amount'], errors='coerce').fillna(0)
        
        erp_grouped = df_erp.groupby('Order Number').agg({
            'Quantity': 'sum',
            'Extended Amount': 'sum'
        }).reset_index()

        # --- [데이터 병합 및 정밀 비교 로직] ---
        merged = pd.merge(sales_grouped, erp_grouped, left_on='Order #', right_on='Order Number', how='outer').fillna(0)

        # 1. 수량 차이 계산
        merged['수량차이'] = merged['수량'] - merged['Quantity']
        
        # 2. 금액 비교용 절사 데이터 생성 (1원 단위 버림)
        merged['Sales_10원절사'] = (merged['Total Amount'] // 10) * 10
        merged['ERP_10원절사'] = (merged['Extended Amount'] // 10) * 10
        merged['금액차이_실제'] = merged['Total Amount'] - merged['Extended Amount']

        # 3. 상태 분류 함수
        def check_status(row):
            if row['수량차이'] != 0:
                return "❌ 수량 불일치"
            if abs(row['금액차이_실제']) < 1:
                return "✅ 완전 일치"
            if row['Sales_10원절사'] == row['ERP_10원절사']:
                return "⚠️ 단가 미세오차(정상)"
            return "❌ 금액 불일치"

        merged['비교결과'] = merged.apply(check_status, axis=1)

        # 최종 불일치 및 미세오차 리스트
        mismatch = merged[merged['비교결과'].str.contains("❌")].copy()
        minor_errors = merged[merged['비교결과'] == "⚠️ 단가 미세오차(정상)"].copy()

        # --- [결과 표시] ---
        st.subheader("✅ 검증 요약")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 오더 수", len(merged))
        c2.metric("완전 일치", len(merged[merged['비교결과']=="✅ 완전 일치"]))
        c3.metric("단가 미세오차(허용)", len(minor_errors))
        c4.metric("실제 불일치", len(mismatch), delta_color="inverse")

        if not mismatch.empty:
            st.error("🚩 즉시 확인이 필요한 불일치 오더")
            display_mismatch = mismatch[['Order #', '수량', 'Quantity', '수량차이', 'Total Amount', 'Extended Amount', '금액차이_실제', '비교결과']]
            st.dataframe(display_mismatch.style.format(precision=0), use_container_width=True)
            
            csv_mismatch = display_mismatch.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 불일치 리스트 다운로드", csv_mismatch, "mismatch_critical.csv")

        if not minor_errors.empty:
            with st.expander("🔍 단가 소수점 차이가 발생한 오더 확인 (정상 처리됨)"):
                display_minor = minor_errors[['Order #', 'Total Amount', 'Extended Amount', '금액차이_실제', '비교결과']]
                st.dataframe(display_minor.style.format(precision=2), use_container_width=True)

        if mismatch.empty:
            st.success("🎉 모든 데이터가 정상 범위 내에서 일치합니다!")

elif len(uploaded_files) > 0:
    st.warning("파일 2개를 모두 올려주세요.")
