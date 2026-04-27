import streamlit as st
import pandas as pd
import numpy as np

# 페이지 설정
st.set_page_config(page_title="Sales vs ERP Recon Tool", layout="wide")

st.title("📊 매출 마감 데이터 최종 검증 툴 (단가 0원 포함 버전)")
st.info("💡 단가가 0원인 행(샘플, 증정 등)도 수량 합산에 모두 포함되도록 개선되었습니다.")

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
                    # [일일출고] 시트 로드
                    df_sales = pd.read_excel(file, sheet_name='일일출고')
                except ValueError:
                    st.error(f"❌ '{file.name}' 파일에 [일일출고] 시트가 없습니다.")
                    st.stop()
            else:
                df_sales = pd.read_csv(file)

    if df_sales is not None and df_erp is not None:
        # --- [Sales Report 전처리] ---
        # [개선] 단가(R열)는 제외하고, 오더#(J열)과 수량(Q열)이 있는지만 확인
        df_sales = df_sales.dropna(subset=['Order #', '수량'])
        
        # 오더번호 전처리 (소수점 제거 및 공백 제거)
        df_sales['Order #'] = df_sales['Order #'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        
        # 수량 데이터를 숫자로 변환 (오류 발생 시 0으로 처리하여 계산 중단 방지)
        df_sales['수량'] = pd.to_numeric(df_sales['수량'], errors='coerce').fillna(0)
        
        # 단가가 0이거나 비어있는 경우를 위해 단가 전처리 (0으로 채움)
        df_sales['단가'] = pd.to_numeric(df_sales['단가'], errors='coerce').fillna(0)

        # [요청사항 반영] 단가 소수점 4자리 절사 및 금액 재계산
        df_sales['단가'] = np.floor(df_sales['단가'] * 10000) / 10000
        df_sales['Total Amount'] = df_sales['단가'] * df_sales['수량']

        # 그룹화 합산
        sales_grouped = df_sales.groupby('Order #').agg({
            '수량': 'sum',
            'Total Amount': 'sum'
        }).reset_index()

        # --- [ERP(Book) 데이터 전처리] ---
        df_erp = df_erp.dropna(subset=['Order Number'])
        df_erp['Order Number'] = df_erp['Order Number'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        df_erp['Quantity'] = pd.to_numeric(df_erp['Quantity'], errors='coerce').fillna(0)
        
        erp_grouped = df_erp.groupby('Order Number').agg({
            'Quantity': 'sum',
            'Extended Amount': 'sum'
        }).reset_index()

        # --- [데이터 병합 및 비교] ---
        merged = pd.merge(sales_grouped, erp_grouped, left_on='Order #', right_on='Order Number', how='outer').fillna(0)

        # 수량 차이 및 금액 차이(10원 단위 절사 비교) 계산
        merged['수량차이'] = merged['수량'] - merged['Quantity']
        merged['Sales_10원절사'] = (merged['Total Amount'] // 10) * 10
        merged['ERP_10원절사'] = (merged['Extended Amount'] // 10) * 10
        merged['금액차이_실제'] = merged['Total Amount'] - merged['Extended Amount']

        def check_status(row):
            if abs(row['수량차이']) > 0: # 수량이 단 1개라도 다르면 불일치
                return "❌ 수량 불일치"
            if abs(row['금액차이_실제']) < 1:
                return "✅ 완전 일치"
            if row['Sales_10원절사'] == row['ERP_10원절사']:
                return "⚠️ 단가 미세오차(정상)"
            return "❌ 금액 불일치"

        merged['비교결과'] = merged.apply(check_status, axis=1)

        # 결과 리스트 분리
        mismatch = merged[merged['비교결과'].str.contains("❌")].copy()
        minor_errors = merged[merged['비교결과'] == "⚠️ 단가 미세오차(정상)"].copy()

        # --- [결과 표시] ---
        st.subheader("✅ 검증 결과 요약")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 오더 수", len(merged))
        c2.metric("완전 일치", len(merged[merged['비교결과']=="✅ 완전 일치"]))
        c3.metric("단가 오차(허용)", len(minor_errors))
        c4.metric("실제 불일치", len(mismatch), delta_color="inverse")

        if not mismatch.empty:
            st.error(f"🚩 확인 필요 오더: {len(mismatch)}건")
            # 305536 오더가 포함되어 있는지 여기서 바로 확인 가능합니다.
            st.dataframe(mismatch[['Order #', '수량', 'Quantity', '수량차이', 'Total Amount', 'Extended Amount', '비교결과']], use_container_width=True)
            
            csv_mismatch = mismatch.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 불일치 리스트 다운로드", csv_mismatch, "mismatch_final_report.csv")

        if mismatch.empty:
            st.success("🎉 모든 오더의 수량과 금액이 정상 범위 내에서 일치합니다!")

elif len(uploaded_files) > 0:
    st.warning("파일 2개를 모두 업로드 해주세요.")
