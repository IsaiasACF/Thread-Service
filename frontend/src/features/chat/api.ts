import { graphqlClient, gql } from '../../lib/graphql';

export interface Channel { id: string; name: string }
export interface Message { id: string; channelId: string; authorId: string; content: string; createdAt: string }
export interface Reply extends Message { messageId: string }
export const channelsKey = ['channels'] as const;
export const channelKey = (id: string) => ['channel', id] as const;
export const messagesKey = (id: string) => ['messages', id] as const;
export const repliesKey = (channel: string, message: string) => ['replies', channel, message] as const;

export async function getChannels(signal?: AbortSignal) {
  return (await graphqlClient.request<{ channels: Channel[] }>({
    document: gql`query GetChannels { channels { id name } }`, signal,
  })).channels;
}
export async function getChannel(id: string, signal?: AbortSignal) {
  return (await graphqlClient.request<{ channel: Channel | null }>({
    document: gql`query GetChannel($id: ID!) { channel(id: $id) { id name } }`, variables: { id }, signal,
  })).channel;
}
export async function createChannel(name: string) {
  return (await graphqlClient.request<{ createChannel: Channel }>({
    document: gql`mutation CreateChannel($name: String!) { createChannel(name: $name) { id name } }`, variables: { name },
  })).createChannel;
}
export async function getMessages(channelId: string, signal?: AbortSignal) {
  return (await graphqlClient.request<{ messages: Message[] }>({
    document: gql`query GetMessages($channelId: ID!) {
      messages(channelId: $channelId) { id channelId authorId content createdAt }
    }`, variables: { channelId }, signal,
  })).messages;
}
export async function sendMessage(channelId: string, authorId: string, content: string) {
  return (await graphqlClient.request<{ sendMessage: Message }>({
    document: gql`mutation SendMessage($channelId: ID!, $authorId: ID!, $content: String!) {
      sendMessage(channelId: $channelId, authorId: $authorId, content: $content) { id channelId authorId content createdAt }
    }`, variables: { channelId, authorId, content },
  })).sendMessage;
}
export async function getReplies(channelId: string, messageId: string, signal?: AbortSignal) {
  return (await graphqlClient.request<{ replies: Reply[] }>({
    document: gql`query GetReplies($channelId: ID!, $messageId: ID!) {
      replies(channelId: $channelId, messageId: $messageId) { id channelId messageId authorId content createdAt }
    }`, variables: { channelId, messageId }, signal,
  })).replies;
}
export async function createReply(channelId: string, messageId: string, authorId: string, content: string) {
  return (await graphqlClient.request<{ createReply: Reply }>({
    document: gql`mutation CreateReply($channelId: ID!, $messageId: ID!, $authorId: ID!, $content: String!) {
      createReply(channelId: $channelId, messageId: $messageId, authorId: $authorId, content: $content) {
        id channelId messageId authorId content createdAt
      }
    }`, variables: { channelId, messageId, authorId, content },
  })).createReply;
}
