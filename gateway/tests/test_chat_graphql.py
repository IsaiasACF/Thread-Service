import asyncio
import json
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient

from chat_cases import CASES, REPLY, GQL_REPLY, USER, GQL_USER
from gateway.app.clients.registry import build_clients
from gateway.app.config import Settings
from gateway.app.main import create_app


@contextmanager
def mock_gateway(handler):
    requests=[]
    def handle(request):
        requests.append(request)
        return handler(request)
    settings=Settings(_env_file=None, **{
        f"{service}_base_url":f"http://{service}.invalid"
        for service in ["users","channels","messages","threads","polls","integrals"]})
    http=httpx.AsyncClient(transport=httpx.MockTransport(handle))
    try:
        with TestClient(create_app(settings)) as client:
            client.app.state.clients=build_clients(http,settings)
            yield client,requests
    finally:
        asyncio.run(http.aclose())


def execute(client,case):
    return client.post("/graphql",json={"query":case["query"],"variables":case["variables"]})


@pytest.mark.parametrize("case", CASES, ids=lambda c:c["root"])
def test_nine_operations_map_variables_to_rest_and_dtos_to_camel_case(case):
    with mock_gateway(lambda _:httpx.Response(201 if case["body"] else 200,json=case["rest"])) as (client,requests):
        response=execute(client,case)
        assert response.status_code==200
        assert response.json()=={"data":{case["root"]:case["gql"]}}
        assert len(requests)==1
        request=requests[0]
        assert request.url.host==case["service"]+".invalid"
        assert request.method==case["http_method"]
        assert request.url.path==case["path"]
        assert (json.loads(request.content) if request.content else None)==case["body"]


@pytest.mark.parametrize("case",CASES,ids=lambda c:c["root"])
@pytest.mark.parametrize("status,code", [(404,"NOT_FOUND"),(422,"VALIDATION_ERROR"),
    (403,"FORBIDDEN"),(409,"CONFLICT"),(500,"BAD_UPSTREAM_RESPONSE"),
    (502,"BAD_UPSTREAM_RESPONSE"),(503,"UPSTREAM_UNAVAILABLE")])
def test_upstream_failures_are_public_graphql_errors(case,status,code):
    with mock_gateway(lambda _:httpx.Response(status,json={"detail":"private database error"})) as (client,requests):
        body=execute(client,case).json()
        assert len(body["errors"])==1
        error=body["errors"][0]
        assert error["extensions"]=={"code":code,"service":case["service"],"httpStatus":status}
        assert error["path"]==[case["root"]]
        assert "private" not in json.dumps(body)
        assert len(requests)==1
        assert not body.get("data") or body["data"][case["root"]] is None


@pytest.mark.parametrize("case",CASES,ids=lambda c:c["root"])
@pytest.mark.parametrize("failure",["timeout","unavailable","invalid_json","invalid_dto"])
def test_transport_and_contract_failures_never_return_success(case,failure):
    def handler(request):
        if failure=="timeout": raise httpx.ReadTimeout("private-url",request=request)
        if failure=="unavailable": raise httpx.ConnectError("private-url",request=request)
        if failure=="invalid_json": return httpx.Response(200,text="private invalid json")
        return httpx.Response(200,json={"private":"invalid DTO"})
    with mock_gateway(handler) as (client,requests):
        body=execute(client,case).json()
        assert body["errors"][0]["extensions"]=={
            "code":{"timeout":"UPSTREAM_TIMEOUT","unavailable":"UPSTREAM_UNAVAILABLE"}.get(failure,"BAD_UPSTREAM_RESPONSE"),
            "service":case["service"]}
        assert "private" not in json.dumps(body)
        assert len(requests)==1


def test_empty_thread_and_lists_are_not_errors():
    for case in [CASES[2],CASES[5],CASES[7]]:
        with mock_gateway(lambda _:httpx.Response(200,json=[])) as (client,_):
            assert execute(client,case).json()=={"data":{case["root"]:[]}}


def test_reply_response_and_subsequent_read_use_persisted_api_values():
    stored=[]
    def handler(request):
        if request.method=="POST":
            stored.append({**REPLY,"id":"persisted-reply","content":"Guardado por la API"})
            return httpx.Response(201,json=stored[0])
        return httpx.Response(200,json=stored)
    expected={**GQL_REPLY,"id":"persisted-reply","content":"Guardado por la API"}
    with mock_gateway(handler) as (client,requests):
        assert execute(client,CASES[8]).json()=={"data":{"createReply":expected}}
        assert execute(client,CASES[7]).json()=={"data":{"replies":[expected]}}
        assert [r.method for r in requests]==["POST","GET"]
    # This models the REST API's persistence semantics; it does not prove MongoDB durability.


def test_pending_domains_do_not_block_chat_in_same_query():
    with mock_gateway(lambda _:httpx.Response(200,json=USER)) as (client,requests):
        body=client.post("/graphql",json={"query":'{ user(id:"u-1"){ id displayName } integral(id:"i"){ id } poll(id:"p"){ pollId } }'}).json()
        assert body["data"]=={"user":GQL_USER,"integral":None,"poll":None}
        assert {e["extensions"]["service"] for e in body["errors"]}=={"integrals","polls"}
        assert all(e["extensions"]["code"]=="NOT_IMPLEMENTED" for e in body["errors"])
        assert len(requests)==1
        assert requests[0].url.host=="users.invalid"
        assert client.get("/health").json()=={"status":"ok"}


@pytest.mark.parametrize("case,variables", [
    (CASES[1],{"name":""}), (CASES[4],{"name":"x"*81}),
    (CASES[6],{"c":"c-1","a":"u-1","text":"x"*4001}),
    (CASES[8],{"c":"c-1","m":"m-1","a":"u-1","text":"  "}),
])
def test_invalid_graphql_domain_inputs_never_call_upstream(case,variables):
    with mock_gateway(lambda _:pytest.fail("Invalid input must not call upstream")) as (client,requests):
        body=client.post("/graphql",json={"query":case["query"],"variables":variables}).json()
        assert body["errors"][0]["extensions"]["code"]=="VALIDATION_ERROR"
        assert not requests
