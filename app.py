import streamlit as st
import pandas as pd
import re
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(page_title="학교 시설물 조사망도 및 물량표 작성기", layout="wide")

st.title("🏫 학교 시설물 조사망도 및 물량표 작성기")
st.caption("층별 도면 관리 및 표준 손상물량표 자동 생성 모바일 웹 앱")

# 세션 상태 초기화
if "floors" not in st.session_state:
    st.session_state.floors = {}

# 수정 모드 상태 관리 (어떤 층의 몇 번째 항목을 수정 중인지 저장)
if "editing_target" not in st.session_state:
    st.session_state.editing_target = None  # 형식: {"floor": 층이름, "index": 인덱스}

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
    st.header("2. 층 선택 및 점검 내용 입력 / 위치 수정")
    
    sorted_floor_names = sorted(list(st.session_state.floors.keys()), key=get_floor_level, reverse=True)
    tabs = st.tabs(sorted_floor_names)

    for idx, selected_floor in enumerate(sorted_floor_names):
        with tabs[idx]:
            current_floor_data = st.session_state.floors[selected_floor]
            floor_img = current_floor_data["image"]
            img_w, img_h = floor_img.size

            # 💡 만약 특정 항목의 위치 수정 모드 중이라면 해당 항목 편집 화면 제공
            is_modifying = False
            mod_item = None
            mod_index = -1
            if st.session_state.editing_target and st.session_state.editing_target["floor"] == selected_floor:
                is_modifying = True
                mod_index = st.session_state.editing_target["index"]
                mod_item = current_floor_data["defects"][mod_index]

            if is_modifying:
                st.info(f"✏️ [{selected_floor}] **{mod_item['발생위치']} ({mod_item['부재']} - {mod_item['유형 및 형상']})**의 위치를 수정 중입니다. 아래 도면에서 새 위치를 터치해 주세요.")
                
                display_width = 600
                coords = streamlit_image_coordinates(floor_img, width=display_width, key=f"mod_coords_{selected_floor}_{mod_index}")

                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    if st.button("❌ 위치 수정 취소", use_container_width=True):
                        st.session_state.editing_target = None
                        st.rerun()
                with col_m2:
                    if st.button("💾 새 위치로 저장", type="primary", use_container_width=True):
                        if coords:
                            scale = img_w / display_width
                            mod_item["X"] = int(coords["x"] * scale)
                            mod_item["Y"] = int(coords["y"] * scale)
                            st.success("위치가 성공적으로 변경되었습니다!")
                            st.session_state.editing_target = None
                            st.rerun()
                        else:
                            st.warning("도면 위에서 새로운 위치를 터치해 주세요.")
                
                st.divider()
                st.markdown("### 📋 등록된 손상 항목 목록 (위치 수정용)")
            
            # 일반 신규 등록 모드
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
                    crack_w_options = ["-", "0.1", "0.2", "0.3", "0.4", "0.5 이상"]
                    crack_l_options = ["-", "0.2", "0.4", "0.6", "0.8", "1.0", "1.2", "1.4", "1.6", "1.8", "2.0 이상"]
                    dimension_options = ["-", "0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "1.0", "1.2", "1.4", "1.6", "1.8", "2.0"]

                    crack_w = st.selectbox("균열폭 (mm)", crack_w_options, key=f"cw_{selected_floor}_{floor_defect_no}")
                    crack_l = st.selectbox("균열길이 (m)", crack_l_options, key=f"cl_{selected_floor}_{floor_defect_no}")
                    dmg_w = st.selectbox("손상가로 (m)", dimension_options, key=f"dw_{selected_floor}_{floor_defect_no}")
                    dmg_h = st.selectbox("손상세로 (m)", dimension_options, key=f"dh_{selected_floor}_{floor_defect_no}")

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
                            "균열폭(mm)": crack_w,
                            "균열길이(m)": crack_l,
                            "손상가로(m)": dmg_w,
                            "손상세로(m)": dmg_h,
                            "개소": cnt,
                            "손상원인": cause,
                            "X": x_pos,
                            "Y": y_pos,
                            "사진": photo_file
                        }
                        current_floor_data["defects"].append(item)
                        st.success(f"[{selected_floor}] {circle_num}번 손상 항목이 등록되었습니다.")
                        st.rerun()

            # 💡 등록된 항목별로 위치를 바로 수정할 수 있는 관리 목록 추가
            if current_floor_data["defects"]:
                st.markdown("---")
                st.markdown(f"#### 📌 [{selected_floor}] 등록된 손상 항목 위치 관리")
                for d_idx, d_item in enumerate(current_floor_data["defects"]):
                    col_item1, col_item2, col_item3 = st.columns([2, 3, 2])
                    with col_item1:
                        st.markdown(f"**{d_item['발생위치']}번 (사진 {d_item['사진번호']})**")
                    with col_item2:
                        st.markdown(f"{d_item['위치']} / {d_item['부재']} / {d_item['유형 및 형상']}")
                    with col_item3:
                        if st.button(f"📍 위치 수정", key=f"edit_pos_{selected_floor}_{d_idx}"):
                            st.session_state.editing_target = {"floor": selected_floor, "index": d_idx}
                            st.rerun()

    st.divider()
    st.header("3. 완성된 조사망도 및 전체 손상물량표 확인")

    view_floor = st.selectbox("마킹 도면 조회할 층 선택", sorted_floor_names, key="view_floor_select")

    # 점 크기와 번호 동그라미 크기 조절 슬라이더
    c_s1, c_s2 = st.columns(2)
    with c_s1:
        size_ratio = st.slider("📍 손상점 크기 조절", min_value=1, max_value=20, value=6)
    with c_s2:
        circle_scale_ratio = st.slider("🔤 번호 동그라미 크기 조절 (숫자 함께 연동)", min_value=1, max_value=20, value=10)

    view_floor_data = st.session_state.floors[view_floor]
    marked_image = view_floor_data["image"].copy()
    draw = ImageDraw.Draw(marked_image)

    # 도면 해상도 비례 기준 적용
    img_max_dim = max(view_floor_data["image"].size)
    dot_radius = max(3, int(img_max_dim * (size_ratio / 1200.0)))
    circle_radius = max(8, int(img_max_dim * (circle_scale_ratio / 400.0)))

    try:
        font = ImageFont.load_default()
    except:
        font = None

    for item in view_floor_data["defects"]:
        x, y = item["X"], item["Y"]
        num_str = str(item["층내번호"])
        
        # 1. 실제 손상 위치 점 (작은 빨간 점)
        draw.ellipse((x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius), fill="red", outline="red")
        
        # 2. 번호 동그라미 위치 (손상점에서 우측 상단으로 분리 배치)
        offset_x = int(circle_radius * 1.8)
        offset_y = -int(circle_radius * 1.8)
        txt_center_x = x + offset_x
        txt_center_y = y + offset_y
        
        # 3. 손상점과 번호 동그라미를 연결하는 인출선(지시선)
        draw.line([(x, y), (txt_center_x, txt_center_y)], fill="red", width=max(1, dot_radius // 2))
        
        # 4. 숫자와 주변 동그라미가 일체화된 레이블 뱃지
        draw.ellipse((txt_center_x - circle_radius, txt_center_y - circle_radius, txt_center_x + circle_radius, txt_center_y + circle_radius), fill="white", outline="red", width=max(1, circle_radius // 8))
        
        # 5. 숫자 중앙 정렬 렌더링
        text_offset_x = int(circle_radius * 0.35)
        text_offset_y = int(circle_radius * 0.55)
        draw.text((txt_center_x - text_offset_x, txt_center_y - text_offset_y), num_str, fill="red", font=font)
        if circle_radius > 15:
            draw.text((txt_center_x - text_offset_x + 1, txt_center_y - text_offset_y), num_str, fill="red", font=font)

    st.subheader(f"📌 [{view_floor}] 마킹 반영 외관조사망도")
    st.image(marked_image, use_container_width=True)

    buffered = BytesIO()
    marked_image.save(buffered, format="PNG")
    st.download_button(
        label=f"💾 [{view_floor}] 마킹 도면 이미지 저장하기",
        data=buffered.getvalue(),
        file_name=f"외관조사망도_{view_floor}.png",
        mime="image/png",
        use_container_width=True
    )

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
