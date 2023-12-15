import type {Preview} from '@storybook/react';

import '../src/assets/css/globals.css';
import {Provider} from "react-redux";
import {store} from "@app/store/store";

const preview: Preview = {
    parameters: {
        actions: {argTypesRegex: '^on[A-Z].*'},
        controls: {
            matchers: {
                color: /(background|color)$/i,
                date: /Date$/i
            }
        }
    },
    decorators: [(Story) => <Provider store={store}>
        <Story/>
    </Provider>]
};

export default preview;
