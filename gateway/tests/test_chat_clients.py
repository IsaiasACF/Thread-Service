import asyncio
import json

import httpx
import pytest

from chat_cases import CASES, USER, CHANNEL, MESSAGE, REPLY
from gateway.app.graphql.errors import GatewayError


def invoke(case, handler, *, args=None, base_url="http://service.invalid"):
    requests = []
    def transport(request):
        requests.append(request)
        return handler(request)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            client = case["cls"](http, base_url)
            return await getattr(client, case["method"])(*(case["args"] if args is None else args))
    return lambda: asyncio.run(run()), requests


@pytest.mark.parametrize("case", CASES, ids=lambda c:c["root"])
def test_each_client_uses_exact_rest_contract(case):
    run, requests = invoke(case, lambda _: httpx.Response(201 if case["body"] else 200, json=case["rest"]))
    result = run()
    assert ([dto.model_dump() for dto in result] if isinstance(result,list) else result.model_dump()) == case["rest"]
    assert len(requests) == 1
    request = requests[0]
    assert request.method == case["http_method"]
    assert request.url.path == case["path"]
    assert request.url.host == "service.invalid"
    assert request.url.query == b""
    assert (json.loads(request.content) if request.content else None) == case["body"]


@pytest.mark.parametrize("case", CASES, ids=lambda c:c["root"])
@pytest.mark.parametrize("bad", [None, {}, {"items": []}, [None]])
def test_required_dto_and_list_shape_are_validated(case, bad):
    run, _ = invoke(case, lambda _: httpx.Response(200, json=bad))
    with pytest.raises(GatewayError) as caught:
        run()
    assert caught.value.extensions == {"code":"BAD_UPSTREAM_RESPONSE", "service":case["service"]}


@pytest.mark.parametrize("case", CASES, ids=lambda c:c["root"])
def test_missing_fields_and_wrong_types_never_coerce(case):
    dto = case["rest"][0] if isinstance(case["rest"],list) else case["rest"]
    for field in dto:
        for bad_value in [None, 123, False]:
            invalid = {**dto, field:bad_value}
            payload = [invalid] if isinstance(case["rest"],list) else invalid
            run, _ = invoke(case, lambda _: httpx.Response(200, json=payload))
            with pytest.raises(GatewayError) as caught:
                run()
            assert caught.value.extensions["code"] == "BAD_UPSTREAM_RESPONSE"
        payload = {key:value for key,value in dto.items() if key != field}
        if isinstance(case["rest"],list): payload = [payload]
        run, _ = invoke(case, lambda _: httpx.Response(200, json=payload))
        with pytest.raises(GatewayError): run()


@pytest.mark.parametrize("case", [c for c in CASES if isinstance(c["rest"],list)], ids=lambda c:c["root"])
def test_empty_lists_are_real_empty_results(case):
    run, _ = invoke(case, lambda _: httpx.Response(200, json=[]))
    assert run() == []


@pytest.mark.parametrize("case", [CASES[0], CASES[3], CASES[5], CASES[6], CASES[7], CASES[8]], ids=lambda c:c["root"])
def test_mismatched_resource_or_parent_is_bad_response(case):
    data = case["rest"][0] if isinstance(case["rest"],list) else case["rest"]
    keys = [key for key in ("channel_id","message_id","author_id") if key in data]
    if case["method"] in {"get_user","get_channel"}: keys=["id"]
    if case["method"] in {"list_messages","list_replies"}: keys.remove("author_id")
    for key in keys:
        payload = {**data, key:"different"}
        if isinstance(case["rest"],list): payload=[payload]
        run, _ = invoke(case, lambda _: httpx.Response(200,json=payload))
        with pytest.raises(GatewayError) as caught: run()
        assert caught.value.extensions["code"] == "BAD_UPSTREAM_RESPONSE"


