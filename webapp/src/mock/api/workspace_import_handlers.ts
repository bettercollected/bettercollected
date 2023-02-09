import { rest } from 'msw';

export const workspace_import_handlers = [
    rest.get('http://localhost:8000/forms/import', (req, res, ctx) => {
        return res();
    }),
    rest.get('http://localhost:8000/forms/import/:form_id', (req, res, ctx) => {
        return res();
    }),
    rest.post('http://localhost:8000/workspaces/:workspace_id/forms/import', (req, res, ctx) => {
        return res();
    }),
    rest.post('http://localhost:8000/workspaces/:workspace_id/forms/import/typeform', (req, res, ctx) => {
        return res();
    }),
    rest.get('http://localhost:8000/typeform/import', (req, res, ctx) => {
        return res();
    }),
    rest.get('http://localhost:8000/typeform/import/:form_id', (req, res, ctx) => {
        return res();
    })
];
