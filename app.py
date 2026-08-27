
import html
import hmac
import re
import smtplib
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage

import streamlit as st
from supabase import create_client, Client
from streamlit.errors import StreamlitSecretNotFoundError

st.set_page_config(
    page_title="Atom Consulting Services | Strategy. Transformation. Impact.",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

def get_secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except StreamlitSecretNotFoundError:
        return default


TO_EMAIL = get_secret("CONTACT_TO_EMAIL", "atomconsultingservices@proton.me")
BUCKET = get_secret("SUPABASE_BUCKET", "client-documents")
MAX_FILE_MB = 15
MAX_FILES = 5
MAX_TOTAL_UPLOAD_MB = 25
ALLOWED_TYPES = ["pdf", "doc", "docx"]

def get_supabase() -> Client:
    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase secrets are not configured.")
    return create_client(url, key)

def safe_filename(name):
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return stem[:120]

def create_lead_and_uploads(name, email, company, service, requirements, files):
    sb = get_supabase()
    lead_id = str(uuid.uuid4())
    created = datetime.now(timezone.utc).isoformat()

    lead = {
        "id": lead_id,
        "created_at": created,
        "name": name,
        "email": email,
        "company": company,
        "service": service,
        "requirements": requirements,
        "status": "New",
        "notification_email": TO_EMAIL,
    }
    docs = []
    stored_paths = []
    try:
        sb.table("leads").insert(lead).execute()

        for uploaded in files:
            original = uploaded.name
            stored = f"{lead_id}/{uuid.uuid4().hex}_{safe_filename(original)}"
            data = uploaded.getvalue()

            sb.storage.from_(BUCKET).upload(
                stored,
                data,
                {"content-type": uploaded.type or "application/octet-stream", "upsert": "false"},
            )
            stored_paths.append(stored)

            doc = {
                "id": str(uuid.uuid4()),
                "lead_id": lead_id,
                "original_name": original,
                "storage_path": stored,
                "size_bytes": len(data),
                "mime_type": uploaded.type,
                "uploaded_at": created,
            }
            sb.table("documents").insert(doc).execute()
            docs.append({"name": original, "data": data, "mime": uploaded.type or "application/octet-stream"})
    except Exception:
        if stored_paths:
            try:
                sb.storage.from_(BUCKET).remove(stored_paths)
            except Exception:
                pass
        try:
            sb.table("leads").delete().eq("id", lead_id).execute()
        except Exception:
            pass
        raise

    return lead_id, docs

def send_smtp_email(name, email, company, service, requirements, lead_id, docs):
    smtp_host = get_secret("SMTP_HOST")
    try:
        smtp_port = int(get_secret("SMTP_PORT", 587))
    except (TypeError, ValueError):
        return False, "SMTP is not configured correctly. The lead was saved to Supabase."
    smtp_username = get_secret("SMTP_USERNAME")
    smtp_password = get_secret("SMTP_PASSWORD")
    from_email = get_secret("SMTP_FROM_EMAIL", smtp_username)
    smtp_use_ssl = str(get_secret("SMTP_USE_SSL", "false")).lower() == "true"
    if not smtp_host or not smtp_username or not smtp_password or not from_email:
        return False, "SMTP is not configured. The lead was saved to Supabase."

    escaped_name = html.escape(name)
    escaped_email = html.escape(email)
    escaped_company = html.escape(company) if company else "Not provided"
    escaped_service = html.escape(service)
    escaped_requirements = html.escape(requirements).replace("\r\n", "<br>").replace("\n", "<br>")
    message = EmailMessage()
    message["From"] = from_email
    message["To"] = TO_EMAIL
    message["Reply-To"] = email
    message["Subject"] = f"New Atom Consulting Lead - {service} - {name}"
    message.set_content(f"New service request from {name} ({email}). Lead ID: {lead_id}")
    message.add_alternative(f"""
        <h2>New Atom Consulting Services Request</h2>
        <p><b>Lead ID:</b> {lead_id}</p>
        <p><b>Name:</b> {escaped_name}<br>
        <b>Email:</b> {escaped_email}<br>
        <b>Company:</b> {escaped_company}<br>
        <b>Service:</b> {escaped_service}</p>
        <h3>Business / User Requirements</h3>
        <p>{escaped_requirements}</p>
        <p><b>Documents:</b> {len(docs)}</p>
        """, subtype="html")
    for doc in docs:
        message.add_attachment(doc["data"], maintype="application", subtype="octet-stream", filename=doc["name"])

    try:
        smtp_class = smtplib.SMTP_SSL if smtp_use_ssl else smtplib.SMTP
        with smtp_class(smtp_host, smtp_port, timeout=30) as smtp:
            if not smtp_use_ssl:
                smtp.starttls()
            smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
        return True, "Email notification sent successfully."
    except Exception as exc:
        print(f"Email notification failed: {exc}")
        return False, "Email notification failed. The lead was saved to Supabase."

STATUS_OPTIONS = ["New", "Contacted", "Qualified", "Proposal", "Won", "Lost", "On Hold"]
PRIORITY_OPTIONS = ["Low", "Normal", "High", "Urgent"]

def admin_login():
    if st.session_state.get("admin_authenticated"):
        return True

    st.title("Atom Admin")
    st.caption("Sign in to manage submitted client requests.")
    with st.form("admin_login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
        if submitted:
            configured_username = get_secret("ADMIN_USERNAME")
            configured_password = get_secret("ADMIN_PASSWORD")
            if (configured_username and configured_password
                    and hmac.compare_digest(username, configured_username)
                    and hmac.compare_digest(password, configured_password)):
                st.session_state.admin_authenticated = True
                st.rerun()
            st.error("Invalid username or password.")
    return False

def get_admin_data(sb):
    leads = sb.table("leads").select("*").order("created_at", desc=True).execute().data or []
    lead_ids = [lead["id"] for lead in leads]
    documents = []
    if lead_ids:
        documents = sb.table("documents").select("*").in_("lead_id", lead_ids).order("uploaded_at", desc=True).execute().data or []
    documents_by_lead = {}
    for document in documents:
        documents_by_lead.setdefault(document["lead_id"], []).append(document)
    return leads, documents_by_lead

def render_admin_dashboard():
    st.markdown("""
    <style>
    .admin-header{padding:20px 0 8px;border-bottom:1px solid #E2E9F1;margin-bottom:24px}
    .admin-kpi{border:1px solid #E2E9F1;border-radius:12px;padding:16px;background:#fff}
    .admin-kpi strong{display:block;font-size:1.8rem;color:#071A2F}
    .admin-kpi span{color:#607085;font-size:.85rem}
    </style>
    """, unsafe_allow_html=True)
    if not admin_login():
        st.stop()

    sb = get_supabase()
    try:
        leads, documents_by_lead = get_admin_data(sb)
    except Exception as exc:
        st.error(f"Could not load dashboard data: {exc}")
        st.stop()

    header_left, header_right = st.columns([4, 1])
    with header_left:
        st.markdown('<div class="admin-header"><div class="section-label">Private workspace</div><h1>Client requests</h1><p class="lead">Review requirements, update pipeline state and download submitted documents.</p></div>', unsafe_allow_html=True)
    with header_right:
        st.write("")
        if st.button("Sign out", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.rerun()

    total_documents = sum(len(items) for items in documents_by_lead.values())
    urgent_count = sum(1 for lead in leads if lead.get("priority") == "Urgent")
    new_count = sum(1 for lead in leads if lead.get("status", "New") == "New")
    kpis = st.columns(4)
    for column, value, label in zip(kpis, [len(leads), new_count, urgent_count, total_documents], ["Total leads", "New", "Urgent", "Documents"]):
        with column:
            st.markdown(f'<div class="admin-kpi"><strong>{value}</strong><span>{label}</span></div>', unsafe_allow_html=True)

    st.write("")
    filter_left, filter_middle, filter_right = st.columns([2, 1, 1])
    with filter_left:
        search = st.text_input("Search leads", placeholder="Name, email, company or requirements")
    with filter_middle:
        status_filter = st.selectbox("Status", ["All"] + STATUS_OPTIONS)
    with filter_right:
        priority_filter = st.selectbox("Priority", ["All"] + PRIORITY_OPTIONS)

    search_text = search.strip().lower()
    filtered_leads = []
    for lead in leads:
        searchable = " ".join(str(lead.get(field) or "") for field in ["name", "email", "company", "service", "requirements"]).lower()
        if search_text and search_text not in searchable:
            continue
        if status_filter != "All" and lead.get("status", "New") != status_filter:
            continue
        if priority_filter != "All" and lead.get("priority", "Normal") != priority_filter:
            continue
        filtered_leads.append(lead)

    st.caption(f"Showing {len(filtered_leads)} of {len(leads)} leads")
    if not filtered_leads:
        st.info("No leads match the current filters.")
        return

    lead_labels = {lead["id"]: f'{lead.get("name", "Unnamed")} · {lead.get("company") or "Individual"} · {lead.get("service", "")}' for lead in filtered_leads}
    selected_id = st.selectbox("Open lead", list(lead_labels), format_func=lambda lead_id: lead_labels[lead_id])
    selected = next(lead for lead in filtered_leads if lead["id"] == selected_id)
    selected_documents = documents_by_lead.get(selected_id, [])

    detail_left, detail_right = st.columns([2, 1], gap="large")
    with detail_left:
        st.subheader(selected.get("name", "Unnamed lead"))
        st.caption(f'{selected.get("email", "")} · {selected.get("company") or "No company provided"}')
        st.markdown(f'**Service**  \n{selected.get("service", "")}')
        st.markdown("**Requirements**")
        st.text_area("Requirements", value=selected.get("requirements", ""), height=220, disabled=True, label_visibility="collapsed")
        st.caption(f'Lead ID: {selected_id} · Submitted: {selected.get("created_at", "")}' )

    with detail_right:
        st.subheader("Manage lead")
        current_status = selected.get("status") or "New"
        current_priority = selected.get("priority") or "Normal"
        with st.form(f"update_lead_{selected_id}"):
            new_status = st.selectbox("Status", STATUS_OPTIONS, index=STATUS_OPTIONS.index(current_status) if current_status in STATUS_OPTIONS else 0)
            new_priority = st.selectbox("Priority", PRIORITY_OPTIONS, index=PRIORITY_OPTIONS.index(current_priority) if current_priority in PRIORITY_OPTIONS else 1)
            save = st.form_submit_button("Save changes", use_container_width=True)
            if save:
                try:
                    sb.table("leads").update({"status": new_status, "priority": new_priority}).eq("id", selected_id).execute()
                    st.success("Lead updated.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not update lead. Apply the priority migration in supabase_schema.sql first. Details: {exc}")

        st.subheader(f"Documents ({len(selected_documents)})")
        for document in selected_documents:
            try:
                file_data = sb.storage.from_(BUCKET).download(document["storage_path"])
                st.download_button(
                    f'Download {document["original_name"]}',
                    data=file_data,
                    file_name=document["original_name"],
                    mime=document.get("mime_type") or "application/octet-stream",
                    key=f'download_{document["id"]}',
                    use_container_width=True,
                )
            except Exception:
                st.warning(f'Could not download {document["original_name"]}.')

if st.query_params.get("admin") == "1":
    render_admin_dashboard()
    st.stop()

# ---------------- CSS ----------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;color:#102033;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;text-rendering:optimizeLegibility;scroll-behavior:smooth;scroll-padding-top:90px}
.stApp{background:#fff}.block-container{max-width:1240px;padding-top:0.5rem;padding-bottom:0}
section[data-testid="stSidebar"]{display:none}
header[data-testid="stHeader"]{display:none !important}
[id]{scroll-margin-top:90px}
.topbar{display:flex;align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap;padding:10px 14px 12px;margin:0 -14px 8px;background:#fff;border-bottom:1px solid rgba(15,36,58,.06)}
.brand{display:flex;align-items:baseline;flex-wrap:wrap;gap:0.22rem;font-family:'Manrope';font-size:clamp(1.08rem,1.7vw,1.55rem);font-weight:800;letter-spacing:-.06em;line-height:1.1;color:#071A2F;white-space:normal;max-width:min(100%, 680px)}
.brand span{display:inline-block;color:#0D5CFF}
.topnav{display:flex;align-items:center;justify-content:flex-end;gap:8px;flex-wrap:wrap}
.navpill{display:inline-block;padding:10px 14px;border-radius:999px;color:#526276;text-decoration:none;font-size:.92rem;font-weight:700;line-height:1.2;transition:all .2s ease}
.navpill:hover{background:#EEF4FF;color:#0D5CFF}
.hero{min-height:555px;border-radius:28px;overflow:hidden;margin-top:14px;margin-bottom:70px;position:relative;background:radial-gradient(circle at 85% 20%,rgba(19,184,200,.30),transparent 27%),radial-gradient(circle at 74% 75%,rgba(13,92,255,.35),transparent 35%),linear-gradient(118deg,#071A2F 0%,#0B2948 56%,#0D5CFF 150%)}
.hero-grid{min-height:555px;padding:70px 68px;display:flex;flex-direction:column;justify-content:center;background-image:linear-gradient(rgba(255,255,255,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.045) 1px,transparent 1px);background-size:42px 42px}
.eyebrow,.section-label{color:#77E1E8;text-transform:uppercase;letter-spacing:.18em;font-size:.76rem;font-weight:800}
.hero h1{font-family:'Manrope';color:white;font-size:clamp(2.6rem,6vw,5.4rem);line-height:.98;letter-spacing:-.065em;max-width:800px;margin:0 0 22px}
.hero p{color:#D7E5F2;font-size:1.15rem;line-height:1.65;max-width:650px;margin-bottom:30px}
.cta{display:inline-block;background:#fff;color:#071A2F!important;padding:13px 21px;border-radius:999px;font-weight:800;text-decoration:none;margin-right:10px}
.cta.secondary{background:rgba(255,255,255,.08);color:#fff!important;border:1px solid rgba(255,255,255,.25)}
.slide-note{position:absolute;right:42px;bottom:35px;color:#D7E5F2;font-size:.78rem;letter-spacing:.08em}
h2{font-family:'Manrope';color:#071A2F;font-size:clamp(2rem,4vw,3.25rem);line-height:1.05;letter-spacing:-.055em;margin:10px 0 16px}
.lead{color:#607085;font-size:1.06rem;line-height:1.7;max-width:760px}
.section-label{color:#0D5CFF}.service-card{border:1px solid #E2E9F1;border-radius:20px;padding:28px;min-height:225px;background:#fff}
.service-no{color:#0D5CFF;font-weight:800;font-size:.75rem;letter-spacing:.14em}.service-card h3{font-family:'Manrope';color:#071A2F;font-size:1.28rem;margin:18px 0 10px}.service-card p{color:#607085;line-height:1.65;font-size:.94rem}
.trust{background:#F5F8FC;border-radius:24px;padding:28px 32px;margin:72px 0}.trust-stat{font-family:'Manrope';font-size:2rem;font-weight:800;color:#071A2F}.trust-copy{color:#607085;font-size:.88rem}
.about{background:#071A2F;border-radius:28px;padding:54px;color:white;margin:70px 0}.about h2{color:white}.about .lead{color:#B9CBDD}.about-point{border-top:1px solid rgba(255,255,255,.13);padding:16px 0}.about-point strong{color:white;display:block;margin-bottom:5px}.about-point span{color:#AFC2D5;font-size:.9rem}
.process-card{padding:24px 0;border-top:1px solid #DCE5EF}.process-number{color:#0D5CFF;font-weight:800;font-size:.8rem}.process-card h3{font-family:'Manrope';margin:8px 0;color:#071A2F}.process-card p{color:#607085;line-height:1.6}
.contact{background:linear-gradient(120deg,#0D5CFF,#13B8C8);border-radius:28px;padding:54px;color:white;margin:70px 0 35px}.contact h2{color:white}.contact p{color:#E7FAFC}
.footer{border-top:1px solid #E2E9F1;padding:30px 0 45px;color:#718096;font-size:.86rem}.footer strong{color:#071A2F}
div.stButton>button{border-radius:999px;border:0;background:#0D5CFF;color:white;font-weight:800}
@media (max-width: 720px){.topbar{align-items:flex-start;flex-direction:column}.topnav{justify-content:flex-start}.hero-grid{padding:48px 28px}.cta{display:inline-flex;align-items:center;justify-content:center;margin:0 10px 12px 0}.slide-note{right:24px;bottom:18px}}
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="topbar">
<div class="brand">ATOM <span>CONSULTING SERVICES</span></div>
<div class="topnav"><a class="navpill" href="#services">Services</a><a class="navpill" href="#about">About</a><a class="navpill" href="#approach">Approach</a><a class="navpill" href="#contact">Contact</a></div>
</div>
""", unsafe_allow_html=True)

# Hero
slides=[
("01 / STRATEGY","Turn complexity into a clear path forward.","Sharper decisions, aligned priorities and measurable execution."),
("02 / TRANSFORMATION","Build the capabilities that move business forward.","AI, digital transformation, operating-model redesign and execution."),
("03 / ANALYTICS","Make better decisions with better intelligence.","Decision-ready analytics, KPI systems and performance intelligence.")
]
if "slide" not in st.session_state: st.session_state.slide=0
s=slides[st.session_state.slide]
st.markdown(f"""<div class="hero"><div class="hero-grid"><div class="eyebrow">{s[0]}</div><h1>{s[1]}</h1><p>{s[2]}</p>
<div><a class="cta" href="#contact">Start a conversation →</a><a class="cta secondary" href="#services">Explore services</a></div></div>
<div class="slide-note">ATOM / {st.session_state.slide+1} — 3</div></div>""",unsafe_allow_html=True)
_,a,b,_=st.columns([5,1,1,5])
with a:
    if st.button("←",use_container_width=True): st.session_state.slide=(st.session_state.slide-1)%3; st.rerun()
with b:
    if st.button("→",use_container_width=True): st.session_state.slide=(st.session_state.slide+1)%3; st.rerun()

# Services
st.markdown("""<div id="services"></div><div class="section-label">What we do</div><h2>Advice that moves from<br>boardroom to business.</h2><p class="lead">Atom Consulting Services helps organisations navigate growth, transformation and technology-led change.</p>""",unsafe_allow_html=True)
services=[
("01","Business & Strategy","Growth strategy, market assessment, operating-model design and strategic planning."),
("02","AI & Digital Transformation","AI opportunity assessment, workflow redesign, digital roadmaps and adoption."),
("03","Data & Analytics","KPI frameworks, dashboards, analytical models and decision intelligence."),
("04","Technology Advisory","Technology strategy, solution roadmaps, architecture direction and governance."),
("05","Operations & Performance","Process redesign, productivity improvement and performance management."),
("06","Project & Change Advisory","PMO support, change planning, stakeholder alignment and execution discipline.")]
cols=st.columns(3)
for i,(n,t,d) in enumerate(services):
    with cols[i%3]: st.markdown(f'<div class="service-card" style="margin-top:18px"><div class="service-no">{n}</div><h3>{t}</h3><p>{d}</p></div>',unsafe_allow_html=True)

st.markdown("""<div class="trust"><div style="color:#0D5CFF;text-transform:uppercase;letter-spacing:.12em;font-size:.7rem;font-weight:800;margin-bottom:14px">Our consulting principles</div>
<div style="display:flex;gap:35px;flex-wrap:wrap"><div style="min-width:180px"><div class="trust-stat">Clarity</div><div class="trust-copy">Make complex decisions easier to understand.</div></div>
<div style="min-width:180px"><div class="trust-stat">Practicality</div><div class="trust-copy">Recommendations designed for execution.</div></div>
<div style="min-width:180px"><div class="trust-stat">Impact</div><div class="trust-copy">Focus effort on outcomes that matter.</div></div>
<div style="min-width:180px"><div class="trust-stat">Integrity</div><div class="trust-copy">Independent and transparent advice.</div></div></div></div>""",unsafe_allow_html=True)

# About
st.markdown("""<div id="about"></div><div class="about"><div class="section-label">About Atom</div><div style="display:grid;grid-template-columns:1.15fr .85fr;gap:50px">
<div><h2>A focused consulting partner for the next chapter.</h2><p class="lead">We solve important business problems without unnecessary complexity, connecting strategy, technology and execution.</p></div>
<div><div class="about-point"><strong>Independent perspective</strong><span>Objective advice grounded in your context.</span></div><div class="about-point"><strong>Business-first technology</strong><span>Technology choices begin with business value.</span></div><div class="about-point"><strong>Built for momentum</strong><span>Clear priorities, practical roadmaps and measurable next steps.</span></div></div></div></div>""",unsafe_allow_html=True)

# Approach
st.markdown("""<div id="approach"></div><div class="section-label">How we work</div><h2>Simple enough to act on.<br>Rigorous enough to trust.</h2><p class="lead">Every engagement is shaped around the decision or outcome that matters most.</p>""",unsafe_allow_html=True)
for n,t,d in [("01","Diagnose","Understand the situation, objectives, constraints and evidence."),("02","Design","Frame options, quantify trade-offs and define a practical roadmap."),("03","Deliver","Turn recommendations into initiatives and execution plans."),("04","Measure","Track outcomes, learn quickly and refine the approach.")]:
    st.markdown(f'<div class="process-card"><div class="process-number">{n}</div><h3>{t}</h3><p>{d}</p></div>',unsafe_allow_html=True)

# Contact
st.markdown('<div id="contact"></div>',unsafe_allow_html=True)
left,right=st.columns([1,1],gap="large")
with left:
    st.markdown(f"""<div class="contact"><div class="section-label">Start a conversation</div><h2>Have a business challenge worth solving?</h2>
<p>Submit your service request and attach your case study, RFP, business requirements, user requirements or supporting documents.</p>
<p><strong>PDF, DOC and DOCX</strong><br>Maximum 15 MB per file, 5 files and 25 MB total</p></div>""",unsafe_allow_html=True)

with right:
    st.markdown("### Contact us")
    with st.form("service_request",clear_on_submit=True):
        name=st.text_input("Name *")
        email=st.text_input("Business email *")
        company=st.text_input("Company / Organisation")
        service=st.selectbox("Service required",[x[1] for x in services]+["Other"])
        requirements=st.text_area("Business / User Requirements *",height=160)
        files=st.file_uploader("Upload case study / requirements / supporting documents",type=ALLOWED_TYPES,accept_multiple_files=True)
        consent=st.checkbox("I consent to Atom Consulting Services using the submitted information to respond to this enquiry.")
        submitted=st.form_submit_button("Send service request →")
        if submitted:
            if not name or not email or not requirements:
                st.warning("Please complete all required fields.")
            elif not consent:
                st.warning("Please provide consent before submitting.")
            elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$",email):
                st.warning("Please enter a valid email address.")
            else:
                files=files or []
                oversized=[f.name for f in files if f.size>MAX_FILE_MB*1024*1024]
                if oversized:
                    st.error("Files over 15 MB: "+", ".join(oversized))
                elif len(files) > MAX_FILES:
                    st.error(f"Please upload no more than {MAX_FILES} files.")
                elif sum(f.size for f in files) > MAX_TOTAL_UPLOAD_MB * 1024 * 1024:
                    st.error(f"Please keep the total upload size under {MAX_TOTAL_UPLOAD_MB} MB.")
                else:
                    try:
                        lead_id,docs=create_lead_and_uploads(name,email,company,service,requirements,files)
                        ok,msg=send_smtp_email(name,email,company,service,requirements,lead_id,docs)
                        st.success(f"Request received. Lead ID: {lead_id}")
                        if ok: st.info(msg)
                        else: st.warning(msg)
                    except Exception:
                        st.error("The request could not be completed. Check Supabase configuration and database/storage setup.")

# Footer
st.markdown(f"""<div class="footer"><div style="display:flex;justify-content:space-between;gap:30px;flex-wrap:wrap">
<div><strong>ATOM CONSULTING SERVICES</strong><br>Independent consulting for strategy, transformation and performance.</div>
<div><strong>Contact us</strong><br>{TO_EMAIL}<br>India · Serving clients globally</div>
<div><strong>Quick links</strong><br>Services · About · Approach · Contact</div></div>
<div style="margin-top:25px">© 2026 Atom Consulting Services. All rights reserved.</div></div>""",unsafe_allow_html=True)
