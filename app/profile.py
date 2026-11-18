from app.domain import cents


def profile_payload(data):
    if data.get('goal') not in ['emergency','short','long'] or data.get('risk') not in ['conservative','moderate','aggressive'] or data.get('expensive_debt') not in ['unknown','yes','no']:
        raise ValueError('Informe objetivo, perfil e situação das dívidas.')
    horizon=int(data['horizon_months']);months=int(data['reserve_months']);rate=int(data['savings_rate'])
    if not 1<=horizon<=600 or not 1<=months<=24 or not 0<=rate<=50:raise ValueError('Confira prazo, meses da reserva e percentual.')
    essentials=cents(str(data['essential_costs']));balance=cents(str(data['emergency_balance']))
    if not 0<essentials<=9000000000000 or not 0<=balance<=9000000000000:raise ValueError('Informe custos essenciais positivos e reserva maior ou igual a zero.')
    if type(data.get('needs_liquidity')) is not bool:raise ValueError('Informe a necessidade de resgate.')
    return dict(goal=data['goal'],risk=data['risk'],horizon_months=horizon,needs_liquidity=data['needs_liquidity'],essential_costs_cents=essentials,emergency_balance_cents=balance,reserve_months=months,savings_rate=rate,expensive_debt=data['expensive_debt'])
