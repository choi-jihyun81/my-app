import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(page_title="학교 시설물 외관조사망도 간편 작성기", layout="wide")

st.title("🏫 학교 시설물 외관조사망도 간편 작성기")
st.caption("스마트폰/태블릿 현장점검용 모바일 웹 앱")

# 세션 상태 초기화
if "defects" not in st.session_state:
    st.session_state.defects = []

st.header("1. 도면 업로드")
bg_image_file = st.file_uploader("📂 평면도 이미지(JPG/PNG) 업로드", type=["png", "jpg", "jpeg"])

if bg_image_file:
    # 이미지를 RGB 모드로 변환하여 색상 마킹 에러(ValueError) 방지
    image = Image.open(bg_image_file).convert("RGB")
    img_w, img_h = image.size

    current_no = len(st.session_state.defects) + 1

    st.header(f"2. NO.{current_no} 결함 정보 입력 및 위치 지정")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("👇 도면 위를 직접 터치/클릭하세요")
        display_width = 600
        coords = streamlit_image_coordinates(image, width=display_width, key=f"coords_{current_no}")

        x_pos, y_pos = None, None
        if coords:
            scale = img_w / display_width
            x_pos = int(coords["x"] * scale)
            y_pos = int(coords["y"] * scale)
            st.success(f"📍 선택된 위치 좌표: X={x_pos}px, Y={y_pos}px")
        else:
            st.info("도면 이미지 위를 직접 터치하면 위치 좌표가 자동으로 수집됩니다.")

    with col2:
        defect_type = st.selectbox(
            "결함 종류",
            ["균열 (Crack)", "누수/습기 (Leak)", "박리/박락 (Spalling)", "철근노출 (Rebar Expose)", "기타 (Other)"],
            key=f"type_{current_no}"
        )
        defect_detail = st.text_input("결함 상세 설명", placeholder="예: 4층 계단실 벽체 2.0*2.0", key=f"detail_{current_no}")
        
        photo_file = st.file_uploader("📸 현장 결함 사진 촬영/첨부", type=["png", "jpg", "jpeg"], key=f"photo_{current_no}")

        if st.button(f"✅ NO.{current_no} 결함 추가하기", use_container_width=True):
            if x_pos is None or y_pos is None:
                st.warning("도면 위를 터치하여 위치를 지정해 주세요!")
            else:
                st.session_state.defects.append({
                    "NO": current_no,
                    "종류": defect_type,
                    "내용": defect_detail,
                    "X": x_pos,
                    "Y": y_pos,
                    "사진": photo_file
                })
                st.success(f"NO.{current_no} 결함이 외관조사망도에 등록되었습니다!")
                st.rerun()

    st.divider()
    st.header("3. 완성된 외관조사망도 및 결함 목록")

    if st.session_state.defects:
        marked_image = image.copy()
        draw = ImageDraw.Draw(marked_image)
        
        for item in st.session_state.defects:
            x, y = item["X"], item["Y"]
            radius = int(max(img_w, img_h) * 0.018)
            # 빨간 원 마킹 및 노란색 테두리
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="red", outline="yellow", width=3)
            # 결함 번호 표시
            draw.text((x + radius + 4, y - radius), str(item["NO"]), fill="red")

        st.subheader("📌 마킹 반영된 외관조사망도")
        st.image(marked_image, use_container_width=True)

        st.subheader("📋 결함 목록")
        df = pd.DataFrame(st.session_state.defects)[["NO", "종류", "내용", "X", "Y"]]
        st.dataframe(df, use_container_width=True)
