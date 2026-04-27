import streamlit as st
import pandas as pd
import numpy as np

# 페이지 설정
st.set_page_config(page_title="Sales vs ERP Recon Tool", layout="wide")

st.title("📊 매출 마감 데이터 최종 검증 툴 (품목 상세 분석)")
st.info("💡 수량 불일치 발생 시 상세 탭을 통해 어떤 품목(ME코드)이 문제인지 즉시 확인 가능합니다.")

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
        df_sales = df_sales.dropna(subset=['Order #', '수량'])
        df_sales['Order #'] = df_sales['Order #'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        df_sales = df_sales[df_sales['Order #'].str.match(r'^\d+$')]
        
        # 단가/수량 전처리 (None은 0으로)
        df_sales['단가'] = pd.to_numeric(df_sales['단가'], errors='coerce').fillna(0)
        df_sales['수량'] = pd.to_numeric(df_sales['수량'], errors='coerce').fillna(0)
        
        # 금액 계산
        df_sales['단가'] = np.floor(df_sales['단가'] * 10000) / 10000
        df_sales['Total Amount'] = df_sales['단가'] * df_sales['수량']

        # 오더별/품목별 그룹화 (상세 분석용)
        sales_detail = df_sales.groupby(['Order #', '제품코드', '제품명']).agg({
            '수량': 'sum'
        }).reset_index()

        # 오더별 합계 (대시보드 요약용)
        sales_summary = df_sales.groupby('Order #').agg({
            '수량': 'sum',
            'Total Amount': 'sum'
        }).reset_index()

        # --- [ERP(Book) 데이터 전처리] ---
        df_erp = df_erp.dropna(subset=['Order Number'])
        df_erp['Order Number'] = df_erp['Order Number'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        df_erp['Quantity'] = pd.to_numeric(df_erp['Quantity'], errors='coerce').fillna(0)
        df_erp['Extended Amount'] = pd.to_numeric(df_erp['Extended Amount'], errors='coerce').fillna(0)
        
        # 오더별/품목별 그룹화 (상세 분석용) - 2nd Item Number를 ME코드로 사용
        erp_detail = df_erp.groupby(['Order Number', '2nd Item Number']).agg({
            'Quantity': 'sum'
        }).reset_index()

        # 오더별 합계 (대시보드 요약용)
        erp_summary = df_erp.groupby('Order Number').agg({
            'Quantity': 'sum',
            'Extended Amount': 'sum'
        }).reset_index()

        # --- [1. 오더 기준 요약 비교] ---
        merged_summary = pd.merge(sales_summary, erp_summary, left_on='Order #', right_on='Order Number', how='outer').fillna(0)
        merged_summary['수량차이'] = merged_summary['수량'] - merged_summary['Quantity']
        merged_summary['금액차이_실제'] = merged_summary['Total Amount'] - merged_summary['Extended Amount']

        def check_status(row):
            if row['수량차이'] != 0: return "❌ 수량 불일치"
            if abs(row['금액차이_실제']) < 1: return "✅ 완전 일치"
            if (row['Total Amount'] // 10) == (row['Extended Amount'] // 10): return "⚠️ 단가 미세오차(정상)"
            return "❌ 금액 불일치"

        merged_summary['비교결과'] = merged_summary.apply(check_status, axis=1)

        # --- [2. 품목별 상세 비교 데이터 생성] ---
        # 수량 불일치가 있는 오더 번호 리스트 추출
        mismatch_order_ids = merged_summary[merged_summary['비교결과'] == "❌ 수량 불일치"]['Order #'].unique()
        
        # 상세 비교 테이블 병합
        detail_comparison = pd.merge(
            sales_detail, 
            erp_detail, 
            left_on=['Order #', '제품코드'], 
            right_on=['Order Number', '2nd Item Number'], 
            how='outer'
        ).fillna(0)
        
        # 수량 차이 발생 건 필터링
        detail_comparison['수량차이'] = detail_comparison['수량'] - detail_comparison['Quantity']
        detail_mismatch = detail_comparison[detail_comparison['Order #'].isin(mismatch_order_ids)].copy()

        # --- [결과 표시] ---
        st.subheader("✅ 검증 요약")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 오더 수", len(merged_summary))
        c2.metric("완전 일치", len(merged_summary[merged_summary['비교결과']=="✅ 완전 일치"]))
        c3.metric("단가 미세오차(허용)", len(merged_summary[merged_summary['비교결과']=="⚠️ 단가 미세오차(정상)"]))
        c4.metric("실제 불일치", len(merged_summary[merged_summary['비교결과'].str.contains("❌")]), delta_color="inverse")

        # 🚩 1. 수량 불일치 상세 탭 (요청하신 기능)
        if not detail_mismatch.empty:
            st.error("🚩 수량 불일치가 발견되었습니다. 아래 탭을 열어 상세 품목을 확인하세요.")
            with st.expander("🔍 수량 불일치 오더 상세 내역 (품목별 확인)"):
                # 열 순서 조정: 오더넘버, ME코드, 상품명, E1수량, 세일즈수량, 수량차이
                display_detail = detail_mismatch[['Order #', '제품코드', '제품명', 'Quantity', '수량', '수량차이']]
                display_detail.columns = ['오더넘버', 'ME코드', '상품명', 'E1수량', '세일즈수량', '수량차이']
                
                st.dataframe(display_detail.style.format(precision=0), use_container_width=True)
                
                csv_detail = display_detail.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 수량 불일치 상세 다운로드", csv_detail, "quantity_mismatch_detail.csv")

        # 🚩 2. 금액 불일치 오더
        mismatch_amt = merged_summary[merged_summary['비교결과'] == "❌ 금액 불일치"]
        if not mismatch_amt.empty:
            with st.expander("💸 금액 불일치 오더 확인"):
                st.dataframe(mismatch_amt[['Order #', 'Total Amount', 'Extended Amount', '금액차이_실제']], use_container_width=True)

        # ✅ 3. 정상 미세오차 탭
        minor_errors = merged_summary[merged_summary['비교결과'] == "⚠️ 단가 미세오차(정상)"]
        if not minor_errors.empty:
            with st.expander("🔍 단가 소수점 차이가 발생한 오더 확인 (정상 처리됨)"):
                st.dataframe(minor_errors[['Order #', 'Total Amount', 'Extended Amount', '금액차이_실제']], use_container_width=True)

        if len(merged_summary[merged_summary['비교결과'].str.contains("❌")]) == 0:
            st.success("🎉 모든 데이터가 정상 범위 내에서 일치합니다!")

elif len(uploaded_files) > 0:
    st.warning("파일 2개를 모두 올려주세요.")
