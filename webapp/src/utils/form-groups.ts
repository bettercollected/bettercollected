import { ResponderGroupDto } from '@app/models/dtos/groups';

/**
 * The groups a form should end up in, without blanks or duplicates.
 * `PATCH …/groups/add` REPLACES the form's groups with the ids it is sent,
 * so callers must always pass the complete set, existing groups included.
 */
export function formGroupsAfterSave(groups: Array<ResponderGroupDto | null | undefined>): Array<ResponderGroupDto> {
    const seen = new Set<string>();
    const result: Array<ResponderGroupDto> = [];
    for (const group of groups) {
        if (!group?.id || seen.has(group.id)) continue;
        seen.add(group.id);
        result.push(group);
    }
    return result;
}
