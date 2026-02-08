# Frontend Settings Tabs Debugging Report

**Date**: 2026-02-03  
**Issue**: FavoritesTab, ProgramsTab, and ProfileTab components not displaying data despite backend APIs returning correct data.

---

## Root Cause Analysis

### Primary Issue: Authentication Race Condition

The main problem is a **timing/race condition** in authentication initialization that prevents API calls from being made with valid authentication headers.

#### Evidence:

1. **Auto-login mechanism** in `useAuthInitialization` hook executes asynchronously in a `useEffect`
2. **React Query hooks** in components mount immediately and attempt to fetch data
3. **API client interceptor** reads token from auth store synchronously
4. **Result**: Queries execute before auto-login completes, causing:
   - Token is `null` initially
   - API calls proceed without authentication headers
   - Backend's `get_current_user_id` dependency returns `default_user_id` (user ID 1)
   - Data may be empty or incorrect if default user has no data

### Secondary Issues:

1. **Missing query enablement checks** - React Query hooks don't check if authentication is ready
2. **Insufficient logging** - No visibility into when queries execute vs. when auth completes
3. **No query invalidation after auth** - Queries that ran before auth aren't refetched after token is available

---

## Detailed Component Analysis

### FavoritesTab ([/Users/shourjosmac/Documents/alloy/frontend/src/components/settings/FavoritesTab.tsx](file:///Users/shourjosmac/Documents/alloy/frontend/src/components/settings/FavoritesTab.tsx))

**Issue**: `useUserMovementRules()` executes before auth is ready

```typescript
const { data: userPreferences, isLoading: isLoadingPreferences } = useUserMovementRules();
```

- Calls `useUserMovementRules()` which fetches from `/movement-preferences`
- Backend endpoint: `/api/movement-preferences` (GET)
- Expected response: 6 items according to user
- Problem: Query may return empty or fail if not authenticated

---

### ProgramsTab ([/Users/shourjosmac/Documents/alloy/frontend/src/components/settings/ProgramsTab.tsx](file:///Users/shourjosmac/Documents/alloy/frontend/src/components/settings/ProgramsTab.tsx))

**Issue**: `usePrograms(false)` executes before auth is ready

```typescript
const { data: programs, isLoading, error } = usePrograms(false);
```

- Calls `usePrograms(false)` which fetches from `/programs`
- Backend endpoint: `/api/programs` (GET)
- Expected response: 34+ items according to user
- Problem: Query may return empty or fail if not authenticated

---

### ProfileTab ([/Users/shourjosmac/Documents/alloy/frontend/src/components/settings/ProfileTab.tsx](file:///Users/shourjosmac/Documents/alloy/frontend/src/components/settings/ProfileTab.tsx))

**Issue**: `useUserProfile()` executes before auth is ready

```typescript
const { data: profile, isLoading, error: profileError } = useUserProfile();
```

- Calls `useUserProfile()` which fetches from `/settings/user/profile`
- Backend endpoint: `/api/settings/user/profile` (GET)
- Expected response: User profile data
- Problem: Query may return empty or fail if not authenticated

---

## Solutions Implemented

### Fix 1: Add Authentication-Aware Query Enablement

Modified all three API hooks to include `enabled` condition that checks both authentication state and token presence:

#### `/Users/shourjosmac/Documents/alloy/frontend/src/api/movement-preferences.ts`

```typescript
export function useUserMovementRules(
  options: MovementPreferencesQueryOptions = {},
) {
  const { isAuthenticated, token } = useAuthStore();
  return useQuery({
    queryKey: movementPreferencesKeys.list(options),
    queryFn: () => fetchMovementPreferences(options),
    enabled: isAuthenticated && !!token, // Only fetch when authenticated with a token
  });
}
```

#### `/Users/shourjosmac/Documents/alloy/frontend/src/api/programs.ts`

```typescript
export function usePrograms(activeOnly = false) {
  const { isAuthenticated, token } = useAuthStore();
  return useQuery({
    queryKey: programKeys.list({ active_only: activeOnly }),
    queryFn: () => fetchPrograms(activeOnly),
    enabled: isAuthenticated && !!token, // Only fetch when authenticated with a token
  });
}
```

#### `/Users/shourjosmac/Documents/alloy/frontend/src/api/settings.ts`

```typescript
export function useUserProfile() {
  const { isAuthenticated, token } = useAuthStore();
  return useQuery({
    queryKey: settingsKeys.profile(),
    queryFn: fetchUserProfile,
    enabled: isAuthenticated && !!token, // Only fetch when authenticated with a token
  });
}
```

**Impact**: Queries will not execute until both `isAuthenticated` is `true` AND a valid token exists.

---

### Fix 2: Enhanced Debug Logging

#### `/Users/shourjosmac/Documents/alloy/frontend/src/hooks/useAuthInitialization.ts`

Added comprehensive logging to track auth state:

```typescript
const DEBUG = true;
const debugLog = (...args: unknown[]) => {
  if (DEBUG) console.log('[useAuthInitialization]', ...args);
};

debugLog('Starting auth initialization', {
  hasToken: !!token,
  hasUser: !!user,
  isAuthenticated,
  pathname: location.pathname,
  isAuthRoute,
  _hasHydrated
});
```

**Logs added for**:
- Auth initialization start/end
- Token verification success/failure
- Auto-login start/completion
- Token presence status

#### `/Users/shourjosmac/Documents/alloy/frontend/src/api/client.ts`

Added request/response interceptor logging:

