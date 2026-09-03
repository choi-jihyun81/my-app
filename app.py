import streamlit as st
import pandas as pd
import re
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from streamlit_image_coordinates import streamlit_image_coordinates

# ============================================================
# 학교 시설물 현장조사 앱 - 스마트폰 최적화 버전
# 기존 기능 유지 + 현장 입력 UX 개선
# ============================================================

st.set_page_config(
    page_title="학교 현장조사",
    page_icon="🏫",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ---------- 모바일 UI ----------
st.markdown("""
<style>
/* 전체 여백 */
.block-container {
    padding-top: .45rem !important;
    padding-bottom: 5rem !important;
    padding-left: .65rem !important;
    padding-right: .65rem !important;
    max-width: 720px;
}

/* 버튼 */
.stButton > button {
    min-height: 48px !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 16px !important;
}
div[data-testid="stHorizontalBlock"] {
    gap: .45rem !important;
}

/* 입력창 */
input, textarea, select {
    font-size: 16px !important;
}
div[data-baseweb="select"] > div {
    min-height: 46px !important;
}

/* 제목 */
h1 { font-size: 1.55rem !important; margin-bottom: .2rem !important; }
h2 { font-size: 1.25rem !important; }
h3 { font-size: 1.05rem !important; }

/* 탭 */
button[data-baseweb="tab"] {
    font-size: 14px !important;
    padding: 8px 10px !important;
}

/* 작은 안내 */
.mobile-note {
    background: #f5f7fa;
    padding: 9px 11px;
    border-radius: 9px;
    font-size: 13px;
    margin: 6px 0 10px;
}

/* 최근 조사 카드 */
.defect-card {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 9px;
    margin: 6px 0;
    background: #fff;
}

/* 하단 고정 느낌의 빠른 메뉴 */
.quick-menu {
    position: sticky;
    bottom: 0;
    z-index: 100;
    background: rgba(255,255,255,.96);
    padding: 7px 0;
    border-top: 1px solid #ddd;
}
</style>
""", unsafe_allow_html=True)

# ---------- 세션 ----------
if "floors" not in st.session_state:
    st.session_state.floors = {}

if "selected_floor" not in st.session_state:
    st.session_state.selected_floor = None

if "editing_target" not in st.session_state:
    st.session_state.editing_target = None

if "pending_coords" not in st.session_state:
    st.session_state.pending_coords = {}

if "input_reset" not in st.session_state:
    st.session_state.input_reset = 0

# ---------- 기본 함수 ----------
def get_floor_level(name):
    if "옥상" in name:
        return 999
    if "지하" in name:
        nums = re.findall(r'\d+', name)
        return -int(nums[0]) if nums else -1
    nums = re.findall(r'\d+', name)
    return int(nums[0]) if nums else 0

def next_numbers():
    total = sum(len(v["defects"]) for v in st.session_state.floors.values())
    return total + 1

def circle_label(n):
    # ①~⑮
    return chr(9311 + n) if n <= 15 else f"({n})"

def get_font(size):
    for f in ["gulim.ttc", "malgun.ttf", "arial.ttf"]:
        try:
            return ImageFont.truetype(f, size)
        except:
            pass
    return ImageFont.load_default()

def all_defects():
    rows = []
    for floor in sorted(st.session_state.floors, key=get_floor_level, reverse=True):
        rows.extend(st.session_state.floors[floor]["defects"])
    return rows

def defect_summary(item):
    return f"{item['발생위치']} · {item['위치']} · {item['부재']} · {item['유형 및 형상']}"

# ============================================================
# HEADER
# ============================================================
st.title("🏫 학교 현장조사")
st.caption("스마트폰 현장조사용 · 도면 위치 → 손상정보 → 사진 → 저장")

# ============================================================
# 1. 층 도면 관리
# ============================================================
with st.expander("⚙️ 조사 기본설정 / 층 도면 등록", expanded=not bool(st.session_state.floors)):
    floor_name = st.text_input(
        "층/섹터",
        placeholder="예: 지하1층, 1층, 2층, 옥상",
        key="floor_name"
    )
    floor_img = st.file_uploader(
        "도면 JPG/PNG",
        type=["png", "jpg", "jpeg"],
        key="floor_upload"
    )

    if st.button("➕ 층 도면 추가 / 갱신", use_container_width=True):
        if floor_name and floor_img:
            img = Image.open(floor_img).convert("RGB")
            if floor_name not in st.session_state.floors:
                st.session_state.floors[floor_name] = {
                    "image": img,
                    "defects": []
                }
            else:
                st.session_state.floors[floor_name]["image"] = img
            st.session_state.selected_floor = floor_name
            st.success(f"{floor_name} 도면 등록 완료")
            st.rerun()
        else:
            st.warning("층 이름과 도면을 모두 선택하세요.")

# ============================================================
# 층 선택
# ============================================================
if not st.session_state.floors:
    st.info("먼저 조사할 층의 도면을 등록하세요.")
    st.stop()

sorted_floors = sorted(
    st.session_state.floors.keys(),
    key=get_floor_level,
    reverse=True
)

if st.session_state.selected_floor not in sorted_floors:
    st.session_state.selected_floor = sorted_floors[0]

st.markdown("### 🏢 조사 층")
selected_floor = st.selectbox(
    "현재 조사 층",
    sorted_floors,
    index=sorted_floors.index(st.session_state.selected_floor),
    label_visibility="collapsed",
    key="current_floor_select"
)
st.session_state.selected_floor = selected_floor

current = st.session_state.floors[selected_floor]
img = current["image"]
img_w, img_h = img.size

# ============================================================
# 현재 층 진행상황
# ============================================================
st.markdown(
    f'<div class="mobile-note">📌 <b>{selected_floor}</b> · 현재 손상 '
    f'<b>{len(current["defects"])}</b>건 · 전체 <b>{len(all_defects())}</b>건</div>',
    unsafe_allow_html=True
)

# ============================================================
# 수정 대상 확인
# ============================================================
edit = st.session_state.editing_target
editing_here = (
    edit is not None and
    edit["floor"] == selected_floor and
    0 <= edit["index"] < len(current["defects"])
)

# ============================================================
# ① 도면 위치
# ============================================================
st.subheader("① 도면에서 위치 지정")

if editing_here:
    item = current["defects"][edit["index"]]
    st.warning(
        f"✏️ {item['발생위치']}번 위치 수정 중 · "
        f"도면에서 새 위치를 터치하세요."
    )
else:
    item = None

# 스마트폰에서는 너무 크게 늘리지 않고 화면 폭에 맞춤
default_width = min(680, max(320, img_w))
display_width = st.slider(
    "도면 크기",
    320,
    min(1200, max(1200, img_w)),
    default_width,
    40,
    key=f"map_size_{selected_floor}"
)

st.caption("📍 기존 마킹을 누르면 해당 손상을 선택합니다. 빈 곳을 누르면 새 위치입니다.")

coords = streamlit_image_coordinates(
    img,
    width=display_width,
    key=f"map_{selected_floor}_{len(current['defects'])}_{'edit' if editing_here else 'new'}"
)

x_pos = y_pos = None

if coords:
    scale = img_w / display_width
    cx = int(coords["x"] * scale)
    cy = int(coords["y"] * scale)

    # 수정 모드
    if editing_here:
        current["defects"][edit["index"]]["X"] = cx
        current["defects"][edit["index"]]["Y"] = cy
        st.session_state.editing_target = None
        st.success(f"📍 {item['발생위치']}번 위치 변경 완료")
        st.rerun()

    # 새 손상: 기존 마킹과 가까우면 수정 대상으로 인식
    matched = -1
    threshold = 45 * scale
    for i, d in enumerate(current["defects"]):
        dist = ((d["X"] - cx) ** 2 + (d["Y"] - cy) ** 2) ** 0.5
        if dist <= threshold:
            matched = i
            break

    if matched >= 0:
        st.session_state.editing_target = {
            "floor": selected_floor,
            "index": matched
        }
        st.info(
            f"🎯 {current['defects'][matched]['발생위치']}번 선택됨. "
            "다시 누르면 위치 수정 화면으로 이동합니다."
        )
        st.rerun()
    else:
        st.session_state.pending_coords[selected_floor] = (cx, cy)
        st.success(f"📍 새 위치 선택: X={cx}, Y={cy}")

if selected_floor in st.session_state.pending_coords and not editing_here:
    x_pos, y_pos = st.session_state.pending_coords[selected_floor]

if editing_here and st.button("❌ 위치 수정 취소", use_container_width=True):
    st.session_state.editing_target = None
    st.rerun()

# ============================================================
# ② 손상정보 입력
# ============================================================
st.subheader("② 손상정보 입력")

next_floor_no = len(current["defects"]) + 1
next_photo_no = next_numbers()

# 반복조사를 위한 빠른 기본값
preset = st.radio(
    "빠른 입력",
    ["일반", "균열", "누수/습기", "박리/박락", "철근노출", "상태양호"],
    horizontal=True,
    key=f"preset_{selected_floor}"
)

# 기본값
if preset == "균열":
    default_type = "균열"
    default_cause = "건조수축"
elif preset == "누수/습기":
    default_type = "누수/습기"
    default_cause = "습기/침수"
elif preset == "박리/박락":
    default_type = "박리/박락"
    default_cause = "자연 연화"
elif preset == "철근노출":
    default_type = "철근노출"
    default_cause = "자연 연화"
elif preset == "상태양호":
    default_type = "상태양호"
    default_cause = "해당없음(양호)"
else:
    default_type = "균열"
    default_cause = "건조수축"

# 수정 모드이면 기존값을 우선
if editing_here:
    base = current["defects"][edit["index"]]
else:
    base = {}

c1, c2 = st.columns(2)

with c1:
    if "옥상" in selected_floor:
        location = "옥상"
        st.text_input("위치", value="옥상", disabled=True, key=f"loc_{selected_floor}")
        element_options = ["파라펫", "처마", "방수층", "구조물", "직접 입력"]
    else:
        location = st.text_input(
            "위치",
            value=base.get("위치", ""),
            placeholder="예: 2-1, 복도, 계단실",
            key=f"loc_{selected_floor}_{'edit' if editing_here else next_floor_no}"
        )
        element_options = ["교실", "복도", "계단실", "행정실", "화장실", "외벽", "직접 입력"]

    old_elem = base.get("부재", element_options[0])
    elem_index = element_options.index(old_elem) if old_elem in element_options else 0
    element_opt = st.selectbox(
        "부재",
        element_options,
        index=elem_index,
        key=f"elem_{selected_floor}_{'edit' if editing_here else next_floor_no}"
    )
    if element_opt == "직접 입력":
        element = st.text_input(
            "부재 직접입력",
            value=base.get("부재", "") if old_elem not in element_options else "",
            key=f"elem_custom_{selected_floor}_{'edit' if editing_here else next_floor_no}"
        )
    else:
        element = element_opt

    type_options = ["균열", "누수/습기", "박리/박락", "철근노출", "백화", "상태양호", "직접 입력"]
    old_type = base.get("유형 및 형상", default_type)
    type_index = type_options.index(old_type) if old_type in type_options else 0
    type_opt = st.selectbox(
        "유형 및 형상",
        type_options,
        index=type_index,
        key=f"type_{selected_floor}_{'edit' if editing_here else next_floor_no}"
    )
    if type_opt == "직접 입력":
        defect_type = st.text_input(
            "유형 직접입력",
            value=base.get("유형 및 형상", ""),
            key=f"type_custom_{selected_floor}_{'edit' if editing_here else next_floor_no}"
        )
    else:
        defect_type = type_opt

with c2:
    crack_w_options = ["-", "0.1", "0.2", "0.3", "0.4", "0.5 이상"]
    crack_l_options = ["-", "0.2", "0.4", "0.6", "0.8", "1.0", "1.2", "1.4", "1.6", "1.8", "2.0 이상"]
    dim_options = ["-", "0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "1.0", "1.2", "1.4", "1.6", "1.8", "2.0"]

    def option_index(options, value):
        return options.index(str(value)) if str(value) in options else 0

    crack_w = st.selectbox(
        "균열폭 (mm)",
        crack_w_options,
        index=option_index(crack_w_options, base.get("균열폭(mm)", "-")),
        key=f"cw_{selected_floor}_{'edit' if editing_here else next_floor_no}"
    )
    crack_l = st.selectbox(
        "균열길이 (m)",
        crack_l_options,
        index=option_index(crack_l_options, base.get("균열길이(m)", "-")),
        key=f"cl_{selected_floor}_{'edit' if editing_here else next_floor_no}"
    )
    dmg_w = st.selectbox(
        "손상가로 (m)",
        dim_options,
        index=option_index(dim_options, base.get("손상가로(m)", "-")),
        key=f"dw_{selected_floor}_{'edit' if editing_here else next_floor_no}"
    )
    dmg_h = st.selectbox(
        "손상세로 (m)",
        dim_options,
        index=option_index(dim_options, base.get("손상세로(m)", "-")),
        key=f"dh_{selected_floor}_{'edit' if editing_here else next_floor_no}"
    )

c3, c4 = st.columns(2)

with c3:
    count = st.number_input(
        "개소",
        min_value=1,
        value=int(base.get("개소", 1)),
        step=1,
        key=f"cnt_{selected_floor}_{'edit' if editing_here else next_floor_no}"
    )

with c4:
    cause_options = ["건조수축", "구조적 부하", "시공부실", "도막 노화", "진동/충격",
                     "습기/침수", "자연 연화", "해당없음(양호)", "직접 입력"]
    old_cause = base.get("손상원인", default_cause)
    cause_index = cause_options.index(old_cause) if old_cause in cause_options else 0
    cause_opt = st.selectbox(
        "손상원인",
        cause_options,
        index=cause_index,
        key=f"cause_{selected_floor}_{'edit' if editing_here else next_floor_no}"
    )
    if cause_opt == "직접 입력":
        cause = st.text_input(
            "원인 직접입력",
            value=base.get("손상원인", ""),
            key=f"cause_custom_{selected_floor}_{'edit' if editing_here else next_floor_no}"
        )
    else:
        cause = cause_opt

# 번호
st.text_input(
    "발생위치 기호",
    value=base.get("발생위치", circle_label(next_floor_no)),
    disabled=True,
    key=f"circle_{selected_floor}_{'edit' if editing_here else next_floor_no}"
)

photo_no = st.text_input(
    "사진 번호",
    value=str(base.get("사진번호", next_photo_no)),
    key=f"photo_no_{selected_floor}_{'edit' if editing_here else next_floor_no}"
)

# ============================================================
# ③ 사진
# ============================================================
st.subheader("③ 현장 사진")

photo = st.file_uploader(
    "📸 사진 촬영 / 갤러리 선택",
    type=["png", "jpg", "jpeg", "heic"],
    key=f"photo_{selected_floor}_{'edit' if editing_here else next_floor_no}"
)

if photo:
    st.image(photo, caption="선택한 사진", use_container_width=True)

# ============================================================
# ④ 저장
# ============================================================
st.subheader("④ 저장")

if editing_here:
    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 수정 저장", use_container_width=True):
            if not location or not element or not defect_type or not cause:
                st.warning("필수 항목을 확인하세요.")
            else:
                old = current["defects"][edit["index"]]
                old.update({
                    "사진번호": photo_no,
                    "위치": location,
                    "부재": element,
                    "유형 및 형상": defect_type,
                    "균열폭(mm)": crack_w,
                    "균열길이(m)": crack_l,
                    "손상가로(m)": dmg_w,
                    "손상세로(m)": dmg_h,
                    "개소": count,
                    "손상원인": cause
                })
                if photo:
                    old["사진"] = photo
                st.session_state.editing_target = None
                st.success("수정되었습니다.")
                st.rerun()

    with col2:
        if st.button("🗑️ 삭제", use_container_width=True):
            current["defects"].pop(edit["index"])
            st.session_state.editing_target = None
            st.success("삭제되었습니다.")
            st.rerun()

else:
    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ 손상 저장", use_container_width=True):
            if selected_floor not in st.session_state.pending_coords:
                st.warning("먼저 도면에서 손상 위치를 터치하세요.")
            elif not location and "옥상" not in selected_floor:
                st.warning("위치를 입력하세요.")
            elif not element or not defect_type or not cause:
                st.warning("부재·유형·원인을 확인하세요.")
            else:
                x, y = st.session_state.pending_coords[selected_floor]
                item = {
                    "층": selected_floor,
                    "층내번호": next_floor_no,
                    "발생위치": circle_label(next_floor_no),
                    "사진번호": photo_no,
                    "위치": location,
                    "부재": element,
                    "유형 및 형상": defect_type,
                    "균열폭(mm)": crack_w,
                    "균열길이(m)": crack_l,
                    "손상가로(m)": dmg_w,
                    "손상세로(m)": dmg_h,
                    "개소": count,
                    "손상원인": cause,
                    "X": x,
                    "Y": y,
                    "사진": photo
                }
                current["defects"].append(item)
                st.session_state.pending_coords.pop(selected_floor, None)
                st.success(f"🎉 {item['발생위치']}번 저장 완료")
                st.rerun()

    with col2:
        if st.button("🧹 입력 초기화", use_container_width=True):
            st.session_state.pending_coords.pop(selected_floor, None)
            st.rerun()

# ============================================================
# 최근 조사 목록
# ============================================================
st.divider()
st.subheader("📋 최근 조사 목록")

if current["defects"]:
    # 최근 항목부터 표시
    for i in range(len(current["defects"]) - 1, -1, -1):
        d = current["defects"][i]
        st.markdown(
            f"""
            <div class="defect-card">
            <b>{d['발생위치']}번</b> · 사진 {d['사진번호']}<br>
            {d['위치']} / {d['부재']} / {d['유형 및 형상']}<br>
            균열폭 {d['균열폭(mm)']} · 길이 {d['균열길이(m)']} · 개소 {d['개소']}
            </div>
            """,
            unsafe_allow_html=True
        )
        b1, b2 = st.columns(2)
        with b1:
            if st.button("✏️ 전체 수정", key=f"edit_{selected_floor}_{i}", use_container_width=True):
                st.session_state.editing_target = {
                    "floor": selected_floor,
                    "index": i
                }
                st.rerun()
        with b2:
            if st.button("📍 위치 수정", key=f"pos_{selected_floor}_{i}", use_container_width=True):
                st.session_state.editing_target = {
                    "floor": selected_floor,
                    "index": i
                }
                st.rerun()
else:
    st.info("아직 조사된 손상이 없습니다.")

# ============================================================
# 결과물
# ============================================================
st.divider()
st.header("📊 결과물")

result_tabs = st.tabs(["🗺️ 조사망도", "📊 물량표", "📷 사진대장"])

with result_tabs[0]:
    view_floor = st.selectbox("층 선택", sorted_floors, key="result_floor")
    view_data = st.session_state.floors[view_floor]
    marked = view_data["image"].copy()
    draw = ImageDraw.Draw(marked)

    max_dim = max(marked.size)
    dot_radius = max(3, int(max_dim * 6 / 1200))
    circle_radius = max(10, int(max_dim * 12 / 350))
    font = get_font(max(10, int(circle_radius * 1.1)))

    for d in view_data["defects"]:
        x, y = d["X"], d["Y"]
        draw.ellipse(
            (x-dot_radius, y-dot_radius, x+dot_radius, y+dot_radius),
            fill="red", outline="red"
        )

        tx = x + int(circle_radius * 1.8)
        ty = y - int(circle_radius * 1.8)

        draw.line(
            [(x, y), (tx, ty)],
            fill="red",
            width=max(1, dot_radius // 2)
        )
        draw.ellipse(
            (tx-circle_radius, ty-circle_radius,
             tx+circle_radius, ty+circle_radius),
            fill="white",
            outline="red",
            width=max(1, circle_radius // 8)
        )

        text = str(d["층내번호"])
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2]-bbox[0]
        th = bbox[3]-bbox[1]
        draw.text(
            (tx-tw/2, ty-th/2-2),
            text,
            fill="red",
            font=font
        )

    st.image(marked, use_container_width=True)

    buf = BytesIO()
    marked.save(buf, format="PNG")
    st.download_button(
        "💾 조사망도 저장",
        data=buf.getvalue(),
        file_name=f"외관조사망도_{view_floor}.png",
        mime="image/png",
        use_container_width=True
    )

with result_tabs[1]:
    rows = all_defects()
    if rows:
        cols = [
            "층", "발생위치", "사진번호", "위치", "부재",
            "유형 및 형상", "균열폭(mm)", "균열길이(m)",
            "손상가로(m)", "손상세로(m)", "개소", "손상원인"
        ]
        df = pd.DataFrame(rows)[cols]
        st.dataframe(df, use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 물량표 CSV 다운로드",
            data=csv,
            file_name="건축물_손상물량표.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("등록된 손상이 없습니다.")

with result_tabs[2]:
    rows = [d for d in all_defects() if d.get("사진") is not None]
    if rows:
        for d in rows:
            st.image(
                d["사진"],
                caption=f"NO.{d['사진번호']} · {d['층']} · {d['위치']} · {d['부재']} · {d['유형 및 형상']}",
                use_container_width=True
            )
    else:
        st.info("등록된 현장 사진이 없습니다.")
