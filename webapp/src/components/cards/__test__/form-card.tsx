import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import FormsCard from 'src/components/cards/form-card';

describe('Form Card Render Test', () => {
    it('renders the card component', () => {
        render(<FormsCard />);
        expect(screen.getByTestId('form-card')).toBeInTheDocument();
    });

    it('renders the card children', () => {
        render(
            <FormsCard>
                <div data-testid="form-card-child"></div>
            </FormsCard>
        );
        expect(screen.getByTestId('form-card-child')).toBeInTheDocument();
    });
});
