// Extends Vitest's `expect` with jest-dom matchers (toBeInTheDocument, etc.)
// and clears the rendered DOM between tests.
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(() => {
    cleanup();
});
