import { auth_handlers } from '@app/mock/api/auth_handlers';
import { workspace_forms_handlers } from '@app/mock/api/workspace_forms_handlers';
import { workspace_handlers } from '@app/mock/api/workspace_handlers';
import { workspace_import_handlers } from '@app/mock/api/workspace_import_handlers';
import { workspace_responses_handlers } from '@app/mock/api/workspace_responses_handlers';


export const handlers = [...auth_handlers, ...workspace_handlers, ...workspace_forms_handlers, ...workspace_responses_handlers, ...workspace_import_handlers];