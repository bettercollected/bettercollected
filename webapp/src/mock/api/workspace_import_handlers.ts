import { rest } from 'msw';

import { importTypeformArrayMock, importTypeformMock } from '@app/mock/data/import-google-forms-mock';
import { importGoogleFormMock, importGoogleFormsArrayMock } from '@app/mock/data/import-type-form-mock';

export const workspace_import_handlers = [
    rest.get('http://localhost:8000/forms/import', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: importGoogleFormsArrayMock
                }
            })
        );
    }),
    rest.get('http://localhost:8000/forms/import/:form_id', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: importGoogleFormMock
                }
            })
        );
    }),
    rest.post('http://localhost:8000/workspaces/:workspace_id/forms/import', (req, res, context) => {
        return res(context.body(JSON.stringify('success')));
    }),
    rest.post('http://localhost:8000/workspaces/:workspace_id/forms/import/typeform', (req, res, context) => {
        return res(context.body(JSON.stringify('success')));
    }),
    rest.get('http://localhost:8000/typeform/import', (req, res, context) => {
        return res(context.json(importTypeformArrayMock));
    }),
    rest.get('http://localhost:8000/typeform/import/:form_id', (req, res, context) => {
        return res(context.json(importTypeformMock));
    })
];
