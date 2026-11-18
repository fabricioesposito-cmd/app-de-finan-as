alter table public.cash_items add column budget_month text
 check (budget_month is null or (budget_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$' and left(budget_month,4)<>'0000'));
do $migration$
declare definition text; updated text;
begin
 definition:=pg_get_functiondef('public.save_financial_entry(uuid,jsonb)'::regprocedure);
 updated:=replace(definition,
 'public.cash_items(description,kind,category,amount_cents,due_date,settled,account_id)',
 'public.cash_items(description,kind,category,amount_cents,due_date,settled,account_id,budget_month)');
 if updated=definition then raise exception 'Cash insert columns not found';end if;
 definition:=updated;
 updated:=replace(definition,
 '(p_data->>''account_id'')::uuid) returning id into saved;',
 '(p_data->>''account_id'')::uuid,p_data->>''month'') returning id into saved;');
 if updated=definition then raise exception 'Cash insert values not found';end if;
 execute updated;
end $migration$;

