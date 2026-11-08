"""Painting estimator: run with `streamlit run app.py`."""
import html
import json
import uuid
from datetime import date

import pandas as pd
import streamlit as st

from pricing import (
    DATA_DIR, UNIT_LABELS, default_qty, is_high_ceiling, load_options, load_price_book,
    load_settings, price_job, room_measurements,
)

settings = load_settings()
book = load_price_book()
options = load_options()

BRAND_RED = "#DA312C"
logo_path = DATA_DIR / settings["business"].get("logo", "")
has_logo = logo_path.is_file()

st.set_page_config(page_title=f"{settings['business']['name']} Estimator",
                   page_icon=str(logo_path) if has_logo else "🎨", layout="centered")
if has_logo:
    st.logo(str(logo_path))


def new_job():
    return {"customer": {"name": "", "address": "", "phone": "", "email": ""}, "notes": "", "rooms": []}


def nid():
    return uuid.uuid4().hex[:8]


if "job" not in st.session_state:
    st.session_state.job = new_job()
job = st.session_state.job

# ---------------- Job (sidebar) ----------------
with st.sidebar:
    st.header("Job")
    c = job["customer"]
    c["name"] = st.text_input("Customer name", c["name"])
    c["address"] = st.text_input("Address", c["address"])
    c["phone"] = st.text_input("Phone", c["phone"])
    c["email"] = st.text_input("Email", c["email"])
    job["notes"] = st.text_area("Notes", job["notes"])

    st.divider()
    fname = (c["name"] or "job").strip().replace(" ", "_") + ".json"
    st.download_button("Save job file", json.dumps(job, indent=2), file_name=fname, mime="application/json")
    uploaded = st.file_uploader("Open a saved job", type="json")
    if uploaded and st.button("Load job"):
        loaded = json.load(uploaded)
        for k in list(st.session_state):
            del st.session_state[k]
        st.session_state.job = loaded
        st.rerun()
    if st.button("Start new job"):
        for k in list(st.session_state):
            del st.session_state[k]
        st.rerun()

tab_rooms, tab_est, tab_book = st.tabs(["Rooms & services", "Estimate", "Price book"])

# ---------------- Rooms & services ----------------
with tab_rooms:
    with st.form("add_room", clear_on_submit=True):
        st.subheader("Add a room")
        name = st.text_input("Room name", placeholder="Kitchen, Bedroom 2…")
        c1, c2, c3 = st.columns(3)
        L = c1.number_input("Length (ft)", min_value=0.0, value=12.0, step=0.5)
        W = c2.number_input("Width (ft)", min_value=0.0, value=12.0, step=0.5)
        H = c3.number_input("Height (ft)", min_value=0.0, value=8.0, step=0.5)
        d1, d2 = st.columns(2)
        doors = d1.number_input("Doors", min_value=0, value=1, step=1)
        windows = d2.number_input("Windows", min_value=0, value=1, step=1)
        if st.form_submit_button("Add room") and name.strip():
            job["rooms"].append({
                "id": nid(), "name": name.strip(), "length": L, "width": W, "height": H,
                "doors": int(doors), "windows": int(windows), "lines": [], "adjustments": [],
            })
            st.rerun()

    if not job["rooms"]:
        st.info("Add the first room above to start the estimate.")

    for room in list(job["rooms"]):
        rid = room["id"]
        with st.expander(room["name"], expanded=True):
            # Dimensions
            c1, c2, c3 = st.columns(3)
            room["length"] = c1.number_input("Length", min_value=0.0, value=float(room["length"]), step=0.5, key=f"L_{rid}")
            room["width"] = c2.number_input("Width", min_value=0.0, value=float(room["width"]), step=0.5, key=f"W_{rid}")
            room["height"] = c3.number_input("Height", min_value=0.0, value=float(room["height"]), step=0.5, key=f"H_{rid}")
            d1, d2 = st.columns(2)
            room["doors"] = int(d1.number_input("Doors", min_value=0, value=int(room["doors"]), step=1, key=f"D_{rid}"))
            room["windows"] = int(d2.number_input("Windows", min_value=0, value=int(room["windows"]), step=1, key=f"Wn_{rid}"))
            meas = room_measurements(room, settings)
            note = (f"Walls {meas['wall_sqft']:,.0f} sq ft · Ceiling {meas['ceiling_sqft']:,.0f} sq ft · "
                    f"Perimeter {meas['perimeter_ft']:,.0f} ft")
            if is_high_ceiling(room, settings):
                note += f" · High-ceiling surcharge applies ({settings['high_ceiling_surcharge']:.0%})"
            st.caption(note)

            # Current services
            st.markdown("**Services**")
            if not room["lines"]:
                st.caption("No services yet.")
            for line in list(room["lines"]):
                svc = book.get(line["service_id"])
                label = svc["name"] if svc else f"{line['service_id']} (not in price book)"
                unit = UNIT_LABELS[svc["unit"]] if svc else ""
                opts = ", ".join(line["options"].values())
                a, b = st.columns([6, 1])
                a.write(f"{label}: {line['qty']:,.1f} {unit}" + (f" ({opts})" if opts else ""))
                if b.button("✕", key=f"del_{line['id']}"):
                    room["lines"].remove(line)
                    st.rerun()

            # Add a service
            sid = st.selectbox(
                "Add a service", list(book),
                format_func=lambda s: f"{book[s]['category']}: {book[s]['name']}", key=f"svc_{rid}",
            )
            svc = book[sid]
            chosen = {}
            if svc["option_groups"]:
                cols = st.columns(len(svc["option_groups"]))
                for col, g in zip(cols, svc["option_groups"]):
                    chosen[g] = col.selectbox(options[g]["label"], list(options[g]["choices"]), key=f"opt_{rid}_{sid}_{g}")
            dq = default_qty(svc, meas)
            qty = st.number_input(
                f"Quantity ({UNIT_LABELS[svc['unit']]})", min_value=0.0, value=float(dq), step=1.0,
                key=f"qty_{rid}_{sid}_{dq}",
                help="Filled in from the room size. Change it if needed." if svc["unit"] in meas else None,
            )
            if st.button("Add service", key=f"add_{rid}"):
                room["lines"].append({"id": nid(), "service_id": sid, "qty": qty, "options": chosen})
                st.rerun()

            # Room adjustments (oddities)
            st.markdown("**Adjustments** (odd corners, stairwells, extra setup)")
            for adj in list(room["adjustments"]):
                a, b = st.columns([6, 1])
                a.write(f"{adj['description']}: ${adj['amount']:,.2f}")
                if b.button("✕", key=f"deladj_{adj['id']}"):
                    room["adjustments"].remove(adj)
                    st.rerun()
            a1, a2 = st.columns([3, 2])
            desc = a1.text_input("Description", key=f"adjd_{rid}")
            amt = a2.number_input("Amount ($)", value=0.0, step=25.0, key=f"adja_{rid}")
            if st.button("Add adjustment", key=f"adjadd_{rid}") and desc.strip() and amt:
                room["adjustments"].append({"id": nid(), "description": desc.strip(), "amount": amt})
                del st.session_state[f"adjd_{rid}"]
                del st.session_state[f"adja_{rid}"]
                st.rerun()

            st.divider()
            if st.button("Remove room", key=f"rmroom_{rid}"):
                job["rooms"].remove(room)
                st.rerun()

