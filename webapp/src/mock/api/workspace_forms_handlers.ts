import { rest } from 'msw';

import { dashboardFormMock, dashboardFormsArrayMock } from '@app/mock/data/standard-form-mock';

export const workspace_forms_handlers = [
    rest.get('http://localhost:8000/workspaces/:workspace_id/forms', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: dashboardFormsArrayMock
                }
            })
        );
    }),
    rest.get('http://localhost:8000/workspaces/:workspace_id/forms/:form_id', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: dashboardFormMock
                }
            })
        );
    }),
    rest.post('http://localhost:8000/workspaces/:workspace_id/forms/search', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: dashboardFormsArrayMock
                }
            })
        );
    }),
    rest.patch('http://localhost:8000/workspaces/:workspace_id/forms/:form_id/settings', (req, res, context) => {
        return res();
    })
];
