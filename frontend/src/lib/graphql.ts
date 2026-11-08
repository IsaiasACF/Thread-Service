import { GraphQLClient } from 'graphql-request';

// Same-origin endpoint. Vite proxies it in development; hosting must proxy it in production.
export const graphqlClient = new GraphQLClient(new URL('/graphql', window.location.origin).href);
export { gql } from 'graphql-request';
