import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

// Infrastructure smoke test: proves the React 19 + Testing Library + jsdom
// rendering pipeline works end to end. Uses a self-contained component so it
// stays green regardless of app-level providers — a starting point for real
// component tests to build on.
function Greeting({ name }: { name: string }) {
    return <h1>Hello, {name}!</h1>;
}

describe('rendering pipeline', () => {
    it('renders a component to the DOM', () => {
        render(<Greeting name="bettercollected" />);
        expect(screen.getByRole('heading', { name: 'Hello, bettercollected!' })).toBeInTheDocument();
    });
});
