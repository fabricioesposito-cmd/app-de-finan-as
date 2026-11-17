
create table public.accounts (
 id uuid primary key default gen_random_uuid(), user_id uuid not null default auth.uid() references auth.users(id),
 name text not null check(length(trim(name)) between 1 and 100), platform text not null default '',
 unique(id,user_id),unique(user_id,name)
);
alter table public.cash_items add column account_id uuid;
alter table public.cash_items add constraint cash_account_owner foreign key(account_id,user_id) references public.accounts(id,user_id);
create index cash_account_idx on public.cash_items(account_id,user_id);
create table public.workbook_imports(
 id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id),
 digest text not null,created_at timestamptz not null default now(),unique(user_id,digest),unique(id,user_id)
);
create table public.recurring_rules (
 id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id),
 description text not null check(length(trim(description)) between 1 and 150),
 kind text not null check(kind in ('income','expense')),channel text not null check(channel in ('cash','card')),
 category text not null check(length(category) between 1 and 60),
 amount_cents bigint not null check(amount_cents between 1 and 9000000000000),
 total_amount_cents bigint check(total_amount_cents between 1 and 9000000000000),
 start_month text not null check(start_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
 end_month text check(end_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
 due_day integer not null check(due_day between 1 and 31),
 interval_months integer not null default 1 check(interval_months between 1 and 12),
 occurrence_count integer check(occurrence_count between 1 and 600),
 schedule_type text not null default 'monthly' check(schedule_type in ('monthly','installment')),
 match_pattern text not null default '',
 card_id uuid,account_id uuid,source_batch_id uuid,
 check(end_month is null or end_month>=start_month),
 check((channel='cash' and card_id is null) or (channel='card' and card_id is not null and account_id is null and kind='expense')),
 check(schedule_type<>'installment' or occurrence_count is not null),
 foreign key(card_id,user_id) references public.cards(id,user_id),
 foreign key(account_id,user_id) references public.accounts(id,user_id),
 foreign key(source_batch_id,user_id) references public.workbook_imports(id,user_id) on delete cascade,
 unique(id,user_id)
);
create index recurring_owner_month_idx on public.recurring_rules(user_id,start_month);
create index recurring_card_idx on public.recurring_rules(card_id,user_id);
create index recurring_account_idx on public.recurring_rules(account_id,user_id);
create index recurring_batch_idx on public.recurring_rules(source_batch_id,user_id);
create table public.recurrence_states (
 id uuid primary key default gen_random_uuid(), user_id uuid not null default auth.uid() references auth.users(id),
 rule_id uuid not null,month text not null check(month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
 status text not null check(status in ('planned','realized','skipped')),
 amount_override_cents bigint check(amount_override_cents between 1 and 9000000000000),
 foreign key(rule_id,user_id) references public.recurring_rules(id,user_id) on delete cascade,
 unique(user_id,rule_id,month)
);
create index recurrence_state_rule_idx on public.recurrence_states(rule_id,user_id);
create table public.card_events (
 id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id),
 card_id uuid not null,month text not null check(month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
 purchase_date date not null,description text not null check(length(trim(description)) between 1 and 150),
 amount_cents bigint not null check(amount_cents between 1 and 9000000000000),
 category text not null check(length(category) between 1 and 60),
 foreign key(card_id,user_id) references public.cards(id,user_id),unique(id,user_id)
);
create index card_events_owner_month_idx on public.card_events(user_id,month);
create index card_events_card_idx on public.card_events(card_id,user_id);
alter table public.entries add constraint entries_owner_unique unique(id,user_id);
create table public.entry_matches (
 id uuid primary key default gen_random_uuid(),user_id uuid not null default auth.uid() references auth.users(id),
 entry_id uuid not null,event_id uuid,rule_id uuid,
 month text not null check(month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
 check(num_nonnulls(event_id,rule_id)=1),
 foreign key(entry_id,user_id) references public.entries(id,user_id) on delete cascade,
 foreign key(event_id,user_id) references public.card_events(id,user_id) on delete cascade,
 foreign key(rule_id,user_id) references public.recurring_rules(id,user_id) on delete cascade,
 unique(user_id,entry_id),unique(user_id,event_id),unique(user_id,rule_id,month)
);
create index entry_match_entry_idx on public.entry_matches(entry_id,user_id);
create index entry_match_event_idx on public.entry_matches(event_id,user_id);
create index entry_match_rule_idx on public.entry_matches(rule_id,user_id);
create table public.action_requests (
 id uuid not null,user_id uuid not null default auth.uid() references auth.users(id),
 payload jsonb not null,result jsonb not null,primary key(user_id,id)
);
do $$ declare t text; begin
 foreach t in array array['accounts','workbook_imports','recurring_rules','recurrence_states','card_events','entry_matches','action_requests'] loop
 execute format('alter table public.%I enable row level security',t);
 execute format('create policy owner_access on public.%I for all to authenticated using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id)',t);
 execute format('revoke all on public.%I from anon',t);
 execute format('grant select,insert,update,delete on public.%I to authenticated',t);
 end loop;
end $$;

create function public.save_financial_entry(p_key uuid,p_data jsonb) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare old public.action_requests; result jsonb; saved uuid; mode text:=p_data->>'mode';
 channel text:=p_data->>'channel'; amount bigint:=(p_data->>'amount_cents')::bigint;
 n int:=coalesce((p_data->>'installments')::int,1); begin
 if auth.uid() is null then raise exception 'Login necessário';end if;
 perform pg_advisory_xact_lock(hashtextextended(auth.uid()::text||p_key::text,0));
 select * into old from public.action_requests where id=p_key;
 if found then
 if old.payload<>p_data then raise exception 'Solicitação já confirmada com outros dados';end if;
 return old.result;end if;
 if mode not in ('once','monthly','installment') or channel not in ('cash','card') or p_data->>'kind' not in ('income','expense')
 or amount<1 or amount>9000000000000 or n<1 or n>600 then raise exception 'Dados inválidos';end if;
 if mode='once' and channel='cash' then
 insert into public.cash_items(description,kind,category,amount_cents,due_date,settled,account_id)
 values(p_data->>'description',p_data->>'kind',p_data->>'category',amount,(p_data->>'date')::date,coalesce((p_data->>'settled')::boolean,false),(p_data->>'account_id')::uuid) returning id into saved;
 elsif mode='once' then
 if p_data->>'kind'<>'expense' then raise exception 'Receita deve entrar em conta';end if;
 insert into public.card_events(card_id,month,purchase_date,description,amount_cents,category)
 values((p_data->>'card_id')::uuid,p_data->>'month',(p_data->>'date')::date,p_data->>'description',amount,p_data->>'category') returning id into saved;
 else
 if mode='installment' and amount<n then raise exception 'Valor insuficiente para o número de parcelas';end if;
 insert into public.recurring_rules(description,kind,channel,category,amount_cents,total_amount_cents,start_month,end_month,due_day,occurrence_count,schedule_type,match_pattern,card_id,account_id)
 values(p_data->>'description',p_data->>'kind',channel,p_data->>'category',
 case when mode='installment' then amount/n else amount end,
 case when mode='installment' then amount else null end,p_data->>'month',nullif(p_data->>'end_month',''),
 extract(day from (p_data->>'date')::date)::int,
 case when mode='installment' then n else null end,
 case when mode='installment' then 'installment' else 'monthly' end,coalesce(p_data->>'match_pattern',p_data->>'description'),
 (p_data->>'card_id')::uuid,(p_data->>'account_id')::uuid) returning id into saved;
 if coalesce((p_data->>'settled')::boolean,false) then
 insert into public.recurrence_states(rule_id,month,status) values(saved,p_data->>'month','realized');end if;
 end if;
 result:=jsonb_build_object('id',saved,'month',p_data->>'month','mode',mode,'channel',channel);
 insert into public.action_requests(id,payload,result) values(p_key,p_data,result);
 return result;end $$;
revoke all on function public.save_financial_entry(uuid,jsonb) from public,anon;
grant execute on function public.save_financial_entry(uuid,jsonb) to authenticated;

create function public.link_statement_entry(p_entry uuid,p_type text,p_source uuid,p_month text) returns void
language plpgsql security invoker set search_path='' as $$
declare card uuid;target uuid;begin
 select i.card_id into card from public.entries e join public.imports i on i.id=e.import_id where e.id=p_entry and i.month=p_month;
 if card is null then raise exception 'Lançamento ou mês inválido';end if;
 if p_type='event' then
 select id into target from public.card_events where id=p_source and card_id=card and month=p_month;
 if target is null then raise exception 'Compra informada pertence a outro cartão ou mês';end if;
 insert into public.entry_matches(entry_id,event_id,month) values(p_entry,p_source,p_month);
 elsif p_type='rule' then
 select id into target from public.recurring_rules where id=p_source and card_id=card and start_month<=p_month and (end_month is null or end_month>=p_month);
 if target is null then raise exception 'Recorrência inválida para este cartão/mês';end if;
 insert into public.entry_matches(entry_id,rule_id,month) values(p_entry,p_source,p_month);
 else raise exception 'Tipo de vínculo inválido';end if;
end $$;
revoke all on function public.link_statement_entry(uuid,text,uuid,text) from public,anon;
grant execute on function public.link_statement_entry(uuid,text,uuid,text) to authenticated;

create function public.confirm_import_with_links(p_card uuid,p_month text,p_digest text,p_expected bigint,p_rows jsonb)
returns uuid language plpgsql security invoker set search_path='' as $$
declare batch uuid;e record;begin
 batch:=public.confirm_import(p_card,p_month,p_digest,p_expected,p_rows);
 for e in select id,payload from public.entries where import_id=batch loop
 if coalesce(e.payload->>'match_id','')<>'' then
 perform public.link_statement_entry(e.id,e.payload->>'match_type',(e.payload->>'match_id')::uuid,p_month);end if;
 end loop;
 return batch;end $$;
revoke all on function public.confirm_import_with_links(uuid,text,text,bigint,jsonb) from public,anon;
grant execute on function public.confirm_import_with_links(uuid,text,text,bigint,jsonb) to authenticated;

