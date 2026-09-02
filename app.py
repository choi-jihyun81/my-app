import streamlit as st
import pandas as pd
import re
from PIL import Image, ImageDraw
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(page_title="학교 시설물 조사망도 및 물량표 작성기", layout="wide")

st.title("🏫 학교 시설물 조사망도 및 물량표 작성기")
st.caption("층별 도면 관리 및 표준 손상물량표 자동 생성 모바일 웹 앱")

# 세션 상태 초기화
if "floors" not in st.session_state:
    st.session_state.floors = {}

# 층 정렬을 위한 헬퍼 함수 (옥상 -> 높은 숫자, 지하 -> 음수)
def get_floor_level(f_name):
    if "옥상" in f_name:
        return 999
    if "지하" in f_name:
        nums = re.findall(r'\d+', f_name)
        return -int(nums[0]) if nums else -1
    nums = re.findall(r'\d+', f_name)
    return int(nums[0]) if nums else 0

st.header("1. 층별 도면 관리 (섹터 등록)")
col_f1, col_f2 = st.columns([1, 2])

with col_f1:
    floor_name_input = st.text_input("층/섹터 이름 입력", placeholder="예: 1층, 2층, 옥상층, 지하1층")
    uploaded_floor_img = st.file_uploader("📂 해당 층 도면 업로드(JPG/PNG)", type=["png", "jpg", "jpeg"])
    
    if st.button("➕ 층 도면 추가/갱신", use_container_width=True):
        if floor_name_input and uploaded_floor_img:
            img = Image.open(uploaded_floor_img).convert("RGB")
            if floor_name_input not in st.session_state.floors:
                st.session_state.floors[floor_name_input] = {"image": img, "defects": []}
            else:
                st.session_state.floors[floor_name_input]["image"] = img
            st.success(f"'{floor_name_input}' 도면이 등록되었습니다.")
            st.rerun()
        else:
            st.warning("층 이름과 도면 이미지를 모두 등록해 주세요.")

