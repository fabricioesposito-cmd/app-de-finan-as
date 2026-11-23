begin;
insert into auth.users(id,email) values('00000000-0000-4000-8000-000000000081','push-owner@example.invalid'),('00000000-0000-4000-8000-000000000082','push-other@example.invalid');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"00000000-0000-4000-8000-000000000081","role":"authenticated"}',true);
do $$ declare i uuid;begin
 i:=public.save_push_subscription('https://web.push.apple.com/fixture-owner','{"p256dh":"fixture","auth":"fixture"}',9);
 if i is distinct from public.save_push_subscription('https://web.push.apple.com/fixture-owner','{"p256dh":"fixture","auth":"fixture"}',9) then raise exception 'Upsert duplicated subscription';end if;
 if not public.claim_push_test(i) or public.claim_push_test(i) then raise exception 'Test rate limit failed';end if;
end $$;
select set_config('request.jwt.claims','{"sub":"00000000-0000-4000-8000-000000000082","role":"authenticated"}',true);
do $$ begin
 if exists(select 1 from public.push_subscriptions where endpoint='https://web.push.apple.com/fixture-owner') then raise exception 'Cross-owner read';end if;
 begin
  perform public.save_push_subscription('https://web.push.apple.com/fixture-owner','{}',9);
  raise exception 'Stolen subscription';
 exception when insufficient_privilege then null; when raise_exception then
  if sqlerrm<>'Este aparelho está vinculado a outra conta.' then raise;end if;
 end;
 if has_function_privilege('authenticated',(select p.oid from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='private' and p.proname='dispatch_daily_push'),'execute') then raise exception 'Scheduler exposed';end if;
end $$;
rollback;
select 'Owner isolation, endpoint collision, upsert and rate limit passed; fixtures rolled back' as result;