@pytest.mark.parametrize("case", [CASES[1],CASES[4],CASES[6],CASES[8]], ids=lambda c:c["root"])
@pytest.mark.parametrize("failure", ["timeout","connection","server","json"])
def test_posts_are_never_retried_even_after_ambiguous_failure(case, failure):
    def handler(request):
        if failure=="timeout": raise httpx.ReadTimeout("private",request=request)
        if failure=="connection": raise httpx.ConnectError("private",request=request)
        if failure=="server": return httpx.Response(500,text="private persistence error")
        return httpx.Response(201,text="invalid json")
    run, requests = invoke(case,handler)
    with pytest.raises(GatewayError) as caught: run()
    assert len(requests) == 1
    assert caught.value.extensions["code"] == {
        "timeout":"UPSTREAM_TIMEOUT", "connection":"UPSTREAM_UNAVAILABLE",
        "server":"BAD_UPSTREAM_RESPONSE", "json":"BAD_UPSTREAM_RESPONSE"}[failure]
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("case,args", [
    (CASES[1],[""]), (CASES[1],["x"*81]), (CASES[4],[""]), (CASES[4],["x"*81]),
    (CASES[6],["c-1","u-1",""]), (CASES[6],["c-1","u-1","x"*4001]),
    (CASES[8],["c-1","m-1","u-1","  "]),
    (CASES[8],["c-1","m-1","u"*129,"Hola"]),
    (CASES[8],["c-1","m-1","u-1","x"*4001]),
    (CASES[0],[""]), (CASES[7],["c-1",""]),
])
def test_invalid_input_fails_before_network(case,args):
    run, requests = invoke(case,lambda _:pytest.fail("No request expected"),args=args)
    with pytest.raises(GatewayError) as caught: run()
    assert caught.value.extensions["code"]=="VALIDATION_ERROR"
    assert not requests


@pytest.mark.parametrize("case,args,payload", [
    (CASES[1],["x"*80],{**USER,"display_name":"x"*80}),
    (CASES[4],["x"*80],{**CHANNEL,"name":"x"*80}),
    (CASES[6],["c-1","u-1","x"*4000],{**MESSAGE,"content":"x"*4000}),
    (CASES[8],["c-1","m-1","u"*128,"x"*4000],{**REPLY,"author_id":"u"*128,"content":"x"*4000}),
])
def test_service_length_boundaries_are_inclusive(case,args,payload):
    run,_=invoke(case,lambda _:httpx.Response(201,json=payload),args=args)
    assert run().id == payload["id"]


def test_only_replies_strip_whitespace_like_thread_service():
    run, requests=invoke(CASES[8],lambda _:httpx.Response(201,json=REPLY),
                         args=["c-1","m-1"," u-1 "," Hola "])
    assert run().content=="Hola"
    assert json.loads(requests[0].content)=={"author_id":"u-1","content":"Hola"}
    run,requests=invoke(CASES[6],lambda _:httpx.Response(201,json={**MESSAGE,"content":" Hola "}),
                        args=["c-1","u-1"," Hola "])
    assert run().content==" Hola "
    assert json.loads(requests[0].content)["content"]==" Hola "


@pytest.mark.parametrize("value", ["not-a-date","2026-11-08","2026-11-08T12:00:00"])
@pytest.mark.parametrize("case", [CASES[5],CASES[6],CASES[7],CASES[8]], ids=lambda c:c["root"])
def test_invalid_dates_are_bad_response(case,value):
    data=case["rest"][0] if isinstance(case["rest"],list) else case["rest"]
    data={**data,"created_at":value}
    if isinstance(case["rest"],list): data=[data]
    run,_=invoke(case,lambda _:httpx.Response(200,json=data))
    with pytest.raises(GatewayError): run()


def test_offsets_are_normalized_to_utc():
    run,_=invoke(CASES[6],lambda _:httpx.Response(201,json={**MESSAGE,"created_at":"2026-11-08T09:00:00-03:00"}))
    assert run().created_at=="2026-11-08T12:00:00Z"


@pytest.mark.parametrize("identifier,encoded", [("a/b ?#%","a%2Fb%20%3F%23%25"),("..","%2E%2E"),("á","%C3%A1")])
def test_opaque_ids_are_encoded_as_single_path_segment(identifier,encoded):
    run,requests=invoke(CASES[0],lambda _:httpx.Response(200,json={**USER,"id":identifier}),args=[identifier])
    assert run().id==identifier
    assert requests[0].url.raw_path==f"/api/v1/users/{encoded}".encode()


@pytest.mark.parametrize("case", CASES, ids=lambda c:c["root"])
def test_unconfigured_clients_do_not_connect(case):
    run,requests=invoke(case,lambda _:pytest.fail("No upstream configured"),base_url=None)
    with pytest.raises(GatewayError) as caught: run()
    assert caught.value.extensions["code"]=="UPSTREAM_UNAVAILABLE"
    assert not requests
