alter table public.cash_items add column registered_at timestamptz;
update public.cash_items set registered_at=created_at;
alter table public.cash_items alter column registered_at set default now();
alter table public.card_events add column registered_at timestamptz;
alter table public.card_events alter column registered_at set default now();
alter table public.entries add column registered_at timestamptz;
update public.entries e set registered_at=i.created_at from public.imports i where i.id=e.import_id and i.user_id=e.user_id;
alter table public.entries alter column registered_at set default now();
do $migration$
declare definition text; changed text;
begin
 definition:=pg_get_functiondef('public.edit_manual_entry(text,uuid,jsonb)'::regprocedure);
 changed:=replace(definition,
 'public.card_events(id,card_id,month,purchase_date,description,amount_cents,category)',
 'public.card_events(id,card_id,month,purchase_date,description,amount_cents,category,registered_at)');
 if changed=definition then raise exception 'Event insert columns not found';end if;
 definition:=changed;
 changed:=replace(definition,
 'p_data->>''description'',amount,p_data->>''category'');',
 'p_data->>''description'',amount,p_data->>''category'',cash.registered_at);');
 if changed=definition then raise exception 'Event insert timestamp not found';end if;
 definition:=changed;
 changed:=replace(definition,
 'public.cash_items(id,description,kind,category,amount_cents,due_date,budget_month,settled,account_id)',
 'public.cash_items(id,description,kind,category,amount_cents,due_date,budget_month,settled,account_id,registered_at)');
 if changed=definition then raise exception 'Cash insert columns not found';end if;
 definition:=changed;
 changed:=replace(definition,
 '(p_data->>''account_id'')::uuid);',
 '(p_data->>''account_id'')::uuid,event.registered_at);');
 if changed=definition then raise exception 'Cash insert timestamp not found';end if;
 execute changed;
end $migration$;

