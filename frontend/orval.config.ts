import { defineConfig } from 'orval';

export default defineConfig({
  api: {
    input: '../backend/openapi.json',
    output: {
      mode: 'tags-split',
      target: 'lib/api/generated.ts',
      schemas: 'lib/api/model',
      client: 'react-query',
    },
  },
});
