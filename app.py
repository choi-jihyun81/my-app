import streamlit as st
import pandas as pd
import re
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from streamlit_image_coordinates import streamlit_image_coordinates

# 페이지 레이아웃 설정 (Wide 모드)
st.set_page_config(
    page_title="학교 시설물 조사망도 및 물량표 작성기", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 스마트폰 및 PC 화면 최적화 CSS (스크롤 피로도 최소화)
st.markdown("""
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
    }
    button {
        min-height: 45px !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🏫 학교 시설물 조사망도 및 물량표 작성기")
st.caption("💡 도면을 터치하면 좌표가 잡히며, 우측(또는 아래쪽) 입력 폼에서 바로 상세 정보를 등록할 수 있습니다.")

# 세션 상태 초기화 (데이터 유실 방지 및 자동 기억용)
if "floors" not in st.session_state:
    st.session_state.floors = {}

if "editing_target" not in st.session_state:
    st.session_state.editing_target = None

# 직전 입력값 기억을 위한 세션 초기화
if "last_loc" not in st.session_state:
    st.session_state.last_loc = ""
if "last_elem" not in st.session_state:
    st.session_state.last_elem = "교실"
if "last_type" not in st.session_state:
    st.session_state.last_type = "균열"
if "last_cause" not in st.session_state:
    st.session_state.last_cause = "건조수축"

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
    uploaded_floor_img = st.file_uploader("📂 해당 층 도면 업로드(JPG/PNG)", type=["png", "jpg", "jpeg"], key="floor_img_upload")
    
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
    st.header("2. 층 선택 및 스마트 진단 입력")
    
    sorted_floor_names = sorted(list(st.session_state.floors.keys()), key=get_floor_level, reverse=True)
    tabs = st.tabs(sorted_floor_names)

    for idx, selected_floor in enumerate(sorted_floor_names):
        with tabs[idx]:
            current_floor_data = st.session_state.floors[selected_floor]
            floor_img = current_floor_data["image"]
            img_w, img_h = floor_img.size

            is_modifying = False
            mod_item = None
            mod_index = -1
            if st.session_state.editing_target and st.session_state.editing_target["floor"] == selected_floor:
                is_modifying = True
                mod_index = st.session_state.editing_target["index"]
                mod_item = current_floor_data["defects"][mod_index]

            if is_modifying:
                st.warning(f"✏️ [{selected_floor}] **{mod_item['발생위치']}번** 위치 수정 중입니다. 도면에서 바꿀 위치를 터치하세요!")
                mod_display_width = st.slider("🔍 수정 도면 표시 크기", min_value=300, max_value=1200, value=700, step=50, key=f"mod_slider_{selected_floor}")
                mod_coords = streamlit_image_coordinates(floor_img, width=mod_display_width, key=f"mod_coords_{selected_floor}_{mod_index}")

                if mod_coords:
                    scale = img_w / mod_display_width
                    mod_item["X"] = int(mod_coords["x"] * scale)
                    mod_item["Y"] = int(mod_coords["y"] * scale)
                    st.success(f"📍 {mod_item['발생위치']}번 위치가 변경되었습니다!")
                    st.session_state.editing_target = None
                    st.rerun()

                if st.button("❌ 위치 수정 취소", use_container_width=True):
                    st.session_state.editing_target = None
                    st.rerun()
                st.divider()

            floor_defect_no = len(current_floor_data["defects"]) + 1
            circle_num = chr(9311 + floor_defect_no) if floor_defect_no <= 15 else f"({floor_defect_no})"

            total_global_defects = sum(len(f_data["defects"]) for f_data in st.session_state.floors.values())
            next_global_photo_no = total_global_defects + 1

            # 💡 스크롤 압박을 없애기 위해 좌측(도면) / 우측(입력폼) 2분할 레이아웃 적용
            col_map, col_form = st.columns([1.1, 1], gap="medium")

            with col_map:
                st.subheader(f"👇 도면 터치 (다음 번호: {circle_num})")
                view_width = st.slider("🔍 도면 크기 조절", min_value=300, max_value=900, value=500, step=50, key=f"view_slider_{selected_floor}")
                
                coords = streamlit_image_coordinates(floor_img, width=view_width, key=f"coords_{selected_floor}_{floor_defect_no}")

                x_pos, y_pos = None, None
                if coords:
                    scale = img_w / view_width
                    clicked_x = int(coords["x"] * scale)
                    clicked_y = int(coords["y"] * scale)

                    matched_idx = -1
                    for d_idx, d_item in enumerate(current_floor_data["defects"]):
                        dist = ((d_item["X"] - clicked_x) ** 2 + (d_item["Y"] - clicked_y) ** 2) ** 0.5
                        if dist <= 45 * scale:
                            matched_idx = d_idx
                            break
                    
                    if matched_idx != -1:
                        st.session_state.editing_target = {"floor": selected_floor, "index": matched_idx}
                        st.success(f"🎯 [{current_floor_data['defects'][matched_idx]['발생위치']}번] 마킹이 선택되었습니다!")
                        st.rerun()
                    else:
                        x_pos, y_pos = clicked_x, clicked_y
                        st.success(f"📍 위치 지정 완료 (X={x_pos}, Y={y_pos})")
                else:
                    st.info("💡 도면 위를 터치하여 위치를 지정하세요.")

            with col_form:
                st.subheader("📋 손상 상세 정보 (스마트 입력)")
                
                if "옥상" in selected_floor:
                    loc_detail = "옥상"
                    st.text_input("위치", value="옥상", disabled=True, key=f"loc_fixed_{selected_floor}_{floor_defect_no}")
                    element_options = ["파라펫", "처마", "방수층", "구조물", "직접 입력"]
                else:
                    loc_detail = st.text_input("위치 (예: 2-1, 복도 등)", value=st.session_state.last_loc, placeholder="예: 2-1", key=f"loc_custom_{selected_floor}_{floor_defect_no}")
                    element_options = ["교실", "복도", "계단실", "행정실", "직접 입력"]

                # 직전 기억된 부재 인덱스 찾기
                elem_default_idx = 0
                if st.session_state.last_elem in element_options:
                    elem_default_idx = element_options.index(st.session_state.last_elem)

                element_opt = st.selectbox("부재", element_options, index=elem_default_idx, key=f"elem_opt_{selected_floor}_{floor_defect_no}")
                if element_opt == "직접 입력":
                    element = st.text_input("부재 명칭 직접 입력", value="", key=f"elem_custom_{selected_floor}_{floor_defect_no}")
                else:
                    element = element_opt

                type_options = ["균열", "누수/습기", "박리/박락", "철근노출", "백화", "상태양호", "직접 입력"]
                type_default_idx = 0
                if st.session_state.last_type in type_options:
                    type_default_idx = type_options.index(st.session_state.last_type)

                defect_type_opt = st.selectbox("유형 및 형상", type_options, index=type_default_idx, key=f"type_opt_{selected_floor}_{floor_defect_no}")
                if defect_type_opt == "직접 입력":
                    defect_type = st.text_input("유형 직접 입력", value="", key=f"type_custom_{selected_floor}_{floor_defect_no}")
                else:
                    defect_type = defect_type_opt

                col_sub1, col_sub2 = st.columns(2)
                with col_sub1:
                    st.text_input("기호", value=circle_num, disabled=True, key=f"circle_show_{selected_floor}_{floor_defect_no}")
                with col_sub2:
                    photo_no = st.text_input("사진 번호", value=str(next_global_photo_no), key=f"pno_{selected_floor}_{floor_defect_no}")

                crack_w_options = ["-", "0.1", "0.2", "0.3", "0.4", "0.5 이상"]
                crack_l_options = ["-", "0.2", "0.4", "0.6", "0.8", "1.0", "1.2", "1.4", "1.6", "1.8", "2.0 이상"]
                dimension_options = ["-", "0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "1.0", "1.2", "1.4", "1.6", "1.8", "2.0"]

                crack_w = st.selectbox("균열폭 (mm)", crack_w_options, key=f"cw_{selected_floor}_{floor_defect_no}")
                crack_l = st.selectbox("균열길이 (m)", crack_l_options, key=f"cl_{selected_floor}_{floor_defect_no}")
                dmg_w = st.selectbox("손상가로 (m)", dimension_options, key=f"dw_{selected_floor}_{floor_defect_no}")
                dmg_h = st.selectbox("손상세로 (m)", dimension_options, key=f"dh_{selected_floor}_{floor_defect_no}")

                cnt = st.number_input("개소", min_value=1, value=1, step=1, key=f"cnt_{selected_floor}_{floor_defect_no}")

                cause_options = ["건조수축", "구조적 부하", "시공부실", "도막 노화", "진동/충격", "습기/침수", "자연 연화", "해당없음(양호)", "직접 입력"]
                cause_default_idx = 0
                if st.session_state.last_cause in cause_options:
                    cause_default_idx = cause_options.index(st.session_state.last_cause)

                cause_opt = st.selectbox("손상원인", cause_options, index=cause_default_idx, key=f"cause_opt_{selected_floor}_{floor_defect_no}")
                if cause_opt == "직접 입력":
                    cause = st.text_input("원인 직접 입력", value="", key=f"cause_custom_{selected_floor}_{floor_defect_no}")
                else:
                    cause = cause_opt

                uploaded_photo = st.file_uploader("📂 현장 사진 업로드", type=["png", "jpg", "jpeg", "heic"], key=f"photo_{selected_floor}_{floor_defect_no}")

                if st.button(f"✅ [{selected_floor}] 손상 항목 추가 ({circle_num})", use_container_width=True, key=f"btn_{selected_floor}_{floor_defect_no}"):
                    if x_pos is None or y_pos is None:
                        st.warning("먼저 좌측 도면 위를 터치하여 위치를 지정해 주세요.")
                    elif not loc_detail and "옥상" not in selected_floor:
                        st.warning("위치를 입력해 주세요.")
                    else:
                        # 입력 성공 시 현재 값을 '직전 기억값'으로 자동 저장
                        st.session_state.last_loc = loc_detail
                        st.session_state.last_elem = element
                        st.session_state.last_type = defect_type
                        st.session_state.last_cause = cause

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
                            "사진": uploaded_photo
                        }
                        current_floor_data["defects"].append(item)
                        st.success(f"[{selected_floor}] {circle_num}번 등록 완료!")
                        st.rerun()

            if current_floor_data["defects"]:
                st.markdown("---")
                st.markdown(f"#### 📌 [{selected_floor}] 등록된 항목 관리")
                for d_idx, d_item in enumerate(current_floor_data["defects"]):
                    col_item1, col_item2, col_item3 = st.columns([2, 4, 2])
                    with col_item1:
                        st.markdown(f"**{d_item['발생위치']}번** (사진 {d_item['사진번호']})")
                    with col_item2:
                        st.markdown(f"{d_item['위치']} / {d_item['부재']} / {d_item['유형 및 형상']}")
                    with col_item3:
                        if st.button(f"📍 위치 수정", key=f"edit_pos_{selected_floor}_{d_idx}"):
                            st.session_state.editing_target = {"floor": selected_floor, "index": d_idx}
                            st.rerun()

    st.divider()
    st.header("3. 결과물 개별 확인 및 다운로드")

    out_tabs = st.tabs(["🗺️ 1. 외관조사망도 (마킹 도면)", "📊 2. 전체 손상물량표", "📷 3. 현장 사진 대장"])

    with out_tabs[0]:
        view_floor = st.selectbox("마킹 도면 조회할 층 선택", sorted_floor_names, key="view_floor_select")

        c_s1, c_s2 = st.columns(2)
        with c_s1:
            size_ratio = st.slider("📍 손상점 크기 조절", min_value=1, max_value=20, value=6)
        with c_s2:
            circle_scale_ratio = st.slider("🔤 번호 동그라미 크기 조절", min_value=5, max_value=30, value=12)

        view_floor_data = st.session_state.floors[view_floor]
        marked_image = view_floor_data["image"].copy()
        draw = ImageDraw.Draw(marked_image)

        img_max_dim = max(view_floor_data["image"].size)
        dot_radius = max(3, int(img_max_dim * (size_ratio / 1200.0)))
        circle_radius = max(10, int(img_max_dim * (circle_scale_ratio / 350.0)))

        try:
            font_size = max(10, int(circle_radius * 1.1))
            font = ImageFont.truetype("gulim.ttc", font_size)
        except:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = ImageFont.load_default()

        for item in view_floor_data["defects"]:
            x, y = item["X"], item["Y"]
            num_str = str(item["층내번호"])
            
            draw.ellipse((x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius), fill="red", outline="red")
            
            offset_x = int(circle_radius * 1.8)
            offset_y = -int(circle_radius * 1.8)
            txt_center_x = x + offset_x
            txt_center_y = y + offset_y
            
            draw.line([(x, y), (txt_center_x, txt_center_y)], fill="red", width=max(1, dot_radius // 2))
            draw.ellipse((txt_center_x - circle_radius, txt_center_y - circle_radius, txt_center_x + circle_radius, txt_center_y + circle_radius), fill="white", outline="red", width=max(1, circle_radius // 8))
            
            bbox = draw.textbbox((0, 0), num_str, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            draw.text((txt_center_x - text_w / 2, txt_center_y - text_h / 2 - 2), num_str, fill="red", font=font)

        st.subheader(f"📌 [{view_floor}] 마킹 반영 외관조사망도")
        st.image(marked_image, use_container_width=True)

        buffered = BytesIO()
        marked_image.save(buffered, format="PNG")
        st.download_button(
            label=f"💾 [{view_floor}] 마킹 도면 이미지 파일로 저장",
            data=buffered.getvalue(),
            file_name=f"외관조사망도_{view_floor}.png",
            mime="image/png",
            use_container_width=True
        )

    with out_tabs[1]:
        all_defects_sorted = []
        for f_name in sorted_floor_names:
            for defect in st.session_state.floors[f_name]["defects"]:
                all_defects_sorted.append(defect)

        if all_defects_sorted:
            st.subheader("📊 전체 건축물 손상물량 집계표")
            df_display = pd.DataFrame(all_defects_sorted)[[
                "층", "발생위치", "사진번호", "위치", "부재", "유형 및 형상",
                "균열폭(mm)", "균열길이(m)", "손상가로(m)", "손상세로(m)", "개소", "손상원인"
            ]]
            st.dataframe(df_display, use_container_width=True)

            csv_data = df_display.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 손상물량표 엑셀(CSV) 파일 다운로드",
                data=csv_data,
                file_name="건축물_손상물량표.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("등록된 손상 항목이 없습니다.")

    with out_tabs[2]:
        st.subheader("📷 현장 사진 대장 (안전진단보고서 표준 양식)")
        
        has_any_photos = any(any(item.get("사진") is not None for item in st.session_state.floors[f]["defects"]) for f in sorted_floor_names)

        if has_any_photos:
            for f_name in sorted_floor_names:
                floor_photos = [item for item in st.session_state.floors[f_name]["defects"] if item.get("사진") is not None]
                if floor_photos:
                    st.markdown(
                        f"""
                        <div style="background-color: #f8f9fa; border: 1px solid #ced4da; padding: 10px; font-weight: bold; font-size: 16px; margin-top: 20px; margin-bottom: 10px;">
                            {f_name} 사진
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    for i in range(0, len(floor_photos), 2):
                        cols = st.columns(2)
                        for j in range(2):
                            if i + j < len(floor_photos):
                                p_item = floor_photos[i + j]
                                with cols[j]:
                                    st.image(p_item["사진"], use_container_width=True)
                                    content_desc = f"{p_item['위치']} {p_item['부재']} {p_item['유형 및 형상']}"
                                    st.markdown(
                                        f"""
                                        <div style="border: 1px solid #ced4da; display: flex; width: 100%; font-size: 14px; margin-bottom: 15px;">
                                            <div style="background-color: #f1f3f5; padding: 6px 10px; width: 22%; border-right: 1px solid #ced4da; font-weight: bold; text-align: center;">NO.{p_item['사진번호']}</div>
                                            <div style="padding: 6px 10px; width: 78%; text-align: left;">{content_desc}</div>
                                        </div>
                                        """,
                                        unsafe_allow_html=True
                                    )
        else:
            st.info("등록된 현장 사진이 없습니다.")
