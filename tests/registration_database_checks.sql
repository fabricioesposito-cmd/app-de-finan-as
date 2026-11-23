begin;
insert into auth.users(id,email) values('00000000-0000-4000-8000-000000000099','registration-test@example.invalid');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"00000000-0000-4000-8000-000000000099","role":"authenticated"}',true);
do $test$ declare c uuid;i uuid;d jsonb;t timestamptz:='2026-11-20T14:30:00Z';begin
insert into public.cards(name,issuer,closing,due) values('Fixture','Fixture',11,18) returning id into c;
insert into public.cash_items(description,kind,category,amount_cents,due_date,settled,registered_at) values('Fixture','expense','Mercado',1500,'2026-11-11',true,t) returning id into i;
d:=jsonb_build_object('channel','card','card_id',c,'month','2026-12','date','2026-11-11','description','Fixture','category','Mercado','amount_cents',1500,'settled',true);
perform public.edit_manual_entry('cash',i,d);
if not exists(select 1 from public.card_events where id=i and registered_at=t) then raise exception 'Registration lost on conversion';end if;
perform public.edit_manual_entry('event',i,d||'{"amount_cents":2000}'::jsonb);
if not exists(select 1 from public.card_events where id=i and registered_at=t and amount_cents=2000) then raise exception 'Edit reordered registration';end if;
perform public.edit_manual_entry('event',i,d||'{"channel":"cash"}'::jsonb);
if not exists(select 1 from public.cash_items where id=i and registered_at=t) then raise exception 'Registration lost on return';end if;
insert into public.card_events(card_id,month,purchase_date,description,amount_cents,category) values(c,'2026-12','2026-11-01','New fixture',1000,'Mercado') returning id into i;
if not exists(select 1 from public.card_events where id=i and registered_at is not null) then raise exception 'New record lacks timestamp';end if;
end $test$;
rollback; select 'Registration defaults and preservation across edits/conversions passed; fixtures rolled back' as result;
