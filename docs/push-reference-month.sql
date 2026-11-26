-- The saved month selects financial data; every enabled subscription is due
-- daily at its chosen hour, regardless of whether that month is past or future.
-- Existing month choices and permissions are preserved.
create or replace function private.dispatch_daily_push() returns integer
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
   'reference_month',row.start_month,'subscription',jsonb_build_object('endpoint',row.endpoint,'keys',row.keys),'data',job_data)::text;
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
