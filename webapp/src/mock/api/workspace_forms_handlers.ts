import { rest } from 'msw';

export const workspace_forms_handlers = [
    rest.get('http://localhost:8000/workspaces/:workspace_id/forms', (req, res, ctx) => {
        return res();
    }),
    rest.get('http://localhost:8000/workspaces/:workspace_id/forms/:form_id', (req, res, ctx) => {
        return res();
    }),
    rest.post('http://localhost:8000/workspaces/:workspace_id/forms/search', (req, res, ctx) => {
        return res();
    }),
    rest.patch('http://localhost:8000/workspaces/:workspace_id/forms/:form_id/settings', (req, res, ctx) => {
        return res();
    })
];
