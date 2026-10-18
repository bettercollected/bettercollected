import type { FormOp, FormOpName } from '../types';
import type { Handler } from './context';
import { addChoice, insertField, insertPage, moveChoice, removeChoice, replaceField, setChoice, setHiddenFields, updateLogo, updatePage, updateWelcomePage } from './editor';
import { addEnding, removeEnding, setEndings, updateEnding } from './endings';
import { addField, addGroup, moveField, removeField, setFieldLogic, setFieldValidation, updateField } from './fields';
import { setFormLanguage, setThemePreset, updateFormInfo, updateFormSettings, updateTheme } from './form';
import { addPage, duplicatePage, movePage, removePage, setPageJumps, setQuestionNumbering, setSectionTitle } from './pages';

/** The handler of each op, in the backend's order (ops.py `_HANDLERS`), then the editor ops. */
export const HANDLERS: { [K in FormOpName]: Handler<Extract<FormOp, { op: K }>> } = {
    add_field: addField,
    add_group: addGroup,
    update_field: updateField,
    remove_field: removeField,
    move_field: moveField,
    add_page: addPage,
    remove_page: removePage,
    update_form_info: updateFormInfo,
    update_form_settings: updateFormSettings,
    set_field_logic: setFieldLogic,
    set_page_jumps: setPageJumps,
    duplicate_page: duplicatePage,
    update_theme: updateTheme,
    set_theme_preset: setThemePreset,
    set_section_title: setSectionTitle,
    move_page: movePage,
    set_field_validation: setFieldValidation,
    set_question_numbering: setQuestionNumbering,
    set_form_language: setFormLanguage,
    add_ending: addEnding,
    update_ending: updateEnding,
    remove_ending: removeEnding,
    insert_field: insertField,
    replace_field: replaceField,
    insert_page: insertPage,
    update_page: updatePage,
    update_welcome_page: updateWelcomePage,
    set_hidden_fields: setHiddenFields,
    update_logo: updateLogo,
    set_choice: setChoice,
    add_choice: addChoice,
    remove_choice: removeChoice,
    move_choice: moveChoice,
    set_endings: setEndings
};

/** Ops only the builder sends; the AI and the API never get them. */
export const EDITOR_ONLY_OPS: ReadonlySet<string> = new Set<FormOpName>(['insert_field', 'replace_field', 'insert_page', 'update_page', 'update_welcome_page', 'set_hidden_fields', 'update_logo', 'set_choice', 'add_choice', 'remove_choice', 'move_choice', 'set_endings']);

export const OP_NAMES: ReadonlySet<string> = new Set(Object.keys(HANDLERS));
