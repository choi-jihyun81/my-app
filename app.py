import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import io
from streamlit_drawable_canvas import st_canvas

st.set_page_config(page_title="학교 시설물 외관조사망도 간편 작성기", layout="wide")

st.title("🏫 학교 시설물 외관조사망도 간편 작성기")
st.caption("스마트폰/태블릿 현장점검용 모바일 웹 앱")

# 세션 상태 초기화 (결함 목록 저장용)
if "defects" not in st.session_state:
    st.session_state.defects = []

st.header("1. 도면 및 현장 사진 등록")
bg_image_file = st.file_uploader("📂 평면도 이미지(JPG/PNG) 업로드", type=["png", "jpg", "jpeg"])

if bg_image_file:
    # 도면 이미지 열기
    image = Image.open(bg_image_file)
    
    st.header("2. 결함 정보 입력 및 위치 지정")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        defect_type = st.selectbox(
            "결함 종류 선택",
            ["균열 (Crack)", "누수/습기 (Leak)", "박리/박락 (Spalling)", "철근노출 (Rebar Expose)", "기타 (Other)"]
        )
        defect_detail = st.text_input("결함 상세 설명", placeholder="예: 4층 복도 보 균열 0.2mm")
        photo_file = st.file_uploader("📷 현장 결함 사진 촬영/첨부", type=["png", "jpg", "jpeg"])

    with col2:
        st.subheader("📍 도면 위를 직접 클릭/터치하여 위치 지정")
        # 캔버스 너비 조정 (기본 이미지 크기 반영)
        canvas_width = min(image.width, 700)
        canvas_height = int(image.height * (canvas_width / image.width))
        
        # 도면 클릭용 캔버스
        canvas_result = st_canvas(
            fill_color="rgba(255, 0, 0, 0.3)",
            stroke_width=6,
            stroke_color="#FF0000",
            background_image=image.resize((canvas_width, canvas_height)),
            update_streamlit=True,
            height=canvas_height,
            width=canvas_width,
            drawing_mode="point",
            key="canvas",
        )

    # 클릭 좌표 계산
    x_pos, y_pos = None, None
    if canvas_result.json_data is not None:
        objects = canvas_result.json_data["objects"]
        if len(objects) > 0:
            last_point = objects[-1]
            # 캔버스 크기 대비 원본 이미지 크기 비율 보정
            scale_x = image.width / canvas_width
            scale_y = image.height / canvas_height
            
            x_pos = int(last_point["left"] * scale_x)
            y_pos = int(last_point["top"] * scale_y)
            st.success(f"선택된 좌표: X = {x_pos}px, Y = {y_pos}px")

    # 결함 추가 버튼
    if st.button("➕ 결함 목록에 추가"):
        if x_pos is None or y_pos is None:
            st.warning("도면 위를 클릭하여 위치를 지정해 주세요!")
        else:
            defect_no = len(st.session_state.defects) + 1
            st.session_state.defects.append({
                "NO": defect_no,
                "종류": defect_type,
                "내용": defect_detail,
                "X": x_pos,
                "Y": y_pos,
                "사진": photo_file
            })
            st.success(f"NO.{defect_no} 결함이 추가되었습니다!")

    st.divider()
    st.header("3. 외관조사망도 및 결함 목록 확인")

    if st.session_state.defects:
        # 원본 도면에 결함 위치 마킹 그리기
        marked_image = image.copy()
        draw = ImageDraw.Draw(marked_image)
        
        for item in st.session_state.defects:
            x, y = item["X"], item["Y"]
            # 빨간 원으로 위치 표시
            radius = int(max(image.width, image.height) * 0.015)  # 이미지 크기에 맞춘 원 크기
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="red", outline="yellow", width=2)
            # 번호 표시
            draw.text((x + radius + 2, y - radius), str(item["NO"]), fill="red")

        st.subheader("🖼️ 마킹된 외관조사망도")
        st.image(marked_image, use_column_width=True)

        st.subheader("📋 결함 목록")
        df = pd.DataFrame(st.session_state.defects)[["NO", "종류", "내용", "X", "Y"]]
        st.dataframe(df, use_container_width=True)
