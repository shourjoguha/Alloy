import { useEffect, useState } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { useUserProfile, useUpdateUserProfile } from '@/api/settings';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Spinner } from '@/components/common/Spinner';
import { useUIStore } from '@/stores/ui-store';
import { ExperienceLevel, PersonaTone, Sex } from '@/types';
import type { UserProfileUpdate } from '@/types';
import { ChevronDown, ChevronUp } from 'lucide-react';

export function ProfileTab() {
  const { data: profile, isLoading, error: profileError } = useUserProfile();
  const updateMutation = useUpdateUserProfile();
  const { addToast } = useUIStore();
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

  const { register, handleSubmit, reset, control, formState: { isDirty } } = useForm<UserProfileUpdate>();

  const disciplinePrefs = useWatch({ control, name: 'discipline_preferences' });

  useEffect(() => {
    console.log('Profile data:', profile);
    console.log('Profile error:', profileError);
    if (profile) {
      reset({
        name: profile.name,
        experience_level: profile.experience_level,
        persona_tone: profile.persona_tone,
        persona_aggression: profile.persona_aggression,
        date_of_birth: profile.date_of_birth,
        sex: profile.sex,
        height_cm: profile.height_cm,
        discipline_preferences: profile.discipline_preferences || {
          mobility: 5,
          calisthenics: 5,
          olympic_lifts: 0,
          crossfit: 0,
          strength: 10,
        },
        discipline_experience: profile.discipline_experience || {},
        scheduling_preferences: profile.scheduling_preferences || {
          mix_disciplines: true,
          cardio_preference: 'finisher',
          endurance_dedicated_cardio_day_policy: 'default',
          microcycle_length_days: 'auto',
          split_template_preference: 'none',
        },
        long_term_goal_category: profile.long_term_goal_category || 'general_fitness',
        long_term_goal_description: profile.long_term_goal_description || '',
      });
    }
  }, [profile, reset, profileError]);

  const onSubmit = async (data: UserProfileUpdate) => {
    try {
      let scheduling_preferences = data.scheduling_preferences;
      if (scheduling_preferences) {
        const microcycle = scheduling_preferences.microcycle_length_days;
        if (typeof microcycle === 'string' && microcycle !== 'auto') {
          scheduling_preferences = {
            ...scheduling_preferences,
            microcycle_length_days: Number(microcycle),
          };
        }
      }

      const payload: Partial<UserProfileUpdate> = {};
      
      if (data.name !== undefined && data.name !== '') payload.name = data.name;
      if (data.experience_level !== undefined) payload.experience_level = data.experience_level;
      if (data.persona_tone !== undefined) payload.persona_tone = data.persona_tone;
      if (data.persona_aggression !== undefined) payload.persona_aggression = data.persona_aggression;
      if (data.date_of_birth !== undefined && data.date_of_birth !== '' && data.date_of_birth !== null) payload.date_of_birth = data.date_of_birth;
      if (data.sex !== undefined && data.sex !== null) payload.sex = data.sex;
      if (data.height_cm !== undefined) payload.height_cm = Number(data.height_cm);
      
      if (data.discipline_preferences) {
        payload.discipline_preferences = {
          mobility: Number(data.discipline_preferences.mobility),
          calisthenics: Number(data.discipline_preferences.calisthenics),
          olympic_lifts: Number(data.discipline_preferences.olympic_lifts),
          crossfit: Number(data.discipline_preferences.crossfit),
          strength: Number(data.discipline_preferences.strength),
        };
      }
      
      if (data.scheduling_preferences) {
        payload.scheduling_preferences = scheduling_preferences;
      }
      
      if (data.discipline_experience) {
        payload.discipline_experience = data.discipline_experience;
      }
      
      if (data.long_term_goal_category !== undefined) payload.long_term_goal_category = data.long_term_goal_category;
      if (data.long_term_goal_description !== undefined) payload.long_term_goal_description = data.long_term_goal_description;
      
      console.log('Submitting profile update:', payload);
      await updateMutation.mutateAsync(payload);
      addToast({
        type: 'success',
        message: 'Profile updated successfully',
      });
    } catch (error: unknown) {
      console.error('Profile update error:', error);
      const err = error as { response?: { data?: { detail?: string | { msg?: string }[] } } };
      console.error('Error response:', err.response);
      console.error('Error data:', err.response?.data);
      
      let errorMessage = 'Failed to update profile';

      if (err.response?.data?.detail) {
        if (typeof err.response.data.detail === 'string') {
          errorMessage = err.response.data.detail;
        } else if (Array.isArray(err.response.data.detail)) {
          errorMessage = err.response.data.detail.map((e: { msg?: string }) => e.msg || JSON.stringify(e)).join(', ');
        } else if (typeof err.response.data.detail === 'object') {
          errorMessage = JSON.stringify(err.response.data.detail);
        }
      } else if (error instanceof Error && error.message) {
        errorMessage = error.message;
      }
      
      addToast({
        type: 'error',
        message: errorMessage,
      });
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-6">
        <Spinner size="sm" />
      </div>
    );
  }

  return (
    <Card variant="grouped" className="p-6">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6 max-w-2xl">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Personal Info */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Name</label>
            <input
              {...register('name')}
              className="w-full rounded-md border-0 bg-background-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="Your name"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Date of Birth</label>
            <input
              type="date"
              {...register('date_of_birth')}
              className="w-full rounded-md border-0 bg-background-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Sex</label>
            <select
              {...register('sex')}
              className="w-full rounded-md border-0 bg-background-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">Select sex</option>
              {Object.values(Sex).map((value) => (
                <option key={value} value={value} className="capitalize">
                  {value}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Height (cm)</label>
            <input
              type="number"
              {...register('height_cm')}
              className="w-full rounded-md border-0 bg-background-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="175"
            />
          </div>

          {/* Training Profile */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Experience Level</label>
            <select
              {...register('experience_level')}
              className="w-full rounded-md border-0 bg-background-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {Object.values(ExperienceLevel).map((value) => (
                <option key={value} value={value} className="capitalize">
                  {value.replace('_', ' ')}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Persona Tone</label>
            <select
              {...register('persona_tone')}
              className="w-full rounded-md border-0 bg-background-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {Object.values(PersonaTone).map((value) => (
                <option key={value} value={value} className="capitalize">
                  {value.replace('_', ' ')}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2 md:col-span-2">
            <label className="text-sm font-medium">Coach Aggression</label>
            <select
              {...register('persona_aggression')}
              className="w-full px-3 py-2 border rounded-lg bg-background text-foreground"
            >
              <option value="CONSERVATIVE">Conservative</option>
              <option value="MODERATE_CONSERVATIVE">Moderate Conservative</option>
              <option value="BALANCED">Balanced</option>
              <option value="MODERATE_AGGRESSIVE">Moderate Aggressive</option>
              <option value="AGGRESSIVE">Aggressive</option>
            </select>
          </div>

          {/* Long Term Goals */}
          <div className="space-y-4 md:col-span-2 pt-4 border-t border-border">
            <h4 className="text-sm font-semibold text-foreground">Long Term Goals</h4>
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Primary Goal Category</label>
                <select
                  {...register('long_term_goal_category')}
                  className="w-full rounded-md border-0 bg-background-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="general_fitness">General Fitness</option>
                  <option value="muscle_gain">Muscle Gain</option>
                  <option value="fat_loss">Fat Loss</option>
                  <option value="strength">Strength</option>
                  <option value="performance">Performance</option>
                  <option value="health_longevity">Health & Longevity</option>
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Goal Description</label>
                <textarea
                  {...register('long_term_goal_description')}
                  className="w-full rounded-md border-0 bg-background-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary min-h-[100px]"
                  placeholder="Describe your goal for next 1-3 years (e.g., run a marathon, gain 10lbs of muscle)"
                />
                <p className="text-xs text-foreground-muted">
                  What do you want to achieve over the next 1-3 years?
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Advanced Filters Section */}
        <Card variant="grouped" className="border border-border">
          <button
            type="button"
            onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
            className="flex w-full items-center justify-between p-4 text-sm font-medium hover:bg-background-secondary transition-colors rounded-lg"
          >
            <span>Advanced Filters</span>
            {isAdvancedOpen ? (
              <ChevronUp className="h-4 w-4 text-foreground-muted" />
            ) : (
              <ChevronDown className="h-4 w-4 text-foreground-muted" />
            )}
          </button>

          {isAdvancedOpen && (
            <div className="p-4 pt-0 space-y-6 border-t border-border mt-2 animate-in slide-in-from-top-2">
              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-foreground">Discipline Settings</h4>
                  <p className="text-xs text-foreground-muted">
                    Set your interest priority (0-10) and experience level for each discipline.
                  </p>
                </div>

                {/* Header for larger screens */}
                <div className="hidden sm:grid sm:grid-cols-12 gap-4 text-xs font-medium text-foreground-muted px-1">
                  <div className="col-span-4">Discipline</div>
                  <div className="col-span-5">Interest Priority</div>
                  <div className="col-span-3">Experience</div>
                </div>

                <div className="space-y-6 sm:space-y-3">
                  {(
                    [
                      { key: 'strength', label: 'Strength & Hypertrophy' },
                      { key: 'mobility', label: 'Mobility & Flexibility' },
                      { key: 'calisthenics', label: 'Calisthenics (Bodyweight)' },
                      { key: 'olympic_lifts', label: 'Olympic Weightlifting' },
                      { key: 'crossfit', label: 'CrossFit / Metcon' },
                    ] as const
                  ).map((discipline) => (
                    <div key={discipline.key} className="grid grid-cols-1 sm:grid-cols-12 gap-2 sm:gap-4 items-center p-2 sm:p-0 rounded-lg hover:bg-background-secondary transition-colors">

                      {/* Label */}
                      <div className="sm:col-span-4">
                        <label className="text-sm font-medium">{discipline.label}</label>
                      </div>

                      {/* Slider */}
                      <div className="sm:col-span-5 flex items-center gap-3">
                        <input
                          type="range"
                          min="0"
                          max="10"
                          step="1"
                          {...register(`discipline_preferences.${discipline.key}`)}
                          className="flex-1 cursor-pointer h-2 bg-background-input rounded-lg appearance-none [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary accent-primary"
                        />
                        <span className="w-6 text-right text-sm font-medium text-foreground-muted">
                          {disciplinePrefs?.[discipline.key] || 0}
                        </span>
                      </div>

                      {/* Experience Select */}
                      <div className="sm:col-span-3">
                        <select
                          {...register(`discipline_experience.${discipline.key}`)}
                          className="w-full rounded-md border-0 bg-background-input px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                        >
                          <option value="">Level</option>
                          {Object.values(ExperienceLevel).map((level) => (
                            <option key={level} value={level}>
                              {level.replace('_', ' ')}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-4 pt-4 border-t border-border">
                <h4 className="text-sm font-semibold text-foreground">Scheduling Preferences</h4>

                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <label className="text-sm font-medium">Mix Disciplines</label>
                    <p className="text-xs text-foreground-muted">
                      Allow combining different styles (e.g. mobility + strength) in a single session.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    {...register('scheduling_preferences.mix_disciplines')}
                    className="h-4 w-4 rounded border-border text-primary focus:ring-primary accent-primary"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Conditioning & Cardio</label>
                  <p className="text-xs text-foreground-muted">How should we schedule your cardio?</p>
                  <select
                    {...register('scheduling_preferences.cardio_preference')}
                    className="w-full rounded-md border-0 bg-background-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="none">None / I do it separately</option>
                    <option value="finisher">Add as finishers (10-20 mins)</option>
                    <option value="dedicated_day">Dedicated cardio or conditioning day</option>
                    <option value="mixed">Mix both (finishers + dedicated)</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Endurance-Heavy Cardio Day</label>
                  <p className="text-xs text-foreground-muted">
                    When endurance is your top goal, include at least one dedicated cardio day per 14-day microcycle.
                  </p>
                  <select
                    {...register('scheduling_preferences.endurance_dedicated_cardio_day_policy')}
                    className="w-full rounded-md border-0 bg-background-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="default">Use system default</option>
                    <option value="always">Always include a cardio day</option>
                    <option value="never">Never include a cardio day</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Microcycle Duration</label>
                  <p className="text-xs text-foreground-muted">
                    Defaults to 14 days. You can also let the system decide.
                  </p>
                  <select
                    {...register('scheduling_preferences.microcycle_length_days')}
                    className="w-full rounded-md border-0 bg-background-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="auto">Auto (recommended)</option>
                    {[7, 8, 9, 10, 11, 12, 13, 14].map((d) => (
                      <option key={d} value={d}>{d} days</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Split Template Preference</label>
                  <p className="text-xs text-foreground-muted">
                    Stored as a preference only. Scheduling is not constrained by templates by default.
                  </p>
                  <select
                    {...register('scheduling_preferences.split_template_preference')}
                    className="w-full rounded-md border-0 bg-background-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="none">None</option>
                    <option value="full_body">Full Body</option>
                    <option value="upper_lower">Upper/Lower</option>
                    <option value="ppl">PPL</option>
                    <option value="hybrid">Hybrid</option>
                  </select>
                </div>
              </div>
            </div>
          )}
        </Card>

        <div className="flex justify-end pt-4">
          <Button type="submit" disabled={!isDirty || updateMutation.isPending}>
            {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      </form>
    </Card>
  );
}