```typescript
const DEBUG_API = true;
const debugLog = (...args: unknown[]) => {
  if (DEBUG_API) console.log('[apiClient]', ...args);
};

// Request logging
debugLog('Request:', {
  method: config.method?.toUpperCase(),
  url: config.url,
  hasToken: !!token,
  isAuthenticated,
  baseURL: config.baseURL,
  fullUrl: `${config.baseURL}${config.url}`
});

// Response logging
debugLog('Response:', {
  status: response.status,
  url: response.config.url,
  dataKeys: Object.keys(response.data || {})
});

// Error logging
debugLog('Response error:', {
  status,
  url: error.config?.url,
  data: error.response.data,
  message: error.message
});
```

**Logs added for**:
- Every API request (method, URL, auth status)
- Every API response (status, data keys)
- Every API error (status, error data)
- Network errors

**Impact**: Full visibility into when API calls are made vs. when auth completes, enabling easy debugging.

---

## How the Fix Works

### Before Fix:

```
Component Mount
    ↓
useEffect (auth init) starts (async)
    ↓
React Query hook executes (immediate)
    ↓
API call without token
    ↓
Backend returns default user data (empty)
    ↓
Component displays empty state
    ↓
Auth completes (too late)
```

### After Fix:

```
Component Mount
    ↓
React Query hook executes but is disabled (enabled: false)
    ↓
useEffect (auth init) starts (async)
    ↓
Auto-login completes, token set
    ↓
Auth store updates (isAuthenticated: true, token: "...")
    ↓
React Query hook re-evaluates enabled condition
    ↓
Query now enabled, executes with token
    ↓
API call with Bearer token
    ↓
Backend returns authenticated user data
    ↓
Component displays data
```

---

## Testing Instructions

1. **Open browser console** to see debug logs
2. **Navigate to Settings** (http://localhost:5174/settings)
3. **Check console logs** for:
   - `[useAuthInitialization]` - Auth initialization steps
   - `[apiClient]` - All API requests/responses

### Expected Console Output:

```
[useAuthInitialization] Starting auth initialization { hasToken: false, hasUser: false, isAuthenticated: false, pathname: "/settings", isAuthRoute: false, _hasHydrated: false }
[useAuthInitialization] No auth found, starting auto-login
[useAuthInitialization] Login successful, got token
[useAuthInitialization] Auto-login complete, user authenticated { id: 1, email: "gainsmith@gainsly.com", ... }
[apiClient] Request: { method: "GET", url: "/movement-preferences", hasToken: true, isAuthenticated: true, baseURL: "/api", fullUrl: "/api/movement-preferences" }
[apiClient] Response: { status: 200, url: "/movement-preferences", dataKeys: ["items", "total"] }
[apiClient] Request: { method: "GET", url: "/programs", hasToken: true, isAuthenticated: true, baseURL: "/api", fullUrl: "/api/programs" }
[apiClient] Response: { status: 200, url: "/programs", dataKeys: [...] }
[apiClient] Request: { method: "GET", url: "/settings/user/profile", hasToken: true, isAuthenticated: true, baseURL: "/api", fullUrl: "/api/settings/user/profile" }
[apiClient] Response: { status: 200, url: "/settings/user/profile", dataKeys: [...] }
```

### Expected UI Behavior:

- **Favorites Tab**: Should display 6 movement preferences
- **Programs Tab**: Should display 34+ programs
- **Profile Tab**: Should display user profile form with current data

---

## Additional Recommendations

### 1. Disable Debug Logging in Production

Update the DEBUG flags to `false` before deploying:

```typescript
// In useAuthInitialization.ts
const DEBUG = false;

// In api/client.ts
const DEBUG_API = false;
```

### 2. Consider Adding Query Invalidation

After auth completes, invalidate any cached queries that ran before auth:

```typescript
// In useAuthInitialization.ts after auth completes
queryClient.invalidateQueries();
```

This ensures any cached empty data is refreshed with authenticated data.

### 3. Add Loading State Components

Consider adding skeleton loaders or better empty states while queries are loading:

```typescript
if (!isAuthenticated) {
  return <div className="p-4 text-center">Authenticating...</div>;
}
```

### 4. Monitor Backend Logs

The backend shows successful API calls (200 OK responses), confirming the endpoints work correctly when authenticated:

```
INFO:     127.0.0.1:52479 - "GET /settings/user/profile HTTP/1.1" 200 OK
```

---

## Summary

**Root Cause**: Authentication race condition - React Query hooks execute before auto-login completes.

**Solution**: Add `enabled` condition to all query hooks that checks both `isAuthenticated` and `token` presence.

**Files Modified**:
- `/Users/shourjosmac/Documents/alloy/frontend/src/api/movement-preferences.ts`
- `/Users/shourjosmac/Documents/alloy/frontend/src/api/programs.ts`
- `/Users/shourjosmac/Documents/alloy/frontend/src/api/settings.ts`
- `/Users/shourjosmac/Documents/alloy/frontend/src/hooks/useAuthInitialization.ts`
- `/Users/shourjosmac/Documents/alloy/frontend/src/api/client.ts`

**Status**: Fix implemented and ready for testing.

---

## Verification Steps

1. ✅ Backend is running (confirmed - uvicorn on port 8000)
2. ✅ Frontend is running (confirmed - vite on port 5174)
3. ✅ Proxy configuration is correct (VITE_API_URL=/api)
4. ✅ React Query is properly configured
5. ✅ Backend API endpoints work (confirmed - logs show 200 OK responses)
6. ⏳ **Test the fix in browser** at http://localhost:5174/settings

**Next Steps**: Open browser console and navigate to Settings to verify data now displays correctly.
