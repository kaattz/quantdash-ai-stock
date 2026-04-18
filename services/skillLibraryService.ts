import { resolveScreenerApiBase } from './apiConfig';
import { loadAIIntegrationSettings, saveAIIntegrationSettings } from './modelIntegrationService';
import { AIIntegrationSettings, AISkillDefinition, SkillLibraryEntry } from '../types';


const SKILL_LIBRARY_ENDPOINT = `${resolveScreenerApiBase()}/integrations/skills/library`;

type SkillLibraryResponse = {
  entries?: SkillLibraryEntry[];
};

const isLibrarySkill = (skill: AISkillDefinition): boolean =>
  skill.source === 'library' || skill.id.startsWith('library:');

const buildLibrarySkill = (
  entry: SkillLibraryEntry,
  previous?: AISkillDefinition,
): AISkillDefinition => ({
  id: entry.id,
  name: entry.name,
  description: entry.description,
  instructions: entry.instructions,
  githubRepo: previous?.githubRepo ?? '',
  githubNotes: previous?.githubNotes ?? '',
  scopes: previous?.scopes?.length ? previous.scopes : entry.scopes,
  enabled: previous?.enabled ?? false,
  createdAt: previous?.createdAt ?? entry.updatedAt,
  updatedAt: entry.updatedAt,
  source: 'library',
  readOnly: true,
  libraryFileName: entry.fileName,
  sourceTitle: entry.sourceTitle,
});

const areSkillListsEqual = (left: AISkillDefinition[], right: AISkillDefinition[]): boolean =>
  JSON.stringify(left) === JSON.stringify(right);

export const fetchSkillLibraryEntries = async (): Promise<SkillLibraryEntry[] | null> => {
  try {
    const response = await fetch(SKILL_LIBRARY_ENDPOINT, {
      cache: 'no-store',
    });
    if (!response.ok) {
      return null;
    }
    const payload = (await response.json()) as SkillLibraryResponse;
    return Array.isArray(payload.entries) ? payload.entries : [];
  } catch (error) {
    console.warn('Failed to load skill library', error);
    return null;
  }
};

export const syncSkillLibraryIntoSettings = async (): Promise<AIIntegrationSettings> => {
  const entries = await fetchSkillLibraryEntries();
  const current = loadAIIntegrationSettings();
  if (entries === null) {
    return current;
  }

  const currentLibrary = new Map(
    current.skills.filter(isLibrarySkill).map((skill) => [skill.id, skill] as const),
  );
  const customSkills = current.skills.filter((skill) => !isLibrarySkill(skill));
  const librarySkills = entries.map((entry) => buildLibrarySkill(entry, currentLibrary.get(entry.id)));
  const mergedSkills = [...librarySkills, ...customSkills];

  if (areSkillListsEqual(current.skills, mergedSkills)) {
    return current;
  }

  return saveAIIntegrationSettings({
    ...current,
    skills: mergedSkills,
  });
};
