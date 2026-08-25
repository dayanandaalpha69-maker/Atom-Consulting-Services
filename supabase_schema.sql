
-- Atom Consulting Services V4
-- Run this in Supabase SQL Editor.

create table if not exists public.leads (
    id uuid primary key,
    created_at timestamptz not null default now(),
    name text not null,
    email text not null,
    company text,
    service text not null,
    requirements text not null,
    status text not null default 'New',
    notification_email text
);

create table if not exists public.documents (
    id uuid primary key,
    lead_id uuid not null references public.leads(id) on delete cascade,
    original_name text not null,
    storage_path text not null,
    size_bytes bigint not null,
    mime_type text,
    uploaded_at timestamptz not null default now()
);

-- Enable RLS. The Streamlit server uses the service-role key,
-- so public/anonymous users never receive database access.
alter table public.leads enable row level security;
alter table public.documents enable row level security;

-- Private storage bucket.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'client-documents',
    'client-documents',
    false,
    15728640,
    array[
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ]
)
on conflict (id) do update set
    public = false,
    file_size_limit = 15728640,
    allowed_mime_types = excluded.allowed_mime_types;

-- Do not create anon/authenticated policies for these tables.
-- The service role used by Streamlit is intended for server-side access.
