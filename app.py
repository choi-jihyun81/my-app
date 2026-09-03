import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import streamlit.components.v1 as components
import base64, io, json, uuid

st.set_page_config(
    page_title="학교 현장조사 앱 v3",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------------------
# 모바일 현장조사용 CSS
# ---------------------------------------------------------
st.markdown("""
<style>
html, body, [class*="css"] {
    font-size: 15px;
}
.block-container {
    padding: 0.55rem 0.55rem 1.5rem 0.55rem;
    max-width: 1100px;
}
button, .stButton > button {
    min-height: 46px !important;
    font-size: 15px !important;
}
div[data-testid="stHorizontalBlock"] {
    gap: 0.35rem;
}
.mobile-card {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 10px;
    margin: 6px 0;
}
.small-note {
    color: #666;
    font-size: 12px;
}
.marker-help {
    background: #f4f6f8;
    border-radius: 9px;
    padding: 8px 10px;
    margin: 5px 0 8px 0;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 세션 데이터
# ---------------------------------------------------------
if "floors" not in st.session_state:
    st.session_state.floors = {}

if "current_floor" not in st.session_state:
    st.session_state.current_floor = None

if "selected_defect_id" not in st.session_state:
    st.session_state.selected_defect_id = None

if "move_mode" not in st.session_state:
    st.session_state.move_mode = False

if "pending_xy" not in st.session_state:
    st.session_state.pending_xy = None

if "edit_id" not in st.session_state:
    st.session_state.edit_id = None

if "photo_counter" not in st.session_state:
    st.session_state.photo_counter = 1


# ---------------------------------------------------------
# 유틸
# ---------------------------------------------------------
def new_id():
    return str(uuid.uuid4())[:8]


def get_floor():
    return st.session_state.floors.get(st.session_state.current_floor)


def save_uploaded_image(uploaded):
    if uploaded is None:
        return None
    try:
        return Image.open(uploaded).convert("RGB")
    except Exception:
        return None


def img_to_bytes(img, fmt="JPEG"):
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def make_marked_plan(floor):
    """기존 도면 위에 손상번호 마커를 표시"""
    if not floor or floor.get("image") is None:
        return None

    base = floor["image"].copy().convert("RGB")
    draw = ImageDraw.Draw(base)

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
    except Exception:
        font = ImageFont.load_default()

    for i, d in enumerate(floor.get("defects", []), start=1):
        x, y = d.get("x"), d.get("y")
        if x is None or y is None:
            continue

        r = 15
        draw.ellipse((x-r, y-r, x+r, y+r), outline="red", width=4)
        draw.text((x+18, y-12), str(i), fill="red", font=font)

    return base


def find_defect(floor, defect_id):
    if not floor:
        return None
    for d in floor.get("defects", []):
        if d.get("id") == defect_id:
            return d
    return None


def next_photo_number():
    n = st.session_state.photo_counter
    st.session_state.photo_counter += 1
    return n


# ---------------------------------------------------------
# 제목
# ---------------------------------------------------------
st.title("🏫 학교 현장조사 앱 v3")
st.caption("정기안전점검 → 향후 정밀안전점검까지 확장 가능한 현장조사 구조")

# ---------------------------------------------------------
# 기본 도면 / 층 관리
# ---------------------------------------------------------
st.subheader("① 조사 도면")

col1, col2 = st.columns([1, 2])

with col1:
    floor_name = st.text_input(
        "층/구역명",
        placeholder="예: 1층, 옥상, 본관-1층",
        key="new_floor_name"
    )

with col2:
    floor_image = st.file_uploader(
        "도면 또는 조사망도",
        type=["png", "jpg", "jpeg"],
        key="floor_image_upload"
    )

if st.button("➕ 층/구역 추가", use_container_width=True):
    if floor_name.strip() and floor_image is not None:
        img = save_uploaded_image(floor_image)
        st.session_state.floors[floor_name.strip()] = {
            "image": img,
            "defects": []
        }
        st.session_state.current_floor = floor_name.strip()
        st.success(f"{floor_name.strip()} 추가 완료")
        st.rerun()
    else:
        st.warning("층/구역명과 도면을 모두 입력해주세요.")

floor_names = list(st.session_state.floors.keys())

if not floor_names:
    st.info("먼저 층/구역과 도면을 추가해주세요.")
    st.stop()

# ---------------------------------------------------------
# 층 선택
# ---------------------------------------------------------
st.session_state.current_floor = st.selectbox(
    "현재 조사 층/구역",
    floor_names,
    index=floor_names.index(st.session_state.current_floor)
    if st.session_state.current_floor in floor_names else 0
)

floor = get_floor()

# ---------------------------------------------------------
# 위치 이동 안내
# ---------------------------------------------------------
if st.session_state.move_mode and st.session_state.selected_defect_id:
    selected = find_defect(floor, st.session_state.selected_defect_id)
    if selected:
        st.markdown(
            f"""
            <div class="marker-help">
            📍 <b>손상 {selected.get('display_no', '?')} 위치 이동 중</b><br>
            도면에서 <b>새 위치를 터치</b>하거나 아래의 <b>마커 이동</b> 기능을 사용하세요.
            </div>
            """,
            unsafe_allow_html=True
        )

# ---------------------------------------------------------
# 도면 표시 + 터치 위치 입력
# ---------------------------------------------------------
st.subheader("② 도면 위치")

if floor["image"] is not None:
    # streamlit_image_coordinates가 설치되어 있으면 사용
    try:
        from streamlit_image_coordinates import streamlit_image_coordinates

        display_width = min(900, floor["image"].width)
        display_height = int(floor["image"].height * display_width / floor["image"].width)

        shown = floor["image"].resize((display_width, display_height))

        # 현재 위치 이동 대상이 있으면 해당 마커를 크게 표시
        marked = shown.copy()
        md = ImageDraw.Draw(marked)

        for idx, d in enumerate(floor.get("defects", []), start=1):
            x, y = d.get("x"), d.get("y")
            if x is None or y is None:
                continue
            sx = int(x * display_width / floor["image"].width)
            sy = int(y * display_height / floor["image"].height)

            r = 13 if d.get("id") != st.session_state.selected_defect_id else 20
            outline = "red" if d.get("id") != st.session_state.selected_defect_id else "blue"
            md.ellipse((sx-r, sy-r, sx+r, sy+r), outline=outline, width=4)
            md.text((sx+15, sy-10), str(idx), fill=outline)

        coords = streamlit_image_coordinates(
            marked,
            key=f"plan_touch_{st.session_state.current_floor}_{len(floor.get('defects', []))}_{st.session_state.move_mode}"
        )

        if coords:
            # 표시 이미지 좌표 -> 원본 도면 좌표
            ox = round(coords["x"] * floor["image"].width / display_width)
            oy = round(coords["y"] * floor["image"].height / display_height)

            # 위치 이동 모드
            if st.session_state.move_mode and st.session_state.selected_defect_id:
                target = find_defect(floor, st.session_state.selected_defect_id)
                if target:
                    target["x"] = ox
                    target["y"] = oy
                    st.session_state.move_mode = False
                    st.session_state.pending_xy = (ox, oy)
                    st.success(
                        f"손상 {target.get('display_no', '?')} 위치를 "
                        f"({ox}, {oy})로 이동했습니다."
                    )
                    st.rerun()

            else:
                st.session_state.pending_xy = (ox, oy)
                st.info(f"선택 위치: X={ox}, Y={oy}")

    except ImportError:
        st.warning(
            "streamlit_image_coordinates가 설치되어 있지 않습니다. "
            "터미널에서 `pip install streamlit-image-coordinates`를 실행하세요."
        )

# ---------------------------------------------------------
# 손상 목록 / 마커 선택
# ---------------------------------------------------------
st.subheader("③ 손상 마커")

defects = floor.get("defects", [])

if defects:
    st.caption("💡 마커를 직접 드래그하는 기능은 브라우저별 지원 차이가 있어, v3에서는 '마커 선택 → 도면 터치'를 기본으로 안정화했습니다. 다음 단계에서 HTML Canvas 기반 드래그를 붙일 수 있습니다.")

    for idx, d in enumerate(defects, start=1):
        label = f"#{idx}  {d.get('부재','')} / {d.get('유형 및 형상','')}"
        if d.get("발생위치"):
            label += f" / {d.get('발생위치')}"

        c1, c2, c3, c4 = st.columns([4, 1.4, 1.4, 1.4])

        with c1:
            if st.button(label, key=f"select_{d['id']}", use_container_width=True):
                st.session_state.selected_defect_id = d["id"]
                st.session_state.move_mode = False
                st.rerun()

        with c2:
            if st.button("📍 이동", key=f"move_{d['id']}", use_container_width=True):
                st.session_state.selected_defect_id = d["id"]
                st.session_state.move_mode = True
                st.rerun()

        with c3:
            if st.button("✏️ 수정", key=f"edit_{d['id']}", use_container_width=True):
                st.session_state.edit_id = d["id"]
                st.rerun()

        with c4:
            if st.button("🗑", key=f"del_{d['id']}", use_container_width=True):
                floor["defects"] = [x for x in defects if x["id"] != d["id"]]
                if st.session_state.selected_defect_id == d["id"]:
                    st.session_state.selected_defect_id = None
                    st.session_state.move_mode = False
                st.rerun()

# ---------------------------------------------------------
# 전체 수정
# ---------------------------------------------------------
if st.session_state.edit_id:
    target = find_defect(floor, st.session_state.edit_id)
    if target:
        st.subheader("✏️ 손상 전체 수정")

        e1, e2 = st.columns(2)
        with e1:
            target["발생위치"] = st.text_input(
                "발생위치", target.get("발생위치", ""),
                key=f"e_loc_{target['id']}"
            )
            target["부재"] = st.text_input(
                "부재", target.get("부재", ""),
                key=f"e_member_{target['id']}"
            )
            target["유형 및 형상"] = st.text_input(
                "유형 및 형상", target.get("유형 및 형상", ""),
                key=f"e_type_{target['id']}"
            )
            target["손상원인"] = st.text_input(
                "손상원인", target.get("손상원인", ""),
                key=f"e_cause_{target['id']}"
            )

        with e2:
            target["균열폭(mm)"] = st.number_input(
                "균열폭(mm)", min_value=0.0,
                value=float(target.get("균열폭(mm)", 0) or 0),
                step=0.01, key=f"e_cw_{target['id']}"
            )
            target["균열길이(m)"] = st.number_input(
                "균열길이(m)", min_value=0.0,
                value=float(target.get("균열길이(m)", 0) or 0),
                step=0.1, key=f"e_cl_{target['id']}"
            )
            target["손상가로(m)"] = st.number_input(
                "손상가로(m)", min_value=0.0,
                value=float(target.get("손상가로(m)", 0) or 0),
                step=0.1, key=f"e_w_{target['id']}"
            )
            target["손상세로(m)"] = st.number_input(
                "손상세로(m)", min_value=0.0,
                value=float(target.get("손상세로(m)", 0) or 0),
                step=0.1, key=f"e_h_{target['id']}"
            )
            target["개소"] = st.number_input(
                "개소", min_value=1,
                value=int(target.get("개소", 1) or 1),
                step=1, key=f"e_n_{target['id']}"
            )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 수정 저장", key=f"save_edit_{target['id']}",
                         use_container_width=True):
                st.session_state.edit_id = None
                st.success("수정되었습니다.")
                st.rerun()
        with c2:
            if st.button("취소", key=f"cancel_edit_{target['id']}",
                         use_container_width=True):
                st.session_state.edit_id = None
                st.rerun()

# ---------------------------------------------------------
# 신규 손상 입력
# ---------------------------------------------------------
st.subheader("④ 신규 손상 입력")

if st.session_state.pending_xy:
    px, py = st.session_state.pending_xy
    st.success(f"📍 신규 위치: X={px}, Y={py}")
else:
    st.info("도면을 먼저 터치해 신규 손상 위치를 지정하세요.")

preset = st.radio(
    "빠른 유형",
    ["일반", "균열", "누수/습기", "박리/박락", "철근노출", "상태양호"],
    horizontal=True,
    key="preset_type"
)

p1, p2 = st.columns(2)

with p1:
    발생위치 = st.text_input("발생위치", placeholder="예: 복도 중앙")
    부재 = st.text_input("부재", placeholder="예: 벽체")

with p2:
    preset_map = {
        "일반": "",
        "균열": "균열",
        "누수/습기": "누수/습기",
        "박리/박락": "박리/박락",
        "철근노출": "철근노출",
        "상태양호": "상태양호"
    }
    유형_초기 = preset_map[preset]
    유형 = st.text_input("유형 및 형상", value=유형_초기)

q1, q2, q3 = st.columns(3)

with q1:
    균열폭 = st.number_input("균열폭(mm)", min_value=0.0, step=0.01)
    균열길이 = st.number_input("균열길이(m)", min_value=0.0, step=0.1)

with q2:
    손상가로 = st.number_input("손상가로(m)", min_value=0.0, step=0.1)
    손상세로 = st.number_input("손상세로(m)", min_value=0.0, step=0.1)

with q3:
    개소 = st.number_input("개소", min_value=1, value=1, step=1)
    원인 = st.text_input("손상원인")

photo = st.file_uploader(
    "📷 현장 사진",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=False,
    key="new_damage_photo"
)

if photo:
    photo_img = save_uploaded_image(photo)
    if photo_img:
        st.image(photo_img, caption="촬영/선택 사진", width=240)

save_col1, save_col2 = st.columns(2)

with save_col1:
    save_damage = st.button("💾 손상 저장", type="primary",
                            use_container_width=True)

with save_col2:
    save_next = st.button("💾 저장 후 다음", use_container_width=True)

if save_damage or save_next:
    if st.session_state.pending_xy is None:
        st.warning("먼저 도면에서 손상 위치를 지정해주세요.")
    elif not 부재.strip() and not 유형.strip():
        st.warning("부재 또는 손상 유형을 입력해주세요.")
    else:
        x, y = st.session_state.pending_xy

        item = {
            "id": new_id(),
            "display_no": len(defects) + 1,
            "층": st.session_state.current_floor,
            "발생위치": 발생위치,
            "부재": 부재,
            "유형 및 형상": 유형,
            "균열폭(mm)": 균열폭,
            "균열길이(m)": 균열길이,
            "손상가로(m)": 손상가로,
            "손상세로(m)": 손상세로,
            "개소": 개소,
            "손상원인": 원인,
            "X": x,
            "Y": y,
            "사진번호": next_photo_number() if photo else "",
            "사진": photo_img if photo else None
        }

        floor["defects"].append(item)

        st.session_state.pending_xy = None
        st.session_state.selected_defect_id = item["id"]

        if save_next:
            st.success(f"손상 #{item['display_no']} 저장 완료 — 다음 손상을 입력하세요.")
        else:
            st.success(f"손상 #{item['display_no']} 저장 완료")

        st.rerun()

# ---------------------------------------------------------
# 출력
# ---------------------------------------------------------
st.subheader("⑤ 결과")

tab1, tab2, tab3 = st.tabs(["📍 조사망도", "📋 물량표", "📷 사진대장"])

with tab1:
    marked = make_marked_plan(floor)
    if marked:
        st.image(marked, use_container_width=True)

with tab2:
    rows = []
    for fname, fdata in st.session_state.floors.items():
        for d in fdata.get("defects", []):
            rows.append({
                "층": fname,
                "번호": d.get("display_no"),
                "발생위치": d.get("발생위치"),
                "부재": d.get("부재"),
                "유형 및 형상": d.get("유형 및 형상"),
                "균열폭(mm)": d.get("균열폭(mm)"),
                "균열길이(m)": d.get("균열길이(m)"),
                "손상가로(m)": d.get("손상가로(m)"),
                "손상세로(m)": d.get("손상세로(m)"),
                "개소": d.get("개소"),
                "손상원인": d.get("손상원인"),
                "X": d.get("X"),
                "Y": d.get("Y")
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        st.download_button(
            "⬇️ CSV 다운로드",
            df.to_csv(index=False).encode("utf-8-sig"),
            "손상물량표.csv",
            "text/csv"
        )
    else:
        st.info("등록된 손상이 없습니다.")

with tab3:
    photo_rows = []
    for fname, fdata in st.session_state.floors.items():
        for d in fdata.get("defects", []):
            if d.get("사진"):
                photo_rows.append({
                    "층": fname,
                    "손상번호": d.get("display_no"),
                    "사진번호": d.get("사진번호"),
                    "발생위치": d.get("발생위치"),
                    "부재": d.get("부재"),
                    "유형": d.get("유형 및 형상")
                })

    if photo_rows:
        st.dataframe(pd.DataFrame(photo_rows), use_container_width=True)
    else:
        st.info("등록된 사진이 없습니다.")

# ---------------------------------------------------------
# 현재 데이터 백업
# ---------------------------------------------------------
st.divider()
st.caption("v3 메모: 현재 버전은 '마커 선택 → 이동 모드 → 도면 터치'를 안정적인 위치수정 방식으로 제공합니다. 실제 손가락 드래그는 Streamlit 기본 컴포넌트의 제약 때문에 다음 단계에서 HTML Canvas 기반 도면 컴포넌트로 구현하는 것이 가장 안정적입니다.")
