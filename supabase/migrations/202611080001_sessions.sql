-- Run in a dedicated Supabase project. No service-role key is used by the app.
create table if not exists public.roleready_sessions (
  id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  payload jsonb not null,
  version integer not null default 1 check (version > 0),
  updated_at timestamptz not null default now()
);
create index if not exists roleready_sessions_user_updated
  on public.roleready_sessions(user_id, updated_at desc);
alter table public.roleready_sessions enable row level security;
revoke all on public.roleready_sessions from anon;
grant select, insert, update, delete on public.roleready_sessions to authenticated;
create policy "Read own sessions" on public.roleready_sessions
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "Create own sessions" on public.roleready_sessions
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "Update own sessions" on public.roleready_sessions
  for update to authenticated using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
create policy "Delete own sessions" on public.roleready_sessions
  for delete to authenticated using ((select auth.uid()) = user_id);
