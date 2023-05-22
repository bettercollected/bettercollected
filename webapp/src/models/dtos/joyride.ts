import { Props as JoyRideState } from 'react-joyride';

export interface JoyrideState extends JoyRideState {
    id: string;
    finished: boolean;
}
