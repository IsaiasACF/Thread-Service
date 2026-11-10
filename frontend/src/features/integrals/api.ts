import { graphqlClient, gql } from '../../lib/graphql';

export interface Integral {
  id: string; latex: string; status: 'calculated' | 'failed'; durationMs: number; createdAt: string;
  result: { latex: string; numeric: number | null; indefinite: boolean } | null;
  error: { code: string; message: string } | null;
  source: { kind: string; channelId: string | null; authorId: string | null; messageId: string | null };
}
export interface IntegralPage { items: Integral[]; total: number; limit: number; offset: number }
const fields = `id latex status durationMs createdAt result { latex numeric indefinite }
 error { code message } source { kind channelId authorId messageId }`;
export async function getIntegrals(limit: number, offset: number, status: string | null, signal?: AbortSignal) {
  return (await graphqlClient.request<{ integrals: IntegralPage }>({
    document: gql`query IntegralHistory($limit:Int!,$offset:Int!,$status:String) {
      integrals(limit:$limit,offset:$offset,status:$status) { items { ${fields} } total limit offset }
    }`, variables: { limit, offset, status }, signal,
  })).integrals;
}
export async function getIntegral(id: string, signal?: AbortSignal) {
  return (await graphqlClient.request<{ integral: Integral | null }>({
    document: gql`query IntegralDetail($id:ID!) { integral(id:$id) { ${fields} } }`, variables: { id }, signal,
  })).integral;
}
export async function calculateIntegral(latex: string) {
  return (await graphqlClient.request<{ calculateIntegral: Integral }>({
    document: gql`mutation CalculateIntegral($latex:String!) { calculateIntegral(latex:$latex) { ${fields} } }`,
    variables: { latex },
  })).calculateIntegral;
}
