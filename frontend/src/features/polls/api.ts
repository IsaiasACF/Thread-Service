import { graphqlClient, gql } from '../../lib/graphql';

export interface Poll {
  pollId: string; channelId: string; authorId: string; question: string;
  options: { optionId: string; position: number; text: string; voteCount: number }[];
  status: 'pending_announcement' | 'open' | 'closed' | 'creation_failed';
  durationMinutes: number; closesAt: string; createdAt: string; closedAt: string | null;
  totalVotes: number; creationError: string | null;
}
export interface CreatePollInput { channelId: string; authorId: string; question: string; options: string[]; durationMinutes: number }
const fields = `pollId channelId authorId question options { optionId position text voteCount }
 status durationMinutes closesAt createdAt closedAt totalVotes creationError`;
export async function getPoll(id: string, signal?: AbortSignal) {
  return (await graphqlClient.request<{ poll: Poll | null }>({
    document: gql`query PollDetail($id:ID!) { poll(id:$id) { ${fields} } }`, variables: { id }, signal,
  })).poll;
}
export async function createPoll(input: CreatePollInput, idempotencyKey: string) {
  return (await graphqlClient.request<{ createPoll: Poll }>({
    document: gql`mutation CreatePoll($input:CreatePollInput!,$idempotencyKey:String!) {
      createPoll(input:$input,idempotencyKey:$idempotencyKey) { ${fields} }
    }`, variables: { input, idempotencyKey },
  })).createPoll;
}
export async function votePoll(pollId: string, voterId: string, optionId: string) {
  return (await graphqlClient.request<{ votePoll: { pollId: string; voterId: string; optionId: string; castAt: string } }>({
    document: gql`mutation VotePoll($pollId:ID!,$voterId:ID!,$optionId:ID!) {
      votePoll(pollId:$pollId,voterId:$voterId,optionId:$optionId) { pollId voterId optionId castAt }
    }`, variables: { pollId, voterId, optionId },
  })).votePoll;
}
export async function closePoll(pollId: string, authorId: string) {
  return (await graphqlClient.request<{ closePoll: Poll }>({
    document: gql`mutation ClosePoll($pollId:ID!,$authorId:ID!) {
      closePoll(pollId:$pollId,authorId:$authorId) { ${fields} }
    }`, variables: { pollId, authorId },
  })).closePoll;
}