# ---------------- Estimate ----------------
with tab_est:
    result = price_job(job, book, options, settings)
    biz = settings["business"]
    c = job["customer"]

    if has_logo:
        st.image(str(logo_path), width=260)
    else:
        st.title(biz["name"])
    st.caption(" | ".join(x for x in [biz["phone"], biz["email"]] if x))
    st.markdown(f"**Estimate for:** {c['name'] or '—'}  \n{c['address']}  \n"
                + " | ".join(x for x in [c["phone"], c["email"]] if x))
    st.caption(f"Date: {date.today():%B %d, %Y}")

    for w in result["warnings"]:
        st.warning(w)

    if not result["rooms"]:
        st.info("Add rooms and services to see the estimate.")

    for r in result["rooms"]:
        st.markdown(f"<h3 style='color:{BRAND_RED}; border-bottom:2px solid #171717; "
                    f"padding-bottom:4px'>{html.escape(r['name'])}</h3>", unsafe_allow_html=True)
        rows = [{"Service": l["name"], "Details": l["options_text"], "Qty": f"{l['qty']:,.1f} {l['unit_label']}",
                 "Rate": f"${l['rate']:,.2f}", "Amount": f"${l['total']:,.2f}"} for l in r["lines"]]
        rows += [{"Service": "Adjustment", "Details": a["description"], "Qty": "", "Rate": "",
                  "Amount": f"${a['total']:,.2f}"} for a in r["adjustments"]]
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True)
            with st.expander("How this room was priced"):
                for l in r["lines"]:
                    st.write(f"**{l['name']}**: {l['explanation']} = ${l['total']:,.2f}")
        st.markdown(f"**Room subtotal: ${r['subtotal']:,.2f}**")

    st.markdown(f"<div style='background:#171717; color:#FFFFFF; padding:14px 18px; border-radius:6px; "
                f"border-left:8px solid {BRAND_RED}; font-size:1.6rem; font-weight:700; margin-top:1rem'>"
                f"Total: ${result['total']:,.2f}</div>", unsafe_allow_html=True)
    if job["notes"]:
        st.caption(job["notes"])

# ---------------- Price book ----------------
with tab_book:
    st.caption("To change prices, edit data/price_book.csv and data/options.csv, then refresh the app.")
    st.dataframe(pd.DataFrame([
        {"Category": s["category"], "Service": s["name"], "Unit": UNIT_LABELS[s["unit"]],
         "Rate": f"${s['rate']:,.2f}", "Options": ", ".join(options[g]["label"] for g in s["option_groups"]),
         "High-ceiling surcharge": "Yes" if s["height_surcharge"] else ""}
        for s in book.values()
    ]), hide_index=True)
    st.markdown("**Option multipliers**")
    st.dataframe(pd.DataFrame([
        {"Option": g["label"], "Choice": ch, "Multiplier": f"{m:g}×"}
        for g in options.values() for ch, m in g["choices"].items()
    ]), hide_index=True)
