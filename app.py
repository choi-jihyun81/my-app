import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw

st.set_page_config(page_title="학교 시설물 외관조사망도 간편 작성기", layout="wide")

st.title("🏫 학교 시설물 외관조사망도 간편 작성기")
st.caption("스마트폰/태블릿 현장점검용 모바일 웹 앱")

# 세션 상태 초기화
if "defects" not in st.session_state:
    st.session_state.defects = []

st.header("1. 도면 업로드")
bg_image_file = st.file_uploader("📂 평면도 이미지(JPG/PNG) 업로드", type=["png", "jpg", "jpeg"])

if bg_image_file:
    image = Image.open(bg_image_file)
    img_w, img_h = image.size

    st.header("2. 도면 클릭하여 결함 등록")
    st.info("👇 아래 도면에서 결함이 발생한 위치를 직접 클릭(터치)하세요.")
    
    # 도면 클릭 이벤트 (최신 Streamlit 표준 기능)
    click_event = st.image(
        image, 
        use_container_width=True, 
        on_select="rerun", 
        selection_mode="point"
    )

    # 클릭한 좌표 감지
    if click_event and "selection" in click_event and "points" in click_event["selection"]:
        points = click_event["selection"]["points"]
        if points:
            last_point = points[-1]
            x_pos = int(last_point["x"])
            y_pos = int(last_point["y"])
            
            # 다음 등록될 결함 번호
            current_no = len(st.session_state.defects) + 1

            st.divider()
            st.subheader(f"📍 NO.{current_no} 결함 정보 및 사진 등록")
            st.write(f"선택된 위치 좌표: X={x_pos}px, Y={y_pos}px")

            col1, col2 = st.columns([1, 1])
            with col1:
                defect_type = st.selectbox(
                    "결함 종류",
                    ["균열 (Crack)", "누수/습기 (Leak)", "박리/박락 (Spalling)", "철근노출 (Rebar Expose)", "기타 (Other)"],
                    key=f"type_{current_no}"
                )
                defect_detail = st.text_input("결함 상세 설명", placeholder="예: 4층 복도 보 균열 0.2mm", key=f"detail_{current_no}")

            with col2:
                # 모바일 현장 사진 찍기 / 파일 첨부
                photo_file = st.file_uploader("📸 현장 결함 사진 촬영 및 첨부", type=["png", "jpg", "jpeg"], key=f"photo_{current_no}")

            if st.button(f"✅ NO.{current_no} 결함 등록 완료", use_container_width=True):
                st.session_state.defects.append({
                    "NO": current_no,
                    "종류": defect_type,
                    "내용": defect_detail,
                    "X": x_pos,
                    "Y": y_pos,
                    "사진": photo_file
                })
                st.success(f"NO.{current_no} 결함이 외관조사망도에 등록되었습니다!")

    st.divider()
    st.header("3. 완성된 외관조사망도 및 결함 목록")

    if st.session_state.defects:
        marked_image = image.copy()
        draw = ImageDraw.Draw(marked_image)
        
        for item in st.session_state.defects:
            x, y = item["X"], item["Y"]
            radius = int(max(img_w, img_h) * 0.018)
            # 빨간 원 마킹
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="red", outline="yellow", width=3)
            # 결함 번호 표시
            draw.text((x + radius + 4, y - radius), str(item["NO"]), fill="red")

        st.subheader("🖼️ 마킹 반영된 외관조사망도")
        st.image(marked_image, use_container_width=True)

        st.subheader("📋 결함 목록")
        df = pd.DataFrame(st.session_state.defects)[["NO", "종류", "내용", "X", "Y"]]
        st.dataframe(df, use_container_width=True)
