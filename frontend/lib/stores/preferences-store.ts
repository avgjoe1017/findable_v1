import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

interface PreferencesState {
  // Dashboard preferences
  sitesViewMode: 'grid' | 'table'
  sitesSortBy: 'name' | 'created_at' | 'latest_score'
  sitesSortOrder: 'asc' | 'desc'

  // Report preferences
  showMath: boolean
  expandAllFixes: boolean

  // UI preferences
  sidebarCollapsed: boolean

  // Actions
  setSitesViewMode: (mode: 'grid' | 'table') => void
  setSitesSort: (sortBy: 'name' | 'created_at' | 'latest_score', sortOrder: 'asc' | 'desc') => void
  setShowMath: (show: boolean) => void
  setExpandAllFixes: (expand: boolean) => void
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void
}

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      // Defaults
      sitesViewMode: 'table',
      sitesSortBy: 'latest_score',
      sitesSortOrder: 'desc',
      showMath: false,
      expandAllFixes: false,
      sidebarCollapsed: false,

      // Actions
      setSitesViewMode: (mode) => set({ sitesViewMode: mode }),
      setSitesSort: (sortBy, sortOrder) => set({ sitesSortBy: sortBy, sitesSortOrder: sortOrder }),
      setShowMath: (show) => set({ showMath: show }),
      setExpandAllFixes: (expand) => set({ expandAllFixes: expand }),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
    }),
    {
      name: 'preferences-storage',
      storage: createJSONStorage(() => localStorage),
    }
  )
)

// Selectors
export const selectSitesViewMode = (state: PreferencesState) => state.sitesViewMode
export const selectSitesSort = (state: PreferencesState) => ({
  sortBy: state.sitesSortBy,
  sortOrder: state.sitesSortOrder,
})
export const selectShowMath = (state: PreferencesState) => state.showMath
export const selectExpandAllFixes = (state: PreferencesState) => state.expandAllFixes
export const selectSidebarCollapsed = (state: PreferencesState) => state.sidebarCollapsed