if st.session_state.floors:
    st.divider()
    st.header("2. 층 선택 및 점검 내용 입력")
    
    sorted_floor_names = sorted(list(st.session_state.floors.keys()), key=get_floor_level, reverse=True)
    tabs = st.tabs(sorted_floor_names)

    for idx, selected_floor in enumerate(sorted_floor_names):
        with tabs[idx]:
            current_floor_data = st.session_state.floors[selected_floor]
            floor_img = current_floor_data["image"]
            img_w, img_h = floor_img.size

            # 1. 각 층별로 1번부터 자동 생성되는 번호 계산
            floor_defect_no = len(current_floor_data["defects"]) + 1
            circle_num = chr(9311 + floor_defect_no) if floor_defect_no <= 15 else f"({floor_defect_no})"

            col_left, col_right = st.columns([1, 1])

            with col_left:
                st.subheader(f"👇 [{selected_floor}] 도면 위 손상 위치 터치 (다음 등록: {circle_num})")
                display_width = 600
                coords = streamlit_image_coordinates(floor_img, width=display_width, key=f"coords_{selected_floor}_{floor_defect_no}")

                x_pos, y_pos = None, None
                if coords:
                    scale = img_w / display_width
                    x_pos = int(coords["x"] * scale)
                    y_pos = int(coords["y"] * scale)
                    st.success(f"📍 선택 좌표: X={x_pos}px, Y={y_pos}px")
                else:
                    st.info("도면 위 손상 위치를 직접 터치해 주세요.")

            with col_right:
                st.subheader("📋 손상 상세 정보 입력")
                
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    loc_opt = st.selectbox("위치", ["교실", "복도", "계단실", "화장실", "교무/행정실", "외벽", "옥상", "직접 입력"], key=f"loc_opt_{selected_floor}_{floor_defect_no}")
                    if loc_opt == "직접 입력":
                        loc_detail = st.text_input("위치 직접 입력", placeholder="예: E/V실, 식당", key=f"loc_custom_{selected_floor}_{floor_defect_no}")
                    else:
                        loc_detail = loc_opt
                    
                    element_opt = st.selectbox("부재", ["벽체", "기둥", "보", "슬래브", "계단", "직접 입력"], key=f"elem_opt_{selected_floor}_{floor_defect_no}")
                    if element_opt == "직접 입력":
                        element = st.text_input("부재 명칭 입력", placeholder="예: 난간, 옹벽", key=f"elem_custom_{selected_floor}_{floor_defect_no}")
                    else:
                        element = element_opt

                    defect_type_opt = st.selectbox("유형 및 형상", ["균열", "누수/습기", "박리/박락", "철근노출", "백화", "직접 입력"], key=f"type_opt_{selected_floor}_{floor_defect_no}")
                    if defect_type_opt == "직접 입력":
                        defect_type = st.text_input("유형 및 형상 입력", placeholder="예: 재료분리, 처짐", key=f"type_custom_{selected_floor}_{floor_defect_no}")
                    else:
                        defect_type = defect_type_opt

                    st.text_input("발생위치 기호 (해당 층 번호)", value=circle_num, disabled=True, key=f"circle_show_{selected_floor}_{floor_defect_no}")
                    photo_no = st.text_input("사진 번호", value=str(floor_defect_no), key=f"pno_{selected_floor}_{floor_defect_no}")
                    
                with col_r2:
                    crack_w = st.text_input("균열폭 (mm)", value="", placeholder="미입력시 -", key=f"cw_{selected_floor}_{floor_defect_no}")
                    crack_l = st.text_input("균열길이 (m)", value="", placeholder="미입력시 -", key=f"cl_{selected_floor}_{floor_defect_no}")
                    dmg_w = st.text_input("손상가로 (m)", value="", placeholder="미입력시 -", key=f"dw_{selected_floor}_{floor_defect_no}")
                    dmg_h = st.text_input("손상세로 (m)", value="", placeholder="미입력시 -", key=f"dh_{selected_floor}_{floor_defect_no}")

                col_r3, col_r4 = st.columns(2)
                with col_r3:
                    cnt = st.number_input("개소", min_value=1, value=1, step=1, key=f"cnt_{selected_floor}_{floor_defect_no}")
                with col_r4:
                    cause_opt = st.selectbox("손상원인", ["건조수축", "구조적 부하", "시공부실", "도막 노화", "진동/충격", "습기/침수", "자연 연화", "직접 입력"], key=f"cause_opt_{selected_floor}_{floor_defect_no}")
                    if cause_opt == "직접 입력":
                        cause = st.text_input("손상원인 입력", placeholder="예: 외부 충격", key=f"cause_custom_{selected_floor}_{floor_defect_no}")
                    else:
                        cause = cause_opt

                photo_file = st.file_uploader("📸 현장 사진 첨부", type=["png", "jpg", "jpeg"], key=f"photo_{selected_floor}_{floor_defect_no}")

                if st.button(f"✅ [{selected_floor}] 손상 항목 추가 ({circle_num})", use_container_width=True, key=f"btn_{selected_floor}_{floor_defect_no}"):
                    if x_pos is None or y_pos is None:
                        st.warning("도면 위를 터치하여 위치를 먼저 지정해 주세요.")
                    elif not element or not defect_type or not cause:
                        st.warning("부재, 유형 및 손상원인 항목을 입력해 주세요.")
                    else:
                        item = {
                            "층": selected_floor,
                            "층내번호": floor_defect_no,
                            "발생위치": circle_num,
                            "사진번호": photo_no,
                            "위치": loc_detail,
                            "부재": element,
                            "유형 및 형상": defect_type,
                            "균열폭(mm)": crack_w.strip() if crack_w.strip() else "-",
                            "균열길이(m)": crack_l.strip() if crack_l.strip() else "-",
                            "손상가로(m)": dmg_w.strip() if dmg_w.strip() else "-",
                            "손상세로(m)": dmg_h.strip() if dmg_h.strip() else "-",
                            "개소": cnt,
                            "손상원인": cause,
                            "X": x_pos,
                            "Y": y_pos,
                            "사진": photo_file
                        }
                        current_floor_data["defects"].append(item)
                        st.success(f"[{selected_floor}] {circle_num}번 손상 항목이 등록되었습니다.")
                        st.rerun()

    st.divider()
    st.header("3. 완성된 조사망도 및 전체 손상물량표")

    view_col1, view_col2 = st.columns([2, 1])
    with view_col1:
        view_floor = st.selectbox("마킹 도면 조회할 층 선택", sorted_floor_names, key="view_floor_select")
    with view_col2:
        # 2. 점 크기 선택 옵션 추가
        mark_size = st.radio("📍 도면 마킹 점/번호 크기", ["작게 (소)", "보통 (중)", "크게 (대)"], index=1, horizontal=True)

    # 선택된 크기에 따른 반지름 배율 적용
    if mark_size == "작게 (소)":
        scale_factor = 0.005
    elif mark_size == "보통 (중)":
        scale_factor = 0.009
    else:
        scale_factor = 0.014

    view_floor_data = st.session_state.floors[view_floor]
    marked_image = view_floor_data["image"].copy()
    draw = ImageDraw.Draw(marked_image)
    
    img_max_dim = max(view_floor_data["image"].size)
    radius = max(8, int(img_max_dim * scale_factor))

    for item in view_floor_data["defects"]:
        x, y = item["X"], item["Y"]
        num_str = str(item["층내번호"])
        
        # 빨간 점 마킹
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="red", outline="red")
        
        # 흰색 배경 원 및 빨간 번호 표시 (시인성 확보)
        txt_x, txt_y = x + radius + (radius // 2), y
        draw.ellipse((txt_x - radius, txt_y - radius, txt_x + radius, txt_y + radius), fill="white", outline="red", width=2)
        draw.text((txt_x - (radius // 3), txt_y - (radius // 2)), num_str, fill="red")

    st.subheader(f"📌 [{view_floor}] 마킹 반영 외관조사망도")
    st.image(marked_image, use_container_width=True)

    # 전체 데이터 모으기 (층별 옥상->아래층 순서 정렬)
    all_defects_sorted = []
    for f_name in sorted_floor_names:
        for defect in st.session_state.floors[f_name]["defects"]:
            all_defects_sorted.append(defect)

    if all_defects_sorted:
        st.subheader("📊 전체 건축물 손상물량표 (층별 1번부터 시작)")
        df_display = pd.DataFrame(all_defects_sorted)[[
            "층", "발생위치", "사진번호", "위치", "부재", "유형 및 형상",
            "균열폭(mm)", "균열길이(m)", "손상가로(m)", "손상세로(m)", "개소", "손상원인"
        ]]
        st.dataframe(df_display, use_container_width=True)

        st.divider()
        st.subheader("📷 첨부된 손상 사진 갤러리")
        photo_items = [item for item in all_defects_sorted if item.get("사진") is not None]
        
        if photo_items:
            cols = st.columns(3)
            for idx, p_item in enumerate(photo_items):
                with cols[idx % 3]:
                    st.image(p_item["사진"], caption=f"[{p_item['층']}] {p_item['발생위치']} (사진 {p_item['사진번호']}) - {p_item['위치']}", use_container_width=True)
        else:
            st.info("첨부된 사진이 없습니다.")
