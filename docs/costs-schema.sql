
create table public.cash_items (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null default auth.uid() references auth.users(id),
 description text not null check(length(trim(description)) between 1 and 150),
 kind text not null check(kind in ('income','expense')),
 category text not null check(length(category) between 1 and 60),
 amount_cents bigint not null check(amount_cents>0 and amount_cents<=9000000000000),
 due_date date not null,
 settled boolean not null default false,
 created_at timestamptz not null default now()
);
create index cash_items_owner_date_idx on public.cash_items(user_id,due_date);
create table public.monthly_plans (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null default auth.uid() references auth.users(id),
 month text not null check(month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
 opening_cents bigint not null default 0 check(abs(opening_cents)<=9000000000000),
 savings_target_cents bigint not null default 0 check(savings_target_cents between 0 and 9000000000000),
 saved_cents bigint not null default 0 check(saved_cents between 0 and 9000000000000),
 unique(user_id,month)
);
create table public.card_settlements (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null default auth.uid() references auth.users(id),
 card_id uuid not null,
 month text not null check(month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
 paid_cents bigint not null default 0 check(paid_cents between 0 and 9000000000000),
 foreign key(card_id,user_id) references public.cards(id,user_id),
 unique(user_id,card_id,month)
);
create index card_settlements_card_owner_idx on public.card_settlements(card_id,user_id);
do $$ declare t text; begin
 foreach t in array array['cash_items','monthly_plans','card_settlements'] loop
 execute format('alter table public.%I enable row level security',t);
 execute format('create policy owner_access on public.%I for all to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id)',t);
 execute format('revoke all on public.%I from anon',t);
 execute format('grant select,insert,update,delete on public.%I to authenticated',t);
 end loop;
end $$;

alter table public.card_settlements add column bill_total_cents bigint check(bill_total_cents between 0 and 9000000000000);

