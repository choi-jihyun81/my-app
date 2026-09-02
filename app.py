import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import io

st.set_page_config(page_title="학교 시설물 외관조사망도 간편 작성기", layout="wide")

st.title("🏫 학교 시설물 외관조사망도 간편 작성기")
st.caption("스마트폰/태블릿 현장점검용 모바일 웹 앱")

# 세션 상태 초기화
if "defects" not in st.session_state:
    st.session_state.defects = []

st.header("1. 도면 및 현장 사진 등록")
bg_image_file = st.file_uploader("📂 평면도 이미지(JPG/PNG) 업로드", type=["png", "jpg", "jpeg"])

if bg_image_file:
    image = Image.open(bg_image_file)
    img_w, img_h = image.size
    
    st.header("2. 결함 정보 입력 및 위치 지정")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        defect_type = st.selectbox(
            "결함 종류 선택",
            ["균열 (Crack)", "누수/습기 (Leak)", "박리/박락 (Spalling)", "철근노출 (Rebar Expose)", "기타 (Other)"]
        )
        defect_detail = st.text_input("결함 상세 설명", placeholder="예: 4층 복도 보 균열 0.2mm")
        photo_file = st.file_uploader("📷 현장 결함 사진 촬영/첨부", type=["png", "jpg", "jpeg"])

        st.subheader("📍 도면 위치 지정 (비율 %)")
        x_pct = st.number_input("가로 위치 (좌側 0% ~ 우側 100%)", min_value=0.0, max_value=100.0, value=50.0, step=1.0)
        y_pct = st.number_input("세로 위치 (상側 0% ~ 하側 100%)", min_value=0.0, max_value=100.0, value=50.0, step=1.0)

        # 퍼센트를 실제 이미지 좌표(pixel)로 계산
        x_pos = int(img_w * (x_pct / 100.0))
        y_pos = int(img_h * (y_pct / 100.0))

        if st.button("➕ 결함 목록에 추가"):
            defect_no = len(st.session_state.defects) + 1
            st.session_state.defects.append({
                "NO": defect_no,
                "종류": defect_type,
                "내용": defect_detail,
                "X": x_pos,
                "Y": y_pos,
                "X_pct": x_pct,
                "Y_pct": y_pct,
                "사진": photo_file
            })
            st.success(f"NO.{defect_no} 결함이 추가되었습니다!")

    with col2:
        st.subheader("🖼️ 업로드된 도면")
        st.image(image, use_column_width=True)

    st.divider()
    st.header("3. 외관조사망도 및 결함 목록 확인")

    if st.session_state.defects:
        marked_image = image.copy()
        draw = ImageDraw.Draw(marked_image)
        
        for item in st.session_state.defects:
            x, y = item["X"], item["Y"]
            radius = int(max(img_w, img_h) * 0.015)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="red", outline="yellow", width=2)
            draw.text((x + radius + 4, y - radius), str(item["NO"]), fill="red")

        st.subheader("📌 마킹 반영된 외관조사망도")
        st.image(marked_image, use_column_width=True)

        st.subheader("📋 결함 목록")
        df = pd.DataFrame(st.session_state.defects)[["NO", "종류", "내용", "X_pct", "Y_pct"]]
        df.columns = ["NO", "종류", "내용", "가로위치(%)", "세로위치(%)"]
        st.dataframe(df, use_container_width=True)
