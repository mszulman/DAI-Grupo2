from ombu import llm


class RespuestaFalsa:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b"{}"


def test_post_json_identifica_el_cliente_con_user_agent(monkeypatch):
    recibidos = {}

    def urlopen(request, **_kwargs):
        recibidos["user_agent"] = request.get_header("User-agent")
        return RespuestaFalsa()

    monkeypatch.setattr(llm.urllib.request, "urlopen", urlopen)

    llm._post_json("https://api.example.test", {}, {})

    assert recibidos["user_agent"] == "DAI-Grupo2/1.0"
