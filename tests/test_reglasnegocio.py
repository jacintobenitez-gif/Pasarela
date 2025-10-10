from reglasnegocio.reglasnegocio import clasificar_mensajes
def test_baseline_reglas():
    out = clasificar_mensajes('hola')
    assert 'valido' in out and 'score' in out
