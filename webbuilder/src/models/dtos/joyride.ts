import {
    BaseProps,
    CallBackProps,
    Props as JoyRideState,
    StoreHelpers
} from 'react-joyride';

export interface JoyrideState extends JoyRideState {
    id: string;
    finished: boolean;
    lifecycle: string;
}

export interface JoyrideStateWithoutSteps extends BaseProps {
    id: string;
    finished: boolean;
    lifecycle: string;
    callback?: (data: CallBackProps) => void;
    continuous?: boolean;
    debug?: boolean;
    getHelpers?: (helpers: StoreHelpers) => any;
    run?: boolean;
    scrollDuration?: number;
    scrollOffset?: number;
    scrollToFirstStep?: boolean;
    stepIndex?: number;
}
