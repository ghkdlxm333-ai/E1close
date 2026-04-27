import streamlit as st
import pandas as pd
import numpy as np

# 페이지 설정
st.set_page_config(page_title="Sales vs ERP Recon Tool", page_icon="🗓️" , layout="wide")

st.title("📊 매출 마감 데이터 최종 검증 툴")
st.info("💡 전체 요약 결과와 함께, 수량 차이가 있는 '특정 품목'만 상세 탭에서 바로 확인하세요.")

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
        
        df_sales['단가'] = pd.to_numeric(df_sales['단가'], errors='coerce').fillna(0)
        df_sales['수량'] = pd.to_numeric(df_sales['수량'], errors='coerce').fillna(0)
        
        df_sales['단가'] = np.floor(df_sales['단가'] * 10000) / 10000
        df_sales['Total Amount'] = df_sales['단가'] * df_sales['수량']

        # [상세용] 품목별 그룹화
        sales_detail = df_sales.groupby(['Order #', '제품코드', '제품명']).agg({'수량': 'sum'}).reset_index()
        # [요약용] 오더별 그룹화
        sales_summary = df_sales.groupby('Order #').agg({'수량': 'sum', 'Total Amount': 'sum'}).reset_index()

        # --- [ERP(Book) 전처리] ---
        df_erp = df_erp.dropna(subset=['Order Number'])
        df_erp['Order Number'] = df_erp['Order Number'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        df_erp['Quantity'] = pd.to_numeric(df_erp['Quantity'], errors='coerce').fillna(0)
        df_erp['Extended Amount'] = pd.to_numeric(df_erp['Extended Amount'], errors='coerce').fillna(0)
        
        # [상세용] 품목별 그룹화 (ME코드 기준)
        erp_detail = df_erp.groupby(['Order Number', '2nd Item Number']).agg({'Quantity': 'sum'}).reset_index()
        # [요약용] 오더별 그룹화
        erp_summary = df_erp.groupby('Order Number').agg({'Quantity': 'sum', 'Extended Amount': 'sum'}).reset_index()

        # --- [데이터 병합 및 비교] ---
        merged_summary = pd.merge(sales_summary, erp_summary, left_on='Order #', right_on='Order Number', how='outer').fillna(0)
        merged_summary['수량차이'] = merged_summary['수량'] - merged_summary['Quantity']
        merged_summary['금액차이_실제'] = merged_summary['Total Amount'] - merged_summary['Extended Amount']

        def check_status(row):
            if row['수량차이'] != 0: return "❌ 수량 불일치"
            if abs(row['금액차이_실제']) < 1: return "✅ 완전 일치"
            if (row['Total Amount'] // 10) == (row['Extended Amount'] // 10): return "⚠️ 단가 미세오차(정상)"
            return "❌ 금액 불일치"

        merged_summary['비교결과'] = merged_summary.apply(check_status, axis=1)

        # --- [화면 표시 1: 기존 상단 요약창 유지] ---
        st.subheader("✅ 검증 요약")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 오더 수", len(merged_summary))
        c2.metric("완전 일치", len(merged_summary[merged_summary['비교결과']=="✅ 완전 일치"]))
        c3.metric("단가 미세오차(정상)", len(merged_summary[merged_summary['비교결과']=="⚠️ 단가 미세오차(정상)"]))
        c4.metric("불일치 오더", len(merged_summary[merged_summary['비교결과'].str.contains("❌")]), delta_color="inverse")

        # --- [화면 표시 2: 불일치 오더 요약 리스트 유지] ---
        mismatch = merged_summary[merged_summary['비교결과'].str.contains("❌")].copy()
        if not mismatch.empty:
            st.error(f"🚩 확인 필요 오더: {len(mismatch)}건")
            st.dataframe(mismatch[['Order #', '수량', 'Quantity', '수량차이', 'Total Amount', 'Extended Amount', '비교결과']], use_container_width=True)

        # --- [화면 표시 3: 수량 차이 '품목'만 보여주는 상세 탭] ---
        # 1. 상세 레벨 병합 (Order + Product)
        detail_comp = pd.merge(
            sales_detail, 
            erp_detail, 
            left_on=['Order #', '제품코드'], 
            right_on=['Order Number', '2nd Item Number'], 
            how='outer'
        ).fillna(0)
        
        # 2. 수량 차이가 실제로 발생한 품목만 필터링
        detail_comp['수량차이'] = detail_comp['수량'] - detail_comp['Quantity']
        item_mismatch = detail_comp[detail_comp['수량차이'] != 0].copy()

        if not item_mismatch.empty:
            with st.expander("🔍 [상세] 수량 차이 발생 품목 리스트 (틀린 ME코드만 보기)"):
                # 열 이름 정리 및 출력
                # Order Number가 0인 경우(ERP에만 있는 경우)를 위해 정규화
                item_mismatch['오더넘버'] = item_mismatch['Order #'].where(item_mismatch['Order #'] != 0, item_mismatch['Order Number'])
                item_mismatch['ME코드'] = item_mismatch['제품코드'].where(item_mismatch['제품코드'] != 0, item_mismatch['2nd Item Number'])
                
                display_table = item_mismatch[['오더넘버', 'ME코드', '제품명', 'Quantity', '수량', '수량차이']]
                display_table.columns = ['오더넘버', 'ME코드', '상품명', 'E1수량(ERP)', '세일즈수량', '수량차이']
                
                # 가독성을 위해 수량차이 순으로 정렬
                display_table = display_table.sort_values(by='수량차이', ascending=False)
                
                st.dataframe(display_table.style.format(precision=0), use_container_width=True)
                
                csv_detail = display_table.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 수량 불일치 상세 내역 다운로드", csv_detail, "item_mismatch_detail.csv")

        # --- [기타 오차 확인 창] ---
        minor_errors = merged_summary[merged_summary['비교결과'] == "⚠️ 단가 미세오차(정상)"]
        if not minor_errors.empty:
            with st.expander("🔍 단가 소수점 미세 오차 오더 확인"):
                st.dataframe(minor_errors[['Order #', 'Total Amount', 'Extended Amount', '금액차이_실제']], use_container_width=True)

        if mismatch.empty:
            st.success("🎉 모든 데이터가 일치합니다!")

elif len(uploaded_files) > 0:
    st.warning("Sales Report와 Book1 파일 2개를 모두 업로드 해주세요.")
