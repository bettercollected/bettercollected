import { setupServer } from 'msw/node';

import { handlers } from './handler';

// @ts-ignore
export const server = setupServer(...handlers);
