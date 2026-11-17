begin;
insert into auth.users(id,email) values ('00000000-0000-4000-8000-000000000011','costs-test-a@example.invalid'),('00000000-0000-4000-8000-000000000012','costs-test-b@example.invalid');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"00000000-0000-4000-8000-000000000011","role":"authenticated"}',true);
do $test$ declare card uuid; entry uuid; begin
insert into public.cards(name,issuer,closing,due) values('Cartão teste','Fictício',5,12) returning id into card;
insert into public.cash_items(description,kind,category,amount_cents,due_date) values('Salário teste','income','Salário',800000,'2026-11-05') returning id into entry;
insert into public.monthly_plans(month,savings_target_cents) values('2026-11',200000);
insert into public.card_settlements(card_id,month,paid_cents,bill_total_cents) values(card,'2026-11',50000,150000);
if (select amount_cents from public.cash_items where id=entry)<>800000 then raise exception 'Valor incorreto'; end if;
begin
 update public.cash_items set user_id='00000000-0000-4000-8000-000000000012' where id=entry;
 raise exception 'Permitiu mudar proprietário';
exception when insufficient_privilege then null; end;
perform set_config('request.jwt.claims','{"sub":"00000000-0000-4000-8000-000000000012","role":"authenticated"}',true);
if exists(select 1 from public.cash_items) or exists(select 1 from public.monthly_plans) or exists(select 1 from public.card_settlements) then raise exception 'Vazamento entre usuários'; end if;
begin
 insert into public.card_settlements(card_id,month,paid_cents) values(card,'2026-11',100);
 raise exception 'Permitiu cartão de outro usuário';
exception when foreign_key_violation then null; end;
end $test$;
rollback;
select 'Custos: gravação, RLS, proprietário e vínculo de cartão validados; fixtures revertidas' as result;
