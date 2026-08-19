from modules.coupa_scraper import _bloquear_recursos_pesados


class _FakeRequest:
    def __init__(self, resource_type: str):
        self.resource_type = resource_type


class _FakeRoute:
    def __init__(self, resource_type: str):
        self.request = _FakeRequest(resource_type)
        self.aborted = False
        self.continued = False

    def abort(self):
        self.aborted = True
        return "aborted"

    def continue_(self):
        self.continued = True
        return "continued"


def test_bloqueia_imagem_midia_fonte_e_stylesheet():
    for tipo in ("image", "media", "font", "stylesheet"):
        route = _FakeRoute(tipo)
        _bloquear_recursos_pesados(route)
        assert route.aborted is True
        assert route.continued is False


def test_libera_documento_e_script():
    for tipo in ("document", "script", "xhr", "fetch"):
        route = _FakeRoute(tipo)
        _bloquear_recursos_pesados(route)
        assert route.continued is True
        assert route.aborted is False
