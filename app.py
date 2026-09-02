import streamlit as st
from PIL import Image, ImageDraw
import io

# 1. 모바일 레이아웃 설정
st.set_page_config(
    page_title="학교 시설물 현장 점검 앱",
    page_icon="🏫",
    layout="centered"
)

st.title("🏫 학교 시설물 외관조사망도 간편 작성기")
st.caption("스마트폰 현장점검용 모바일 웹 앱")

# 세션 상태 초기화
if "defects" not in st.session_state:
    st.session_state["defects"] = []
if "tag_count" not in st.session_state:
    st.session_state["tag_count"] = 1

# 2. 파일 업로드 섹션
st.subheader("1. 도면 및 현장 사진 등록")
bg_file = st.file_uploader("📂 평면도 이미지(JPG/PNG) 업로드", type=["jpg", "jpeg", "png"])

if bg_file:
    orig_img = Image.open(bg_file).convert("RGB")
    img_w, img_h = orig_img.size

    st.subheader("2. 결함 정보 입력 및 위치 지정")
    
    # 결함 입력 폼
    defect_type = st.selectbox("결함 종류 선택", ["🔴 균열 (Crack)", "🔵 누수/습기 (Leak)", "🟠 마감/기타 손상 (Damage)"])
    defect_desc = st.text_input("결함 상세 설명 (예: 4층 복도 보 균열 0.2mm)", "")
    
    # 위치 좌표 입력 (모바일 터치 보완용 슬라이더)
    st.write("📍 도면 상의 위치 지정 (비율 %)")
    col1, col2 = st.columns(2)
    with col1:
        x_ratio = st.slider("가로 위치 (X %)", 0, 100, 50)
    with col2:
        y_ratio = st.slider("세로 위치 (Y %)", 0, 100, 50)
        
    # 현장 사진 첨부 (스마트폰 카메라 연동)
    photo_file = st.file_uploader("📷 현장 결함 사진 촬영/첨부", type=["jpg", "png", "jpeg"], key="photo")

    if st.button("➕ 결함 목록에 추가"):
        tag_id = f"NO.{st.session_state['tag_count']}"
        st.session_state["defects"].append({
            "id": tag_id,
            "type": defect_type,
            "desc": defect_desc,
            "x": int(img_w * (x_ratio / 100)),
            "y": int(img_h * (y_ratio / 100)),
            "photo": photo_file.name if photo_file else "사진 없음"
        })
        st.session_state["tag_count"] += 1
        st.success(f"{tag_id} 결함이 추가되었습니다!")

    # 3. 도면 및 목록 실시간 렌더링
    st.divider()
    st.subheader("3. 외관조사망도 및 결함 목록 확인")
    
    # 도면에 마킹 그리기
    drawn_img = orig_img.copy()
    draw = ImageDraw.Draw(drawn_img)
    
    color_dict = {
        "🔴 균열 (Crack)": "red",
        "🔵 누수/습기 (Leak)": "blue",
        "🟠 마감/기타 손상 (Damage)": "orange"
    }

    for item in st.session_state["defects"]:
        x, y = item["x"], item["y"]
        c = color_dict.get(item["type"], "red")
        
        # 반경 설정 및 그려주기
        r = int(min(img_w, img_h) * 0.02)
        draw.ellipse([x-r, y-r, x+r, y+r], fill=c, outline="white", width=2)
        draw.text((x-r//2, y-r//2), item["id"].replace("NO.", ""), fill="white")

    # 마킹 완료된 도면 표시
    st.image(drawn_img, caption="완성된 외관조사망도", use_column_width=True)

    # 집계표 출력
    if st.session_state["defects"]:
        st.write("📋 **등록된 결함 목록**")
        st.dataframe(st.session_state["defects"])

        # 이미지 다운로드 버튼
        buf = io.BytesIO()
        drawn_img.save(buf, format="PNG")
        st.download_button(
            label="💾 완성 도면 핸드폰에 저장하기",
            data=buf.getvalue(),
            file_name="school_defect_map.png",
            mime="image/png",
            use_container_width=True
        )

    # 초기화 버튼
    if st.button("🗑️ 전체 결함 목록 초기화"):
        st.session_state["defects"] = []
        st.session_state["tag_count"] = 1
        st.experimental_rerun()
