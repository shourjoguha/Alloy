/**
 * Feature flags for controlling application behavior
 * These flags can be toggled to enable/disable features without code changes
 */

export interface OnboardingFeatureFlags {
  /** Whether the onboarding flow is enabled at all */
  enabled: boolean;
  /** Whether users can skip the onboarding process */
  allowSkip: boolean;
  /** Whether completion is enforced for new users */
  requiredForNewUsers: boolean;
}

export const ONBOARDING_FEATURES: OnboardingFeatureFlags = {
  enabled: true,
  allowSkip: true,
  requiredForNewUsers: false,
};
