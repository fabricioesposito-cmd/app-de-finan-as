begin;
insert into auth.users(id,email) values('00000000-0000-4000-8000-000000000001','finance-test-a@example.invalid'),('00000000-0000-4000-8000-000000000002','finance-test-b@example.invalid');
set local role authenticated;
select set_config('request.jwt.claims','{"sub":"00000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
do $test$ declare card uuid; batch uuid; rows jsonb := '[{"date":"2026-11-01","description":"Teste fictício","amount":1000,"kind":"compra","current":2,"total":5,"category":"Compras","source_line":2}]'; begin
insert into public.cards(name,issuer,closing,due) values('Teste','Fictício',5,12) returning id into card;
batch:=public.confirm_import(card,'2026-11','test-digest',1000,rows);
if (select count(*) from public.entries)<>1 then raise exception 'Gravação falhou'; end if;
begin perform public.confirm_import(card,'2026-11','test-2',999,rows); raise exception 'Aceitou duplicidade'; exception when others then if sqlerrm='Aceitou duplicidade' then raise; end if; end;
begin perform public.confirm_import(card,'2026-12','test-3',999,rows); raise exception 'Aceitou total errado'; exception when others then if sqlerrm='Aceitou total errado' then raise; end if; end;
perform set_config('request.jwt.claims','{"sub":"00000000-0000-4000-8000-000000000002","role":"authenticated"}',true);
if (select count(*) from public.cards)<>0 or (select count(*) from public.entries)<>0 then raise exception 'Vazamento de dados'; end if;
perform set_config('request.jwt.claims','{"sub":"00000000-0000-4000-8000-000000000001","role":"authenticated"}',true);
delete from public.imports where id=batch;
if (select count(*) from public.entries)<>0 then raise exception 'Desfazer deixou lançamentos'; end if;
end $test$;
rollback;
