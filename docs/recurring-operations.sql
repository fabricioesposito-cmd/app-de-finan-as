create or replace function public.save_financial_entry(p_key uuid,p_data jsonb) returns jsonb
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
 if coalesce(p_data->>'fulfill_rule_id','')<>'' then
 if mode<>'once' or channel<>'cash' then raise exception 'Vínculo de receita/conta deve ser único e fora do cartão';end if;
 select rr.id into saved from public.recurring_rules rr where rr.id=(p_data->>'fulfill_rule_id')::uuid
 and rr.channel='cash' and rr.kind=p_data->>'kind' and rr.start_month<=p_data->>'month'
 and (rr.end_month is null or rr.end_month>=p_data->>'month');
 if saved is null then raise exception 'Previsão não encontrada';end if;
 insert into public.recurrence_states(rule_id,month,status,amount_override_cents)
 values(saved,p_data->>'month',case when coalesce((p_data->>'settled')::boolean,false) then 'realized' else 'planned' end,amount)
 on conflict(user_id,rule_id,month) do update set status=excluded.status,amount_override_cents=excluded.amount_override_cents;
 elsif mode='once' and channel='cash' then
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


create function public.import_workbook_plan(p_digest text,p_rules jsonb,p_plans jsonb,p_replace_targets boolean)
returns uuid language plpgsql security invoker set search_path='' as $$
declare batch uuid;r jsonb;p jsonb;new_rule uuid;m text;begin
 if auth.uid() is null then raise exception 'Login necessário';end if;
 if jsonb_typeof(p_rules)<>'array' or jsonb_array_length(p_rules)>2000 or jsonb_typeof(p_plans)<>'array' or jsonb_array_length(p_plans)>120 then raise exception 'Planilha fora do limite';end if;
 perform pg_advisory_xact_lock(hashtextextended(auth.uid()::text||'workbook-plan',0));
 if exists(select 1 from public.workbook_imports where digest=p_digest) then raise exception 'Esta planilha já foi importada';end if;
 insert into public.workbook_imports(digest) values(p_digest) returning id into batch;
 for r in select value from jsonb_array_elements(p_rules) loop
 if exists(select 1 from public.recurring_rules where lower(trim(description))=lower(trim(r->>'description'))
 and kind=r->>'kind' and channel=r->>'channel' and start_month<=r->>'end_month' and coalesce(end_month,'9999-12')>=r->>'start_month') then
 raise exception 'Já existe planejamento recorrente sobreposto: %',r->>'description';end if;
 if exists(select 1 from public.cash_items where lower(trim(description))=lower(trim(r->>'description')) and kind=r->>'kind'
 and to_char(due_date,'YYYY-MM') between r->>'start_month' and r->>'end_month') then
 raise exception 'Já existe conta/receita manual neste período: %. Revise antes de importar.',r->>'description';end if;
 insert into public.recurring_rules(description,kind,channel,category,amount_cents,start_month,end_month,due_day,match_pattern,card_id,account_id,source_batch_id)
 values(r->>'description',r->>'kind',r->>'channel',r->>'category',(r->>'amount_cents')::bigint,r->>'start_month',r->>'end_month',(r->>'due_day')::int,
 coalesce(r->>'match_pattern',r->>'description'),(r->>'card_id')::uuid,(r->>'account_id')::uuid,batch) returning id into new_rule;
 for m in select jsonb_array_elements_text(coalesce(r->'settled_months','[]'::jsonb)) loop
 if m<r->>'start_month' or m>r->>'end_month' then raise exception 'Situação fora do período';end if;
 insert into public.recurrence_states(rule_id,month,status) values(new_rule,m,'realized');
 end loop;
 end loop;
 for p in select value from jsonb_array_elements(p_plans) loop
 if p_replace_targets then
 insert into public.monthly_plans(month,savings_target_cents) values(p->>'month',(p->>'savings_target_cents')::bigint)
 on conflict(user_id,month) do update set savings_target_cents=excluded.savings_target_cents;
 else
 insert into public.monthly_plans(month,savings_target_cents) values(p->>'month',(p->>'savings_target_cents')::bigint)
 on conflict(user_id,month) do nothing;
 end if;
 end loop;
 return batch;end $$;
revoke all on function public.import_workbook_plan(text,jsonb,jsonb,boolean) from public,anon;
grant execute on function public.import_workbook_plan(text,jsonb,jsonb,boolean) to authenticated;

