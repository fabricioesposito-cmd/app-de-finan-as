
alter table public.recurring_rules add column first_installment integer not null default 1 check(first_installment between 1 and 600);
alter table public.recurring_rules add column total_installments integer check(total_installments between 1 and 600);
alter table public.recurring_rules add column source_import_id uuid;
alter table public.recurring_rules add constraint rule_source_import_owner foreign key(source_import_id,user_id) references public.imports(id,user_id) on delete cascade;
create index recurring_import_idx on public.recurring_rules(source_import_id,user_id);
create or replace function public.confirm_import_with_links(p_card uuid,p_month text,p_digest text,p_expected bigint,p_rows jsonb)
returns uuid language plpgsql security invoker set search_path='' as $$
declare batch uuid;e record;next_month text;pattern text;remaining int;begin
 batch:=public.confirm_import(p_card,p_month,p_digest,p_expected,p_rows);
 for e in select id,payload from public.entries where import_id=batch loop
 if coalesce(e.payload->>'match_id','')<>'' then
 perform public.link_statement_entry(e.id,e.payload->>'match_type',(e.payload->>'match_id')::uuid,p_month);end if;
 if coalesce(e.payload->>'future_mode','') in ('installment','monthly') and (e.payload->>'amount')::bigint>0 and coalesce(e.payload->>'match_type','')<>'rule' then
 next_month:=to_char((p_month||'-01')::date+interval '1 month','YYYY-MM');
 pattern:=coalesce(nullif(e.payload->>'future_description',''),e.payload->>'description');
 remaining:=(e.payload->>'total')::int-(e.payload->>'current')::int;
 if e.payload->>'future_mode'='installment' and remaining<=0 then raise exception 'Não há parcelas futuras';end if;
 if exists(select 1 from public.recurring_rules r where r.card_id=p_card and lower(trim(r.match_pattern))=lower(trim(pattern)) and (r.end_month is null or r.end_month>=next_month)) then
 raise exception 'Já existe recorrência para %. Vincule a previsão ou desative a criação futura.',pattern;end if;
 insert into public.recurring_rules(description,kind,channel,category,amount_cents,start_month,due_day,occurrence_count,schedule_type,match_pattern,card_id,first_installment,total_installments,source_import_id)
 values(pattern,'expense','card',e.payload->>'category',(e.payload->>'amount')::bigint,next_month,
 (select due from public.cards where id=p_card),
 case when e.payload->>'future_mode'='installment' then remaining else null end,
 case when e.payload->>'future_mode'='installment' then 'installment' else 'monthly' end,pattern,p_card,
 case when e.payload->>'future_mode'='installment' then (e.payload->>'current')::int+1 else 1 end,
 case when e.payload->>'future_mode'='installment' then (e.payload->>'total')::int else null end,batch);
 end if;
 end loop;
 return batch;end $$;
revoke all on function public.confirm_import_with_links(uuid,text,text,bigint,jsonb) from public,anon;
grant execute on function public.confirm_import_with_links(uuid,text,text,bigint,jsonb) to authenticated;

