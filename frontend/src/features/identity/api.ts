import { graphqlClient, gql } from '../../lib/graphql';

export interface User { id: string; displayName: string }
export const userKey = (id: string) => ['users', id] as const;
export async function getUser(id: string, signal?: AbortSignal) {
  const data = await graphqlClient.request<{ user: User | null }>({
    document: gql`query GetUser($id: ID!) { user(id: $id) { id displayName } }`,
    variables: { id }, signal,
  });
  return data.user;
}
export async function createUser(name: string) {
  const data = await graphqlClient.request<{ createUser: User }>({
    document: gql`mutation CreateUser($name: String!) { createUser(displayName: $name) { id displayName } }`,
    variables: { name },
  });
  return data.createUser;
}
