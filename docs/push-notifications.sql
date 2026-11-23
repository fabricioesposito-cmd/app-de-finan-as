-- Web Push preferences belong to the signed-in owner. Private scheduler alone
-- can assemble cross-table jobs. No service-role key is installed on the app.
create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table public.push_subscriptions (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
 endpoint text not null unique check(length(endpoint) between 20 and 4096),
 keys jsonb not null check(jsonb_typeof(keys)='object'),
 enabled boolean not null default true,
 hour integer not null default 9 check(hour between 0 and 23),
 created_at timestamptz not null default now(),
 last_sent_at timestamptz,
 last_test_at timestamptz
);
alter table public.push_subscriptions enable row level security;
create policy push_owner on public.push_subscriptions to authenticated
 using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
grant select,insert,update,delete on public.push_subscriptions to authenticated;
revoke all on public.push_subscriptions from anon;
create index push_subscriptions_owner on public.push_subscriptions(user_id);

create function public.save_push_subscription(p_endpoint text,p_keys jsonb,p_hour integer default 9)
returns uuid language plpgsql security invoker set search_path='' as $$
declare result uuid;
begin
 if auth.uid() is null then raise exception 'Entre na sua conta.';end if;
 insert into public.push_subscriptions(endpoint,keys,hour)
 values(p_endpoint,p_keys,p_hour)
 on conflict(endpoint) do update set keys=excluded.keys,hour=excluded.hour,enabled=true
 where push_subscriptions.user_id=auth.uid()
 returning id into result;
 if result is null then raise exception 'Este aparelho está vinculado a outra conta.';end if;
 return result;
end $$;
revoke all on function public.save_push_subscription(text,jsonb,integer) from public,anon;
grant execute on function public.save_push_subscription(text,jsonb,integer) to authenticated;

create function public.claim_push_test(p_id uuid) returns boolean
language plpgsql security invoker set search_path='' as $$
begin
 update public.push_subscriptions set last_test_at=now()
 where id=p_id and user_id=auth.uid() and enabled
 and (last_test_at is null or last_test_at<now()-interval '1 minute');
 return found;
end $$;
revoke all on function public.claim_push_test(uuid) from public,anon;
grant execute on function public.claim_push_test(uuid) to authenticated;

create table private.push_deliveries (
 subscription_id uuid not null references public.push_subscriptions(id) on delete cascade,
 day date not null,
 attempts integer not null default 0,
 request_id bigint,
 attempted_at timestamptz,
 delivered_at timestamptz,
 primary key(subscription_id,day)
);
alter table private.push_deliveries enable row level security;
create policy scheduler_only on private.push_deliveries to authenticated using (false) with check (false);
revoke all on private.push_deliveries from public,anon,authenticated;

-- Internal cron function, deliberately not exposed through PostgREST. Only the
-- postgres scheduler can call it. Every source read has an explicit owner filter.
create function private.dispatch_daily_push() returns integer
language plpgsql security definer set search_path='' as $$
declare
 row record; response record; job_data jsonb; table_name text; rows_data jsonb;
 body_text text; secret text; request bigint; total integer:=0; result_json jsonb;
 local_now timestamp:=now() at time zone 'America/Sao_Paulo';
begin
 if not pg_try_advisory_xact_lock(721834591) then return 0;end if;
 -- A response contains only status, never financial values or endpoint keys.
 for row in select d.subscription_id,d.day,d.request_id from private.push_deliveries d
 where d.delivered_at is null and d.request_id is not null and d.day>=local_now::date-1
 loop
  select status_code,content into response from net._http_response where id=row.request_id;
  if found and response.status_code=200 then
   begin result_json:=response.content::jsonb;exception when invalid_text_representation then result_json:='{}'::jsonb;end;
   if result_json->>'status'='sent' then
    update private.push_deliveries set delivered_at=now() where subscription_id=row.subscription_id and day=row.day;
    update public.push_subscriptions set last_sent_at=now() where id=row.subscription_id;
   elsif result_json->>'status'='expired' then
    update public.push_subscriptions set enabled=false where id=row.subscription_id;
   end if;
  end if;
 end loop;
 select decrypted_secret into secret from vault.decrypted_secrets where name='clareza_push_job_secret';
 if secret is null then return 0;end if;
 for row in
  select s.* from public.push_subscriptions s
  left join private.push_deliveries d on d.subscription_id=s.id and d.day=local_now::date
  where s.enabled and local_now >= local_now::date+make_interval(hours=>s.hour)
   and local_now < local_now::date+make_interval(hours=>s.hour)+interval '2 hours'
   and d.delivered_at is null and coalesce(d.attempts,0)<3
   and (d.attempted_at is null or d.attempted_at<now()-interval '10 minutes')
  order by s.id limit 20
 loop
  job_data:='{}'::jsonb;
  foreach table_name in array array['cards','imports','budgets','entries','cash_items','monthly_plans','card_settlements','accounts','recurring_rules','recurrence_states','card_events','entry_matches','investor_profiles','savings_schedules']
  loop
   execute format('select coalesce(jsonb_agg(to_jsonb(t)),''[]''::jsonb) from public.%I t where user_id=$1',table_name)
    into rows_data using row.user_id;
   job_data:=job_data||jsonb_build_object(table_name,rows_data);
  end loop;
  body_text:=jsonb_build_object('sent_at',extract(epoch from now()),'day',local_now::date,
   'subscription',jsonb_build_object('endpoint',row.endpoint,'keys',row.keys),'data',job_data)::text;
  request:=net.http_post(
   url:='https://clareza-financas.onrender.com/api/push/daily',
   headers:=jsonb_build_object('Content-Type','application/json','X-Push-Signature',encode(extensions.hmac(body_text,secret,'sha256'),'hex')),
   body:=body_text::jsonb,timeout_milliseconds:=120000);
  insert into private.push_deliveries(subscription_id,day,attempts,request_id,attempted_at)
   values(row.id,local_now::date,1,request,now())
   on conflict(subscription_id,day) do update set attempts=push_deliveries.attempts+1,request_id=excluded.request_id,attempted_at=excluded.attempted_at;
  total:=total+1;
 end loop;
 delete from private.push_deliveries where day<local_now::date-7;
 delete from cron.job_run_details where jobid in (select jobid from cron.job where jobname='clareza-daily-push') and end_time<now()-interval '3 days';
 return total;
end $$;
revoke all on function private.dispatch_daily_push() from public,anon,authenticated;
-- Enabled only after the app worker is deployed and its HMAC secret is in Vault:
-- select cron.schedule('clareza-daily-push','*/5 * * * *','select private.dispatch_daily_push();');
