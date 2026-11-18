create or replace function public.confirm_import(p_card uuid,p_month text,p_digest text,p_expected bigint,p_rows jsonb)
returns uuid language plpgsql security invoker set search_path='' as $$
declare batch uuid; r jsonb; calculated bigint; begin
 if auth.uid() is null then raise exception 'Login necessário'; end if;
 perform pg_advisory_xact_lock(hashtextextended(auth.uid()::text||p_card::text||p_month,0));
 if jsonb_typeof(p_rows)<>'array' or jsonb_array_length(p_rows)=0 or jsonb_array_length(p_rows)>10000 then
 raise exception 'Lista inválida'; end if;
 for r in select value from jsonb_array_elements(p_rows) loop
 if jsonb_typeof(r->'amount')<>'number' or (r->>'amount')::numeric<>trunc((r->>'amount')::numeric)
 or length(coalesce(r->>'description',''))=0 or length(r->>'description')>1000
 or length(trim(coalesce(r->>'category',''))) not between 1 and 60
 or coalesce(r->>'kind','') not in ('compra','estorno','credito','juros','tarifa')
 or coalesce((r->>'current')::int,0)<1 or coalesce((r->>'total')::int,0)<(r->>'current')::int or (r->>'total')::int>120
 or coalesce(r->>'date','') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
 then raise exception 'Lançamento inválido'; end if;
 perform (r->>'date')::date;
 if (r->>'kind') in ('credito','estorno') and (r->>'amount')::bigint>0 then raise exception 'Crédito deve ser negativo'; end if;
 if (r->>'kind') in ('compra','juros','tarifa') and (r->>'amount')::bigint<0 then raise exception 'Despesa deve ser positiva'; end if;
 if exists(select 1 from public.entries e join public.imports i on i.id=e.import_id
 where i.card_id=p_card and i.month=p_month
 and e.payload->>'date'=r->>'date'
 and lower(trim(e.payload->>'description'))=lower(trim(r->>'description'))
 and e.payload->>'amount'=r->>'amount' and e.payload->>'current'=r->>'current'
 and e.payload->>'total'=r->>'total' and e.payload->>'kind'=r->>'kind') then
 raise exception 'Possível duplicidade. Revise a importação anterior.'; end if;
 end loop;
 select sum((value->>'amount')::bigint) into calculated from jsonb_array_elements(p_rows);
 if calculated<>p_expected then raise exception 'Total divergente'; end if;
 insert into public.imports(card_id,month,digest,expected) values(p_card,p_month,p_digest,p_expected) returning id into batch;
 for r in select value from jsonb_array_elements(p_rows) loop
 insert into public.entries(import_id,payload) values(batch,r);
 if coalesce((r->>'remember')::boolean,false) then
 insert into public.category_rules(description,category) values(r->>'description',r->>'category')
 on conflict(user_id,description) do update set category=excluded.category;
 end if;
 end loop;
 return batch;
end $$;
revoke all on function public.confirm_import(uuid,text,text,bigint,jsonb) from public,anon;
grant execute on function public.confirm_import(uuid,text,text,bigint,jsonb) to authenticated;
