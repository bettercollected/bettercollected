import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import FormsContainer from 'src/components/cards/form-container';

describe('Form Card Render Test', () => {
    it('renders the card component', () => {
        render(<FormsContainer />);
        expect(screen.getByTestId('forms-container')).toBeInTheDocument();
    });

    it('renders the card children', () => {
        render(
            <FormsContainer>
                <div data-testid="form-container-child"></div>
            </FormsContainer>
        );
        expect(screen.getByTestId('form-container-child')).toBeInTheDocument();
    });
});
