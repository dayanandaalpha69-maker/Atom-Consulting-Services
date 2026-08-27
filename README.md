# Atom Consulting Services 

This version replaces local lead/document storage with a free-tier-oriented cloud architecture:

**Streamlit Community Cloud**
→ **Supabase Free: PostgreSQL + private Storage**
→ **SMTP: transactional email**
→ **atomconsultingservices@proton.me**

## Why this architecture?

Supabase Free currently includes a Postgres database, 500 MB database quota and 1 GB file storage, with a 50 MB maximum file-size setting. Email is sent through an authenticated SMTP account, so the app does not depend on the Streamlit domain or Resend.

Sources:
- Supabase pricing: https://supabase.com/pricing
- Resend pricing: https://resend.com/pricing
- Supabase Storage limits: https://supabase.com/docs/guides/storage/uploads/file-limits

## capabilities

- 3-position hero
- Services
- About
- Consulting approach
- Contact / service-request form
- PDF, DOC, DOCX uploads
- Multiple attachments
- 15 MB application-level limit per file
- Maximum 5 files and 25 MB total per request
- Private Supabase Storage
- Supabase PostgreSQL lead database
- Unique Lead ID
- SMTP email notification
- Client email in Reply-To
- Password-protected admin dashboard
- Lead search, status and priority management
- Secure document downloads from private Storage
- Secrets kept outside GitHub

## Setup — Supabase Free

1. Create a free Supabase project.
2. Open SQL Editor.
3. Paste and run `supabase_schema.sql`.
4. Go to Project Settings → API.
5. Copy the project URL.
6. Copy the `service_role` key.
7. Keep the service-role key private. Never expose it in browser/client code.

The SQL creates:
- `leads`
- `documents`
- private `client-documents` Storage bucket

Supabase recommends storing files outside the database; Storage provides buckets and access controls.

## Setup — SMTP email

1. Use an SMTP-enabled mailbox for sending notifications. Proton Mail requires a paid plan and a Proton Mail Bridge SMTP connection; alternatively use Gmail, Zoho, Outlook, or another SMTP provider.
2. Create an app password where your provider supports it. Do not use your normal mailbox password.
3. Put the SMTP settings in Streamlit Secrets. The recipient remains `atomconsultingservices@proton.me`.

The Streamlit hosting domain does not need to support SMTP. Streamlit sends the message server-side through the configured SMTP provider.

## Admin dashboard

1. Add `ADMIN_USERNAME` and a long unique `ADMIN_PASSWORD` to Streamlit Cloud Secrets.
2. Apply `supabase_schema.sql` in Supabase SQL Editor. The `priority` migration is safe to run against an existing `leads` table.
3. Open `https://atomconsultingservices.streamlit.app/?admin=1`.
4. Sign in to search every lead, inspect requirements, update status and priority, and download documents from the private `client-documents` bucket.

The admin dashboard uses the server-side Supabase service-role key. Never put that key or the admin password in frontend code or GitHub.

## Streamlit Cloud Secrets

Copy `.streamlit/secrets.toml.example` into the Streamlit Cloud Secrets panel.

Example:

```toml
CONTACT_TO_EMAIL = "atomconsultingservices@proton.me"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "use-a-long-unique-password"

SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "YOUR_SUPABASE_SERVICE_ROLE_KEY"
SUPABASE_BUCKET = "client-documents"

SMTP_HOST = "smtp.example.com"
SMTP_PORT = 587
SMTP_USERNAME = "your-sending-email@example.com"
SMTP_PASSWORD = "your-email-app-password"
SMTP_FROM_EMAIL = "your-sending-email@example.com"
SMTP_USE_SSL = false
```

Do not commit a real `secrets.toml`.

## Local setup

```bash
python -m venv .venv
```

Windows:
```bash
.venv\Scripts\activate
```

macOS/Linux:
```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub deployment

```bash
git init
git add .
git commit -m "Atom Consulting Services V4"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY
git push -u origin main
```

Then deploy `app.py` on Streamlit Community Cloud and add the secrets.

## Security model

The website does not expose the Supabase service-role key to visitors. Streamlit runs the database/storage calls server-side.

Uploaded client documents go into a **private** Storage bucket.

The browser never receives a public document URL.

The lead record and document metadata are stored in PostgreSQL; the actual documents are stored in Supabase Storage.

## Important free-tier limitation

The system is designed to remain within free tiers for early usage, but quotas are not guarantees of unlimited production use.

Monitor:
- Supabase storage usage
- Supabase database usage
- Supabase project inactivity/pausing
- Supabase egress
- SMTP provider sending limits

Supabase Free projects can pause after one week of inactivity.

For confidential consulting documents, add malware scanning, stronger access controls, retention/deletion policies and a formal privacy policy before scaling the service.

## Future upgrade path

When Atom Consulting Services grows:

1. Add authenticated consultant dashboard.
2. Add CRM integration.
3. Add automatic acknowledgement email.
4. Add AI document extraction.
5. Generate lead summary / opportunity score.
6. Assign leads to consultants.
7. Add proposal-generation workflow.
8. Add client portal.
