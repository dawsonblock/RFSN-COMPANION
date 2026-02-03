from companion_exec.tokens_hmac import mint, verify

def test_token_roundtrip():
    s = b"secret"
    tok = mint(s, token_type="send_email", ttl_s=10, bind={"qid":"x","spec_hash":"y"})
    a = verify(s, tok)
    assert a is not None
    assert a.token_type == "send_email"
    assert a.bind["qid"] == "x"
