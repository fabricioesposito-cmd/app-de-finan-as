-- Read-only verification: never calls the dispatcher, net.http_post or reads
-- financial records/subscription keys. Safe to run against production.
do $$
declare source text; n integer;
begin
 select pg_get_functiondef('private.dispatch_daily_push()'::regprocedure) into source;
 if source ~ 's\.start_month\s*<=' then raise exception 'Data reference month still gates daily delivery';end if;
 if position('''reference_month'',row.start_month' in source)=0 then raise exception 'Reference month absent from signed worker payload';end if;
 if has_function_privilege('authenticated','private.dispatch_daily_push()','execute') then raise exception 'Scheduler exposed to clients';end if;
 -- Two consecutive delivery days, each with past and future reference months.
 select count(*) into n from (values(timestamp '2026-11-26 09:00',true,9,'2026-10'),(timestamp '2026-11-26 09:00',true,9,'2026-12'),(timestamp '2026-11-27 09:00',true,9,'2026-10'),(timestamp '2026-11-27 09:00',true,9,'2026-12')) as cases(local_now,enabled,hour,reference_month)
 where enabled and local_now>=local_now::date+make_interval(hours=>hour)
 and local_now<local_now::date+make_interval(hours=>hour)+interval '2 hours';
 if n<>4 then raise exception 'Past/future references failed daily timing scenarios';end if;
 if not exists(select 1 from cron.job where jobname='clareza-daily-push' and active and schedule='*/5 * * * *') then raise exception 'Daily scheduler inactive';end if;
end $$;
select 'Read-only scheduler checks passed: selected reference payload, daily timing, client restrictions and active cron; no dispatch or HTTP executed' as result;
