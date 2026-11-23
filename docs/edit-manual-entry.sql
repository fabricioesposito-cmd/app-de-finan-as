create or replace function public.edit_manual_entry(p_source text,p_id uuid,p_data jsonb) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare cash public.cash_items; event public.card_events; entry_kind text; target text:=p_data->>'channel'; amount bigint:=(p_data->>'amount_cents')::bigint; target_month text:=p_data->>'month';
begin
 if auth.uid() is null then raise exception 'Entre na sua conta';end if;
 if p_source not in ('cash','event') or target not in ('cash','card') or amount is null or amount<1 or amount>9000000000000
 or target_month is null or target_month !~ '^[0-9]{4}-(0[1-9]|1[0-2])$' or left(target_month,4)='0000'
 or coalesce(length(trim(p_data->>'description')),0) not between 1 and 150
 or coalesce(length(trim(p_data->>'category')),0) not between 1 and 60
 then raise exception 'Confira os dados do lançamento';end if;
 if p_source='cash' then
  select * into cash from public.cash_items where id=p_id and user_id=auth.uid() for update;
  if not found then raise exception 'Lançamento não encontrado. Atualize a lista';end if;
  entry_kind:=cash.kind;
 else
  select * into event from public.card_events where id=p_id and user_id=auth.uid() for update;
  if not found then raise exception 'Lançamento não encontrado. Atualize a lista';end if;
  if exists(select 1 from public.entry_matches where event_id=p_id) then raise exception 'Compra vinculada à fatura. Edite o lançamento importado';end if;
  entry_kind:='expense';
 end if;
 if target='card' then
  if entry_kind<>'expense' then raise exception 'Receitas devem entrar em conta';end if;
  if not exists(select 1 from public.cards where id=(p_data->>'card_id')::uuid and user_id=auth.uid()) then raise exception 'Cartão não encontrado';end if;
  if p_source='cash' then
   insert into public.card_events(id,card_id,month,purchase_date,description,amount_cents,category,registered_at)
   values(p_id,(p_data->>'card_id')::uuid,target_month,(p_data->>'date')::date,p_data->>'description',amount,p_data->>'category',cash.registered_at);
   delete from public.cash_items where id=p_id and user_id=auth.uid();
  else
   update public.card_events set card_id=(p_data->>'card_id')::uuid,month=target_month,purchase_date=(p_data->>'date')::date,
    description=p_data->>'description',amount_cents=amount,category=p_data->>'category' where id=p_id and user_id=auth.uid();
  end if;
 else
  if p_source='event' then
   insert into public.cash_items(id,description,kind,category,amount_cents,due_date,budget_month,settled,account_id,registered_at)
   values(p_id,p_data->>'description',entry_kind,p_data->>'category',amount,(p_data->>'date')::date,target_month,(p_data->>'settled')::boolean,(p_data->>'account_id')::uuid,event.registered_at);
   delete from public.card_events where id=p_id and user_id=auth.uid();
  else
   update public.cash_items set description=p_data->>'description',category=p_data->>'category',amount_cents=amount,
    due_date=(p_data->>'date')::date,budget_month=target_month,settled=(p_data->>'settled')::boolean,account_id=(p_data->>'account_id')::uuid
    where id=p_id and user_id=auth.uid();
  end if;
 end if;
 return jsonb_build_object('id',p_id,'channel',target);
end $$;
revoke all on function public.edit_manual_entry(text,uuid,jsonb) from public,anon;
grant execute on function public.edit_manual_entry(text,uuid,jsonb) to authenticated;

