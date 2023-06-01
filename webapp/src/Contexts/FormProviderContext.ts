import { createContext } from 'react';

import { IntegrationFormProviders } from '@app/models/dtos/provider';

const FormProviderContext = createContext<Array<IntegrationFormProviders>>([]);

export default FormProviderContext;
