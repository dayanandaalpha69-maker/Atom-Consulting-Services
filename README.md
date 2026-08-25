# Atom Consulting Services 

This version replaces local lead/document storage with a free-tier-oriented cloud architecture:

**Streamlit Community Cloud**
→ **Supabase Free: PostgreSQL + private Storage**
→ **Resend Free: transactional email**
→ **atomconsultingservices@proton.me**

## Why this architecture?

Supabase Free currently includes a Postgres database, 500 MB database quota and 1 GB file storage, with a 50 MB maximum file-size setting. Resend Free currently includes 3,000 emails/month and a 100-email/day limit. These quotas are suitable for an early-stage consulting website with modest enquiry volume.

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
- Resend email notification
- Client email in Reply-To
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

## Setup — Resend Free

1. Create a free Resend account.
2. Create an API key.
3. For initial testing, use the sender/domain allowed by Resend for your account.
4. For a professional production sender, verify your Atom Consulting Services domain in Resend.
5. Put the API key in Streamlit Secrets.

Resend Free currently provides 3,000 emails/month and a 100-email/day limit.

## Streamlit Cloud Secrets

Copy `.streamlit/secrets.toml.example` into the Streamlit Cloud Secrets panel.

Example:

```toml
CONTACT_TO_EMAIL = "atomconsultingservices@proton.me"

SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "YOUR_SUPABASE_SERVICE_ROLE_KEY"
SUPABASE_BUCKET = "client-documents"

RESEND_API_KEY = "re_xxxxxxxxxxxxxxxxx"
RESEND_FROM_EMAIL = "Atom Consulting Services <onboarding@resend.dev>"
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
- Resend email count

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
