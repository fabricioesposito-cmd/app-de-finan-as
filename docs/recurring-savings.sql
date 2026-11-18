create table public.savings_schedules (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
 start_month text not null check(start_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$' and left(start_month,4)<>'0000'),
 amount_cents bigint not null check(amount_cents between 0 and 9000000000000),
 unique(user_id,start_month)
);
alter table public.savings_schedules enable row level security;
create policy owner_access on public.savings_schedules for all to authenticated
 using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
grant select,insert,update,delete on public.savings_schedules to authenticated;
alter table public.monthly_plans add column savings_override boolean not null default false;

