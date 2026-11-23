begin;
insert into auth.users(id,email) values('00000000-0000-4000-8000-000000000083','push-schedule@example.invalid');
insert into public.push_subscriptions(user_id,endpoint,keys,hour)
values('00000000-0000-4000-8000-000000000083','https://web.push.apple.com/scheduler-fixture','{"auth":"fixture","p256dh":"fixture"}',extract(hour from now() at time zone 'America/Sao_Paulo')::integer);
insert into public.cash_items(user_id,description,kind,category,amount_cents,due_date,settled)
values('00000000-0000-4000-8000-000000000083','Scheduler fixture','income','Salário',500000,current_date,true);
insert into public.push_subscriptions(user_id,endpoint,keys,hour,start_month)
values('00000000-0000-4000-8000-000000000083','https://web.push.apple.com/future-fixture','{"auth":"fixture","p256dh":"fixture"}',extract(hour from now() at time zone 'America/Sao_Paulo')::integer,to_char((now() at time zone 'America/Sao_Paulo')+interval '1 month','YYYY-MM'));
do $$ declare n integer;q record;body_data jsonb;secret text;begin
 n:=private.dispatch_daily_push();
 if exists(select 1 from private.push_deliveries d join public.push_subscriptions s on s.id=d.subscription_id where s.endpoint='https://web.push.apple.com/future-fixture') then raise exception 'Future start month queued before due';end if;
 if n<1 then raise exception 'Due subscription not queued';end if;
 select http_job.* into q from net.http_request_queue http_job join private.push_deliveries d on d.request_id=http_job.id join public.push_subscriptions s on s.id=d.subscription_id where s.endpoint='https://web.push.apple.com/scheduler-fixture';
 if not found then raise exception 'No HTTP job';end if;
 body_data:=convert_from(q.body,'utf8')::jsonb;
 if jsonb_array_length(body_data->'data'->'cash_items')<>1 or body_data->'data'->'cash_items'->0->>'description'<>'Scheduler fixture' then raise exception 'Worker data ownership mismatch';end if;
 select decrypted_secret into secret from vault.decrypted_secrets where name='clareza_push_job_secret';
 if q.headers->>'X-Push-Signature'<>encode(extensions.hmac(convert_from(q.body,'utf8'),secret,'sha256'),'hex') then raise exception 'HMAC does not match actual transmitted bytes';end if;
 perform private.dispatch_daily_push();
 if exists(select 1 from private.push_deliveries d join public.push_subscriptions s on s.id=d.subscription_id where s.endpoint='https://web.push.apple.com/scheduler-fixture' and attempts<>1) then raise exception 'Immediate duplicate enqueued';end if;
 insert into net._http_response(id,status_code,content) values(q.id,200,'{"ok":true,"status":"sent"}');
 perform private.dispatch_daily_push();
 if not exists(select 1 from private.push_deliveries d join public.push_subscriptions s on s.id=d.subscription_id where s.endpoint='https://web.push.apple.com/scheduler-fixture' and d.delivered_at is not null and s.last_sent_at is not null) then raise exception 'Delivery receipt not recorded';end if;
 update public.push_subscriptions set start_month=to_char(now() at time zone 'America/Sao_Paulo','YYYY-MM') where endpoint='https://web.push.apple.com/future-fixture';
 perform private.dispatch_daily_push();
 if not exists(select 1 from private.push_deliveries d join public.push_subscriptions s on s.id=d.subscription_id where s.endpoint='https://web.push.apple.com/future-fixture') then raise exception 'Start month arrival did not queue notification';end if;
end $$;
rollback;
select 'Due job, exact HTTP HMAC, owner-scoped data deduplication and delivery acknowledgement passed; no HTTP requests sent (transaction rolled back)' as result;
