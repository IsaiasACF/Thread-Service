"""Independent REST/GraphQL examples based on documented contracts, not runtime DTOs."""
from gateway.app.clients.users import UsersClient
from gateway.app.clients.channels import ChannelsClient
from gateway.app.clients.messages import MessagesClient
from gateway.app.clients.threads import ThreadsClient

USER = {"id": "u-1", "display_name": "Ana"}
CHANNEL = {"id": "c-1", "name": "general"}
MESSAGE = {"id": "m-1", "channel_id": "c-1", "author_id": "u-1",
           "content": "Hola", "created_at": "2026-11-08T12:00:00Z"}
REPLY = {**MESSAGE, "id": "r-1", "message_id": "m-1"}
GQL_USER = {"id": "u-1", "displayName": "Ana"}
GQL_CHANNEL = {"id": "c-1", "name": "general"}
GQL_MESSAGE = {"id": "m-1", "channelId": "c-1", "authorId": "u-1",
               "content": "Hola", "createdAt": "2026-11-08T12:00:00Z"}
GQL_REPLY = {**GQL_MESSAGE, "id": "r-1", "messageId": "m-1"}
MSG_PATH = "/api/v1/channels/c-1/messages"
REPLY_PATH = MSG_PATH + "/m-1/replies"
SELECTIONS = {"user": "id displayName", "channel": "id name",
              "message": "id channelId authorId content createdAt",
              "reply": "id channelId messageId authorId content createdAt"}


def case(service, cls, method, args, http_method, path, body, rest, root, query, variables, gql):
    return dict(service=service, cls=cls, method=method, args=args, http_method=http_method,
                path=path, body=body, rest=rest, root=root, query=query, variables=variables, gql=gql)


CASES = [
    case("users", UsersClient, "get_user", ["u-1"], "GET", "/api/v1/users/u-1", None, USER,
         "user", "query($id:ID!){ user(id:$id){ id displayName } }", {"id":"u-1"}, GQL_USER),
    case("users", UsersClient, "create_user", ["Ana"], "POST", "/api/v1/users", {"display_name":"Ana"}, USER,
         "createUser", "mutation($name:String!){ createUser(displayName:$name){ id displayName } }", {"name":"Ana"}, GQL_USER),
    case("channels", ChannelsClient, "list_channels", [], "GET", "/api/v1/channels", None, [CHANNEL],
         "channels", "{ channels { id name } }", {}, [GQL_CHANNEL]),
    case("channels", ChannelsClient, "get_channel", ["c-1"], "GET", "/api/v1/channels/c-1", None, CHANNEL,
         "channel", "query($id:ID!){ channel(id:$id){ id name } }", {"id":"c-1"}, GQL_CHANNEL),
    case("channels", ChannelsClient, "create_channel", ["general"], "POST", "/api/v1/channels", {"name":"general"}, CHANNEL,
         "createChannel", "mutation($name:String!){ createChannel(name:$name){ id name } }", {"name":"general"}, GQL_CHANNEL),
    case("messages", MessagesClient, "list_messages", ["c-1"], "GET", MSG_PATH, None, [MESSAGE],
         "messages", "query($c:ID!){ messages(channelId:$c){ id channelId authorId content createdAt } }", {"c":"c-1"}, [GQL_MESSAGE]),
    case("messages", MessagesClient, "send_message", ["c-1","u-1","Hola"], "POST", MSG_PATH,
         {"author_id":"u-1","content":"Hola"}, MESSAGE,
         "sendMessage", "mutation($c:ID!,$a:ID!,$text:String!){ sendMessage(channelId:$c,authorId:$a,content:$text){ id channelId authorId content createdAt } }",
         {"c":"c-1","a":"u-1","text":"Hola"}, GQL_MESSAGE),
    case("threads", ThreadsClient, "list_replies", ["c-1","m-1"], "GET", REPLY_PATH, None, [REPLY],
         "replies", "query($c:ID!,$m:ID!){ replies(channelId:$c,messageId:$m){ id channelId messageId authorId content createdAt } }",
         {"c":"c-1","m":"m-1"}, [GQL_REPLY]),
    case("threads", ThreadsClient, "create_reply", ["c-1","m-1","u-1","Hola"], "POST", REPLY_PATH,
         {"author_id":"u-1","content":"Hola"}, REPLY,
         "createReply", "mutation($c:ID!,$m:ID!,$a:ID!,$text:String!){ createReply(channelId:$c,messageId:$m,authorId:$a,content:$text){ id channelId messageId authorId content createdAt } }",
         {"c":"c-1","m":"m-1","a":"u-1","text":"Hola"}, GQL_REPLY),
]
